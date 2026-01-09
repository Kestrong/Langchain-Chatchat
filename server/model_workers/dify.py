import io
import json
import re
from typing import List, Dict, Literal

import requests
from fastchat import conversation as conv
from fastchat.conversation import Conversation
from langchain_core.prompts.string import DEFAULT_FORMATTER_MAPPING

from configs import logger
from server.db.repository import get_assistant_simple_from_db, get_model_metadata_from_db
from server.knowledge_base.oss import default_oss
from server.memory.token_info_memory import get_token_info
from server.model_workers import ApiModelWorker, ApiChatParams
from server.utils import truncate_text

# 自定义 MIME 类型和文件类别映射
MIME_TYPE_MAP = {
    # 文档类
    'txt': 'text/plain',
    'md': 'text/markdown',
    'markdown': 'text/markdown',
    'pdf': 'application/pdf',
    'html': 'text/html',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'xls': 'application/vnd.ms-excel',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'doc': 'application/msword',
    'csv': 'text/csv',
    'eml': 'message/rfc822',
    'msg': 'application/vnd.ms-outlook',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'ppt': 'application/vnd.ms-powerpoint',
    'xml': 'application/xml',
    'epub': 'application/epub+zip',

    # 图像类
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif',
    'webp': 'image/webp',
    'svg': 'image/svg+xml',

    # 音频类
    'mp3': 'audio/mpeg',
    'm4a': 'audio/x-m4a',
    'wav': 'audio/wav',
    'webm': 'audio/webm',
    'amr': 'audio/amr',

    # 视频类
    'mp4': 'video/mp4',
    'mov': 'video/quicktime',
    'mpeg': 'video/mpeg',
    'mpga': 'audio/mpeg',  # 注意：MPGA 有时是音频

    # 其他通用类型
    'bin': 'application/octet-stream',
    'unknown': 'application/octet-stream'
}

# 文件分类规则
FILE_CATEGORY_MAP = {
    'document': ['txt', 'md', 'markdown', 'pdf', 'html', 'xlsx', 'xls', 'docx', 'doc', 'csv', 'eml', 'msg', 'pptx',
                 'ppt', 'xml', 'epub'],
    'image': ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'],
    'audio': ['mp3', 'm4a', 'wav', 'webm', 'amr'],
    'video': ['mp4', 'mov', 'mpeg', 'mpga']
}


def get_file_category(ext):
    ext_lower = ext.lower()
    for category, extensions in FILE_CATEGORY_MAP.items():
        if ext_lower in extensions:
            return category
    return 'custom'


def analyze_file(filename):
    # 获取扩展名
    if '.' not in filename:
        ext = ''
    else:
        ext = filename.rsplit('.', 1)[-1].strip().lower()

    mime = get_mime_type(ext)
    category = get_file_category(ext)

    return {
        'filename': filename,
        'extension': ext or '(无扩展名)',
        'category': category,
        'mime_type': mime
    }


def get_mime_type(ext):
    ext_lower = ext.lower()
    return MIME_TYPE_MAP.get(ext_lower, MIME_TYPE_MAP['unknown'])


class DifyWorker(ApiModelWorker):

    def __init__(
            self,
            *,
            model_names: List[str] = ["dify-api"],
            controller_addr: str = None,
            worker_addr: str = None,
            version: Literal["dify-v1"] = "dify-v1",
            **kwargs,
    ):
        kwargs.update(model_names=model_names, controller_addr=controller_addr, worker_addr=worker_addr)
        super().__init__(**kwargs)
        self.version = version

    def get_inputs(self, role_meta: dict, model_config: dict):
        return model_config.get('inputs') or role_meta.get("inputs", {})

    def get_chunk_response(self, json_data, is_workflow, mark, user, api_key, events, node_types, attachments):
        event = json_data.get('event')
        if is_workflow:
            if event == "workflow_finished":
                return mark + '[BREAK]' + mark
            elif event == "tts_message":
                return json_data.get('audio', '')
            elif event == "node_finished":
                obj = {"answer": json_data.get('data', {}).get('outputs')}
                if attachments:
                    obj["docs"] = attachments
                return mark + json.dumps(obj) + mark
            else:
                return None
        else:
            if event == "workflow_finished":
                return mark + '[BREAK]' + mark
            if events and event not in events:
                return None
            event_data = json_data.get('data', {})
            if event == "node_finished" and event_data.get('node_type') in node_types:
                conversation_id = json_data.get('conversation_id')
                message_id = json_data.get('message_id')
                outputs = event_data.get('outputs', {})
                if 'answer' in outputs:
                    msg = outputs.get('answer', '')
                else:
                    msg = outputs.get('text', '')
                inner_json = json.dumps(
                    {"conversation_id": conversation_id, "message_id": message_id,
                     "user": user, "api_key": api_key, "answer": msg})
                return mark + inner_json + mark
            elif event == "text_chunk":
                msg = event_data.get('text', '')
                return msg
            elif event == "message" or event == "agent_message":
                conversation_id = json_data.get('conversation_id')
                message_id = json_data.get('message_id')
                msg = json_data.get('answer', '')
                inner_json = json.dumps(
                    {"conversation_id": conversation_id, "message_id": message_id,
                     "user": user, "api_key": api_key, "answer": msg})
                return mark + inner_json + mark
            elif event == "message_end":
                conversation_id = json_data.get('conversation_id')
                message_id = json_data.get('message_id')
                metadata = json_data.get('metadata') or {}
                retriever_resources = metadata.get('retriever_resources') or []
                if retriever_resources:
                    grouped_docs = {}
                    docs = [a for a in attachments]
                    for r in retriever_resources:
                        key = f"{r.get('dataset_name')}:{r.get('document_name')}"
                        if key not in grouped_docs:
                            grouped_docs[key] = {
                                "filename": r.get('document_name'),
                                "knowledge_base_name": r.get('dataset_name'),
                                "page_content": []
                            }
                            docs.append(grouped_docs[key])
                        grouped_docs[key]["page_content"].append(truncate_text(r.get('content')))
                    inner_json = json.dumps(
                        {"conversation_id": conversation_id, "message_id": message_id,
                         "user": user, "api_key": api_key, "docs": docs})
                    return mark + inner_json + mark
                elif attachments:
                    inner_json = json.dumps(
                        {"conversation_id": conversation_id, "message_id": message_id,
                         "user": user, "api_key": api_key, "docs": attachments})
                    return mark + inner_json + mark
                return None
            elif event == "tts_message":
                return json_data.get('audio', '')
            elif event == "error":
                return json_data.get('message', '')
            else:
                return None

    def upload_files(self, url, api_key, user, contentObj, file_type, extra_headers):
        result, attachments = [], []
        knowledge_id = contentObj.get('knowledge_id')
        files = contentObj.get('files')
        if not knowledge_id and not files:
            logger.debug("knowledge_id和files都为空，不需要上传")
            return result, attachments
        headers = {'Authorization': f'Bearer {api_key}'}
        if 'X-APP-ID' in extra_headers:
            headers['X-APP-ID'] = extra_headers['X-APP-ID']
        if 'X-APP-KEY' in extra_headers:
            headers['X-APP-KEY'] = extra_headers['X-APP-KEY']
        data = {'user': user}
        match = re.search(r'https?://[^?]*?/v1(?=/|$)', url)
        upload_url = f"{match.group(0)}/files/upload" if match else url
        logger.debug(f"上传内部和第三方文件到dify, url={upload_url}, knowledge_id={knowledge_id}, files={files}")
        if knowledge_id:
            attachment_names = default_oss().list_objects(bucket_name="temp", object_name=knowledge_id)
            if attachment_names:
                for a in attachment_names:
                    logger.debug(f"upload file: {a}")
                    attachments.append({"filename": a, "knowledge_base_name": "temp", "path": knowledge_id})
                    with default_oss().get_object(bucket_name="temp", object_name=f"{knowledge_id}/{a}") as o:
                        file_prop = analyze_file(a)
                        with requests.post(url=upload_url, headers=headers, data=data,
                                           files=[("file", (a, o, file_prop.get('mime_type')))],
                                           verify=False) as response:
                            if not response.ok:
                                logger.error(response.text)
                            response.raise_for_status()
                            file = {
                                "type": file_type or file_prop.get('category'),
                                "transfer_method": "local_file",
                                "url": "",
                                "upload_file_id": response.json().get('id')
                            }
                            result.append(file)
        if files:
            cookies = contentObj.get('cookies')
            get_file_headers = None
            if contentObj.get('token'):
                get_file_headers = {"Authorization": contentObj.get('token')}
            for f in files:
                logger.debug(f"upload file: {f.get('name')}")
                attachments.append({"filename": f.get('name'), "url": f.get('url')})
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
                    with requests.post(url=upload_url, headers=headers, data=data,
                                       files=[("file", (f.get('name'), file_stream, file_prop.get('mime_type')))],
                                       verify=False) as response:
                        if not response.ok:
                            logger.error(response.text)
                        response.raise_for_status()
                        file = {
                            "type": file_type or file_prop.get('category'),
                            "transfer_method": "local_file",
                            "url": "",
                            "upload_file_id": response.json().get('id')
                        }
                        result.append(file)
                finally:
                    file_stream.close()
        return result, attachments

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
            model_config = assistant.get('model_config') or {}
        url = model_config.get('api_proxy', params.api_proxy)
        api_key = model_config.get('api_key') or contentObj.get('api_key') or params.api_key
        response_mode = model_config.get('stream', contentObj.get('stream', True))
        is_workflow = model_config.get('is_workflow') or role_meta.get('is_workflow', False)
        events = model_config.get('events', role_meta.get('events', []))
        node_types = model_config.get('node_types', role_meta.get('node_types', []))
        user = model_config.get('user') or role_meta.get("user")
        timeout = model_config.get("timeout") or role_meta.get("timeout", 30)
        file_type = model_config.get('file_type') or role_meta.get("file_type")
        extra_headers = model_config.get("extra_headers") or role_meta.get("extra_headers", {})
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", **extra_headers}
        inputs = self.get_inputs(role_meta, model_config)
        inputs['cookie'] = contentObj.get('cookie')
        inputs['token_info'] = json.dumps(get_token_info(contentObj.get('token')), ensure_ascii=False)
        query = contentObj.get('question', '')
        for k, v in inputs.items():
            if isinstance(v, str):
                matches = re.findall(r'\{\{(\s*[.\w-]+\s*)}}', v)
                for var_name in set(matches):
                    placeholder = "{{" + var_name + "}}"
                    if var_name.strip() == "query":
                        v = v.replace(placeholder, query)
                    else:
                        try:
                            var_val = DEFAULT_FORMATTER_MAPPING["jinja2"](placeholder, **contentObj)
                            if var_val:
                                v = v.replace(placeholder, var_val)
                        except:
                            pass
                inputs[k] = v
        data = {
            "inputs": inputs,
            "query": query,
            "response_mode": "streaming" if response_mode else "blocking",
            "user": user,
            "conversation_id": contentObj.get('conversation_id'),
        }
        text = ""
        mark = f'###[{self.model_names[0]}]###'
        try:
            files, attachments = self.upload_files(url, api_key, user, contentObj, file_type, extra_headers)
            data['files'] = files
            logger.debug(f"请求dify接口参数：{data}")
            data.update({"input_data": inputs, "mode": data.get('response_mode')})
            with requests.post(url, stream=response_mode, headers=headers, timeout=timeout, json=data,
                               verify=False) as response:
                if response.status_code != 200:
                    logger.error(response.text)
                response.raise_for_status()
                if response_mode:
                    for chunk in response.iter_lines():
                        if chunk is None or len(chunk) == 0:
                            continue
                        if chunk.startswith(b'data:'):
                            json_str = chunk.decode('utf-8')[6:]
                            try:
                                json_data = json.loads(json_str)
                                result = self.get_chunk_response(json_data, is_workflow, mark, data.get('user'),
                                                                 api_key, events, node_types, attachments)
                                if not result:
                                    continue
                                if result == mark + '[BREAK]' + mark:
                                    break
                                text += result
                                yield {"error_code": 0, "text": text}
                            except json.JSONDecodeError:
                                pass
                else:
                    json_data = response.json()
                    if is_workflow:
                        inner_json_obj = {"answer": json_data.get('data', {}).get('outputs')}
                        if attachments:
                            inner_json_obj['docs'] = attachments
                        inner_json = json.dumps(inner_json_obj)
                        yield {"error_code": 0, "text": mark + inner_json + mark}
                    else:
                        conversation_id = json_data.get('conversation_id')
                        message_id = json_data.get('message_id')
                        inner_json_obj = {"conversation_id": conversation_id, "message_id": message_id,
                                          "user": data.get('user'), "api_key": api_key,
                                          "answer": json_data.get('answer', '')}
                        metadata = json_data.get('metadata') or {}
                        retriever_resources = metadata.get('retriever_resources') or []
                        if retriever_resources:
                            grouped_docs = {}
                            docs = [a for a in attachments]
                            for r in retriever_resources:
                                key = f"{r.get('dataset_name')}:{r.get('document_name')}"
                                if key not in grouped_docs:
                                    grouped_docs[key] = {
                                        "filename": r.get('document_name'),
                                        "knowledge_base_name": r.get('dataset_name'),
                                        "page_content": []
                                    }
                                    docs.append(grouped_docs[key])
                                grouped_docs[key]["page_content"].append(truncate_text(r.get('content')))
                            inner_json_obj['docs'] = docs
                        elif attachments:
                            inner_json_obj['docs'] = attachments
                        inner_json = json.dumps(inner_json_obj)
                        yield {"error_code": 0, "text": mark + inner_json + mark}
        except Exception as e:
            logger.error(f"{e}")
            if text == '':
                model_label = (get_model_metadata_from_db(self.model_names[0]).get(self.model_names[0], {})
                               .get('label', 'dify-api'))
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