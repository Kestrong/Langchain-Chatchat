import io
import json
import re
import time
import uuid
from typing import List, Dict, Literal

import requests
from fastchat import conversation as conv
from fastchat.conversation import Conversation
from websocket._core import create_connection

from configs import logger
from server.db.repository import get_assistant_simple_from_db, get_model_metadata_from_db
from server.knowledge_base.oss import default_oss
from server.memory.token_info_memory import get_token_info
from server.model_workers import ApiModelWorker, ApiChatParams
from server.model_workers.dify import analyze_file, parse_inputs_expr
from server.utils import truncate_text


class QimingWorker(ApiModelWorker):

    def __init__(
            self,
            *,
            model_names: List[str] = ["qiming-api"],
            controller_addr: str = None,
            worker_addr: str = None,
            version: Literal["MaaS-Ws-v2"] = "MaaS-Ws-v2",
            **kwargs,
    ):
        kwargs.update(model_names=model_names, controller_addr=controller_addr, worker_addr=worker_addr)
        super().__init__(**kwargs)
        self.version = version

    def do_chat(self, params: ApiChatParams) -> Dict:
        params = params.load_config(self.model_names[0])
        content = params.messages[-1].get('content')
        contentObj = json.loads(content)
        assistant_id = contentObj.get('assistant_id')
        assistant = None
        if assistant_id and assistant_id >= 0:
            assistant = get_assistant_simple_from_db(assistant_id)
        model_config = {}
        if assistant:
            model_config = assistant.get('model_config') or {}
        uri = model_config.get('api_proxy', params.api_proxy)
        xappid = model_config.get('api_key') or params.api_key
        xappkey = model_config.get('secret_key') or params.secret_key
        version = model_config.get('version', params.version)
        if version == "workflow":
            yield from self.do_chat_workflow(uri=uri, params=params, model_config=model_config, contentObj=contentObj,
                                             xappid=xappid, xappkey=xappkey)
        else:
            yield from self.do_chat_common(uri=uri, params=params, model_config=model_config, contentObj=contentObj,
                                           xappid=xappid, xappkey=xappkey)

    def upload_files(self, url, app_id, user, contentObj, file_type, extra_headers):
        result, attachments = [], []
        knowledge_id = contentObj.get('knowledge_id')
        files = contentObj.get('files')
        if not knowledge_id and not files:
            logger.debug("knowledge_id和files都为空，不需要上传")
            return result, attachments
        headers = {}
        if 'X-APP-ID' in extra_headers:
            headers['X-APP-ID'] = extra_headers['X-APP-ID']
        if 'X-APP-KEY' in extra_headers:
            headers['X-APP-KEY'] = extra_headers['X-APP-KEY']
        data = {'user': user, 'app_id': app_id}
        match = re.search(r'https?://[^?]*?/rest(?=/|$)', url)
        upload_url = f"{match.group(0)}/wsc/upload" if match else url
        logger.debug(f"上传内部和第三方文件到dify, url={upload_url}, knowledge_id={knowledge_id}, files={files}")
        if knowledge_id:
            attachment_names = default_oss().list_objects(bucket_name="temp", object_name=knowledge_id)
            if attachment_names:
                for a in attachment_names:
                    logger.debug(f"upload file: {a}")
                    attachments.append({"filename": a, "knowledge_base_name": "temp", "path": knowledge_id})
                    with default_oss().get_object(bucket_name="temp", object_name=f"{knowledge_id}/{a}") as o:
                        file_prop = analyze_file(a)
                        data['type'] = file_prop.get('extension')
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
                    data['type'] = file_prop.get('extension')
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

    def do_chat_common(self, uri: str, params: ApiChatParams, model_config: dict, contentObj: dict, xappid: str,
                       xappkey: str):
        """
            ------   问答场景输入参数描述   ------
            1、规章制度:param1用户问题,param2预留字段不使用,scene固定值8;\n
            2、综维问答:param1用户问题,param2预留字段不使用,scene固定值2;\n
            3、无线网优:param1用户问题,param2知识库检索开关。“true”：启用知识库检索功能,“false”：关闭知识库检索功能,scene固定值3;\n
            4、装维问答:param1用户角色，可填写：装维一线、客支、客调、客服、客户,param2用户问题,scene固定值7;\n
            5、故障复盘:param1固定为1，代表事故复盘,param2用户问题,scene固定值6;\n
            6、传输故障处置:param1故障现象,param2故障描述,scene固定值1;\n
            7、运维助手：param1用户问题,param2细分场景标识符，可填写：变更操作管控bgczgk、故障诊断gzzd、安全漏洞修复aqldxf、故障自愈gzzy、运维规范问答ywgfwd、服务台/翼问赋能fwt，scene固定值9;\n
            8、天翼云知识助手：param1用户问题,param2固定statecolud,scene固定值13;\n
        """
        timestamp = str(int(round(time.time() * 1000)))
        seqid = str(uuid.uuid1())
        headers = {"X-APP-ID": xappid, "X-APP-KEY": xappkey}
        message = {
            "uid": xappid,
            "timestamp": timestamp,
            "seqid": seqid,
            "stream": "true",
            "prov": model_config.get('prov') or params.role_meta['prov'],
            "session_id": seqid,
            "param1": "",
            "param2": "",
            "param3": "",
            "param4": "",
            "param5": "",
            "param6": "",
            "scene": ""
        }
        websocket = None
        text = ''
        timeout = model_config.get("timeout") or params.role_meta.get("timeout", 30)
        stream = model_config.get('stream', contentObj.get('stream', True))
        try:
            conversation_id = contentObj.get('conversation_id')
            if conversation_id:
                message['session_id'] = conversation_id
            if contentObj.get('question', '').startswith('###') and contentObj.get('question', '').endswith('###'):
                parts = contentObj.get('question', '').split('###')
                message['scene'] = parts[1]
                message['param1'] = parts[2]
                message['param2'] = parts[3] if len(parts) > 3 else ""
            else:
                scene = contentObj.get('scene', '')
                message['scene'] = scene
                if scene in ['2', '8']:
                    message['param1'] = contentObj.get('question', '')
                elif scene == '3':
                    message['param1'] = contentObj.get('question', '')
                    message['param2'] = 'true'
                elif scene == '7':
                    message['param1'] = contentObj.get('role', '')
                    message['param2'] = contentObj.get('question', '')
                elif scene == '6':
                    message['param1'] = '1'
                    message['param2'] = contentObj.get('question', '')
                elif scene == '9':
                    message['param1'] = contentObj.get('question', '')
                    message['param2'] = contentObj.get('iTSubScene', contentObj.get('role', ''))
                elif scene == '13':
                    message['param1'] = contentObj.get('question', '')
                    message['param2'] = 'statecolud'
                else:
                    message['param1'] = contentObj.get('question', '')
                    message['param2'] = contentObj.get('description', '')
            websocket = create_connection(url=uri, header=headers, timeout=timeout)
            websocket.send(json.dumps(message))
            while True:
                response = websocket.recv()
                if response == "<#END>":
                    break
                text += response
                if stream:
                    yield {"error_code": 0, "text": text}
            if not stream:
                yield {"error_code": 0, "text": text}
        except Exception as e:
            logger.error(f"{e}")
            if text == '':
                yield {"error_code": 0, "text": "调用启明大模型失败或者启明大模型没有任何回复内容。"}
            else:
                if not stream:
                    yield {"error_code": 0, "text": text}
        finally:
            try:
                if websocket is not None:
                    websocket.close()
            except Exception:
                pass

    def do_chat_workflow(self, uri: str, params: ApiChatParams, model_config: dict, contentObj: dict, xappid: str,
                         xappkey: str):
        # 构建请求头
        headers = {
            "X-APP-ID": xappid,
            "X-APP-KEY": xappkey,
            "Content-Type": "application/json"
        }
        # 构建请求数据
        file_type = model_config.get('file_type') or params.role_meta.get("file_type")
        user = model_config.get('user') or params.role_meta.get("user")
        business_type = model_config.get("business_type") or params.role_meta.get('business_type', '')
        app_id = model_config.get("app_id") or params.role_meta.get('app_id', '')
        is_workflow = model_config.get('is_workflow') or params.role_meta.get('is_workflow', False)
        stream = False if is_workflow else True
        files, attachments = self.upload_files(uri, app_id or business_type, user, contentObj, file_type, headers)
        task_id = model_config.get('task_id') or params.role_meta.get('task_id')
        # 构建apiData
        if task_id:
            api_data = {
                "content": contentObj.get('question', ''),
                "frequency_penalty": 0,
                "max_tokens": params.max_tokens,
                "presence_penalty": 0,
                "taskId": task_id,
                "temperature": params.temperature,
                "top_p": params.top_p
            }
        else:
            query = contentObj.get('question', '')
            inputs = model_config.get('inputs') or params.role_meta.get("inputs", {})
            parse_inputs_expr(inputs, query, contentObj)
            inputs['cookie'] = contentObj.get('cookie')
            inputs['token_info'] = json.dumps(get_token_info(contentObj.get('token')), ensure_ascii=False)
            final_user = user or get_token_info(contentObj.get('token')).get('userId') or '1'
            api_data = {
                "files": files,
                "response_mode": "streaming" if stream else "blocking",  # Agent只能使用流式输出
                "user": str(final_user),
                "conversation_id": contentObj.get('conversation_id', ''),
                "opening_statement": model_config.get('opening_statement') or params.role_meta.get("opening_statement",
                                                                                                   {}),
                "suggested_questions": model_config.get('suggested_questions') or params.role_meta.get(
                    "suggested_questions", {}),
                "query": query,
                "inputs": inputs
            }
        # 构建完整请求数据
        data = {
            "businessType": business_type,
            "apiKey": "",
            "apiData": api_data
        }

        mark = f'###[{self.model_names[0]}]###'
        text = ''
        try:
            logger.debug(f"请求qiming-v2接口参数: {data}")
            timeout = model_config.get("timeout") or params.role_meta.get("timeout", 30)
            # 发送POST请求
            with requests.post(uri, headers=headers, json=data, stream=stream, timeout=timeout,
                               verify=False) as response:
                if response.status_code != 200:
                    logger.error(f"请求失败，状态码: {response.status_code}, 响应: {response.text}")
                    response.raise_for_status()
                if task_id:
                    choices = response.json().get('choices', [])
                    if choices:
                        text = choices[0].get('message', {}).get('content')
                        yield {"error_code": 0, "text": text}
                elif is_workflow:
                    if stream:
                        pass
                    else:
                        answer_key = model_config.get('output_key') or params.role_meta.get("output_key")
                        response_json = response.json()
                        logger.debug(f"qiming-v2接口返回数据: {response_json}")
                        response_data = response_json.get('data', {})
                        outputs = response_data.get('outputs') or {}
                        answer = ''
                        if answer_key and answer_key in outputs:
                            answer = outputs.get(answer_key, '')
                        else:
                            if len(outputs) == 1:
                                answer = list(outputs.values())[0]
                            elif len(outputs) > 1:
                                answer = json.dumps(outputs, ensure_ascii=False)
                        if not answer and response_data.get('error'):
                            text = response_data.get('error')
                            yield {"error_code": 0, "text": text}
                        else:
                            text = answer if answer is not None else ''
                            if not isinstance(text, str):
                                text = json.dumps(answer, ensure_ascii=False)
                            yield {"error_code": 0, "text": text}
                else:
                    if stream:
                        # 处理流式响应
                        for chunk in response.iter_lines():
                            logger.debug(f"接收到流式响应: {chunk}")
                            if chunk is None or len(chunk) == 0:
                                continue
                            if chunk.startswith(b'data:'):
                                json_str = chunk.decode('utf-8')[6:]
                                try:
                                    json_data = json.loads(json_str)
                                    event = json_data.get('event')
                                    # 根据事件类型处理响应
                                    if event == "agent_message" or event == "message":
                                        answer = json_data.get('answer', '')
                                        conversation_id = json_data.get('conversation_id')
                                        message_id = json_data.get('message_id')
                                        inner_json = json.dumps(
                                            {"conversation_id": conversation_id, "message_id": message_id,
                                             "answer": answer})
                                        text += mark + inner_json + mark
                                        yield {"error_code": 0, "text": text}
                                    elif event == "agent_thought":
                                        # 暂时不处理
                                        thought = json_data.get('thought', '')
                                    elif event == "message_end":
                                        # 结束消息
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
                                                grouped_docs[key]["page_content"].append(
                                                    truncate_text(r.get('content')))
                                            inner_json = json.dumps(
                                                {"conversation_id": conversation_id, "message_id": message_id,
                                                 "docs": docs})
                                            text += mark + inner_json + mark
                                            yield {"error_code": 0, "text": text}
                                        elif attachments:
                                            inner_json = json.dumps(
                                                {"conversation_id": conversation_id, "message_id": message_id,
                                                 "docs": attachments})
                                            text += mark + inner_json + mark
                                            yield {"error_code": 0, "text": text}
                                        break
                                except json.JSONDecodeError as e:
                                    logger.error(f"JSON解析错误: {e}")
        except Exception as e:
            logger.error(f"调用启明V2接口异常: {e}")
            if text == '':
                model_label = (get_model_metadata_from_db(self.model_names[0]).get(self.model_names[0], {})
                               .get('label', 'qiming-api'))
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
