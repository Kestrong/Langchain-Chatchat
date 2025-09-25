import io
import json
import re
from typing import List, Dict, Literal
from urllib.parse import urlunparse, urlparse

import requests
from fastchat import conversation as conv
from fastchat.conversation import Conversation

from configs import logger
from server.db.repository import get_assistant_simple_from_db, get_model_metadata_from_db
from server.knowledge_base.oss import default_oss
from server.memory.token_info_memory import get_token_info
from server.model_workers import ApiModelWorker, ApiChatParams
from server.model_workers.dify import analyze_file


class FuXiWorker(ApiModelWorker):

    def __init__(
            self,
            *,
            model_names: List[str] = ["fuxi-api"],
            controller_addr: str = None,
            worker_addr: str = None,
            version: Literal["fuxi-v1"] = "fuxi-v1",
            **kwargs,
    ):
        kwargs.update(model_names=model_names, controller_addr=controller_addr, worker_addr=worker_addr)
        super().__init__(**kwargs)
        self.version = version

    def get_inputs(self, role_meta: dict, model_config: dict):
        return model_config.get('inputs') or role_meta.get("inputs", {})

    def replace_last_path_segment(self, url, new_segment):
        parsed_url = urlparse(url)

        # Split the path into segments
        path_segments = parsed_url.path.strip('/').split('/')

        # Replace the last segment if there are any
        if path_segments and path_segments[-1]:
            path_segments[-1] = new_segment
        else:
            # If the path ends with a slash or is empty, just set the new segment
            path_segments = [new_segment]

        # Rebuild the path
        new_path = '/' + '/'.join(path_segments)

        # Reconstruct the URL with the new path
        new_url = parsed_url._replace(path=new_path)
        return urlunparse(new_url)

    def upload_files(self, url, api_key, contentObj, file_type, extra_headers):
        result = []
        knowledge_id = contentObj.get('knowledge_id')
        files = contentObj.get('files')
        if not knowledge_id and not files:
            logger.debug("knowledge_id和files都为空，不需要上传")
            return result
        headers = {"X-API-KEY": api_key}
        if 'X-APP-ID' in extra_headers:
            headers['X-APP-ID'] = extra_headers['X-APP-ID']
        if 'X-APP-KEY' in extra_headers:
            headers['X-APP-KEY'] = extra_headers['X-APP-KEY']
        match = re.search(r'https?://[^?]*?/llm(?=/|$)', url)
        upload_url = f"{match.group(0)}/file/upload" if match else url
        logger.debug(f"上传内部和第三方文件到fuxi, url={upload_url}, knowledge_id={knowledge_id}, files={files}")
        if knowledge_id:
            attachment_names = default_oss().list_objects(bucket_name="temp", object_name=knowledge_id)
            if attachment_names:
                for a in attachment_names:
                    logger.debug(f"upload file: {a}")
                    with default_oss().get_object(bucket_name="temp", object_name=f"{knowledge_id}/{a}") as o:
                        file_prop = analyze_file(a)
                        with requests.post(url=upload_url, headers=headers,
                                           files=[("file", (a, o, file_prop.get('mime_type')))],
                                           verify=False) as response:
                            if not response.ok:
                                logger.error(response.text)
                            response.raise_for_status()
                            file = {
                                "type": file_type or file_prop.get('category'),
                                "docId": response.json().get('fileId')
                            }
                            result.append(file)
        if files:
            cookies = contentObj.get('cookies')
            get_file_headers = None
            if contentObj.get('token'):
                get_file_headers = {"Authorization": contentObj.get('token')}
            for f in files:
                logger.debug(f"upload file: {f.get('name')}")
                response = requests.get(f.get('url'), headers=get_file_headers, cookies=cookies, stream=True,
                                        verify=False)
                if not response.ok:
                    logger.error(response.text)
                response.raise_for_status()

                file_stream = io.BytesIO()
                try:
                    for chunk in response.iter_content(chunk_size=1024 * 64):
                        if chunk:
                            file_stream.write(chunk)
                    file_stream.seek(0)
                    file_prop = analyze_file(f.get('name'))
                    with requests.post(url=upload_url, headers=headers,
                                       files=[("file", (f.get('name'), file_stream, file_prop.get('mime_type')))],
                                       verify=False) as response:
                        if not response.ok:
                            logger.error(response.text)
                        response.raise_for_status()
                        file = {
                            "type": file_type or file_prop.get('category'),
                            "docId": response.json().get('fileId')
                        }
                        result.append(file)
                finally:
                    file_stream.close()
        return result

    def do_chat(self, params: ApiChatParams) -> Dict:
        params = params.load_config(self.model_names[0])
        role_meta = params.role_meta
        content = params.messages[-1].get('content')
        contentObj = json.loads(content)
        assistant_id = contentObj.get('assistant_id')
        assistant = None
        if assistant_id and assistant_id >= 0:
            assistant = get_assistant_simple_from_db(assistant_id)
        model_config = {}
        if assistant:
            model_config = assistant.get('model_config', {})
        url = model_config.get('api_proxy', params.api_proxy)
        api_key = model_config.get('api_key') or contentObj.get('api_key') or params.api_key
        stream = model_config.get('stream', contentObj.get('stream', True))
        is_workflow = True if 'workflow' in url else False
        is_completion = True if 'completion' in url else False
        timeout = model_config.get("timeout") or role_meta.get("timeout", 30)
        result_key = model_config.get('result_key') or role_meta.get("result_key")
        file_type = model_config.get('file_type') or role_meta.get("file_type")
        extra_headers = model_config.get("extra_headers") or role_meta.get("extra_headers", {})
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json", **extra_headers}
        inputs = self.get_inputs(role_meta, model_config)
        inputs['cookie'] = contentObj.get('cookie')
        inputs['token_info'] = json.dumps(get_token_info(contentObj.get('token')), ensure_ascii=False)
        conversation_id = contentObj.get('conversation_id')
        files = self.upload_files(url, api_key, contentObj, file_type, extra_headers)
        data = {
            "inputs": inputs,
            "query": contentObj.get('question', ''),
            "stream": stream,
            "conversationId": conversation_id,
            "files": files,
        }
        text = ""
        mark = f'###[{self.model_names[0]}]###'
        try:
            if not conversation_id and not is_workflow and not is_completion:
                conversation_create_url = self.replace_last_path_segment(url=url, new_segment="create")
                with requests.post(conversation_create_url, stream=False, headers=headers, timeout=timeout,
                                   json={"inputs": inputs}, verify=False) as response:
                    if response.status_code != 200:
                        logger.error(response.text)
                    response.raise_for_status()
                    conversation_id = response.text
                    data['conversationId'] = conversation_id
            logger.debug(f"请求fuxi接口参数：{data}")
            with requests.post(url, stream=stream, headers=headers, timeout=timeout, json=data,
                               verify=False) as response:
                if response.status_code != 200:
                    logger.error(response.text)
                response.raise_for_status()
                if is_workflow:
                    if result_key:
                        json_data = response.json()
                        yield {"error_code": 0, "text": json_data.get(result_key)}
                    else:
                        yield {"error_code": 0, "text": response.text}
                else:
                    if stream:
                        for chunk in response.iter_lines():
                            if chunk is None or len(chunk) == 0:
                                continue
                            if chunk.startswith(b'data:'):
                                json_str = chunk.decode('utf-8')[6:]
                                try:
                                    json_data = json.loads(json_str)
                                    if str(json_data.get('done')).lower() == 'true':
                                        break
                                    if json_data.get('type') == 'answer':
                                        msg = json_data.get('text', '')
                                        message_id = json_data.get('messageId')
                                        inner_json = json.dumps(
                                            {"conversation_id": conversation_id, "message_id": message_id,
                                             "answer": msg})
                                        text += mark + inner_json + mark
                                        yield {"error_code": 0, "text": text}
                                except json.JSONDecodeError:
                                    pass
                    else:
                        json_data = response.json()
                        conversation_id = json_data.get('conversationId')
                        message_id = json_data.get('messageId')
                        inner_json = json.dumps({"conversation_id": conversation_id, "message_id": message_id,
                                                 "answer": json_data.get('answer', '')})
                        yield {"error_code": 0, "text": mark + inner_json + mark}
        except Exception as e:
            logger.error(f"{e}")
            if text == '':
                model_label = (get_model_metadata_from_db(self.model_names[0]).get(self.model_names[0], {})
                               .get('label', 'fuxi-api'))
                yield {"error_code": 0, "text": f"调用{model_label}失败。"}

    def get_embeddings(self, params):
        print("get_embedding")
        print(params)

    def make_conv_template(self, conv_template: str = None, model_path: str = None) -> Conversation:
        return conv.Conversation(
            name=self.model_names[0],
            system_message="",
            messages=[],
            roles=["user", "assistant", "system"],
            sep="\n### ",
            stop_str="###",
        )

    def format_online_llm(self):
        return False
