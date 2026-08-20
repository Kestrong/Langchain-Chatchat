import copy
import json
import logging
import re
from functools import reduce
from typing import List, Dict, Literal, Union

import requests
from fastchat import conversation as conv
from fastchat.conversation import Conversation
from langchain_core.prompts.string import DEFAULT_FORMATTER_MAPPING

from configs import logger
from server.db.repository import get_assistant_simple_from_db, get_model_metadata_from_db
from server.knowledge_base.oss import default_oss
from server.memory.message_i18n import Message_I18N
from server.model_workers import ApiModelWorker, ApiChatParams
from server.utils import truncate_text, get_mime_type, get_file_category


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


def parse_inputs_expr(inputs, query, contentObj, assistant):
    template_var = {'assistant': assistant, **contentObj}
    for k, v in inputs.items():
        if k in ['cookie', 'token_info']:
            continue
        if isinstance(v, str):
            matches = re.findall(r'\{\{(\s*[.\w-]+\s*)}}', v)
            for var_name in set(matches):
                placeholder = "{{" + var_name + "}}"
                if var_name.strip() == "query":
                    v = v.replace(placeholder, query)
                else:
                    try:
                        var_val = DEFAULT_FORMATTER_MAPPING["jinja2"](placeholder, **template_var)
                        if var_val:
                            v = v.replace(placeholder, var_val)
                    except:
                        pass
            inputs[k] = v

    for k in ['default_reply_text']:
        if k not in inputs and k in contentObj:
            inputs[k] = contentObj.get(k)

    if assistant:
        inputs['assistant_code'] = assistant.get('code')
        inputs['region_id'] = assistant.get('region_id')
        inputs['system_id'] = assistant.get('system_id')


def filter_sensitive_data(data: dict, target: str = "inputs") -> dict:
    """过滤敏感信息用于日志打印"""
    filtered_data = copy.deepcopy(data)

    inputs = reduce(lambda d, k: d.get(k, {}) if isinstance(d, dict) else {}, target.split("."), filtered_data)
    if inputs and isinstance(inputs, dict):
        for key in ["cookie", "token_info"]:
            if key in inputs and inputs[key]:
                inputs[key] = '***FILTERED***'

    return filtered_data


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

    def get_workflow_output(self, response_data: dict, answer_key: str = None):
        answer = ''
        outputs = response_data.get('outputs') or {}
        if answer_key and answer_key in outputs:
            answer = outputs.get(answer_key, '')
        else:
            if len(outputs) == 1:
                answer = list(outputs.values())[0]
            elif len(outputs) > 1:
                answer = json.dumps(outputs, ensure_ascii=False)
        if not answer and response_data.get('error'):
            answer = response_data.get('error')
        else:
            answer = answer if answer is not None else ''
        return answer

    def get_block_response(self, json_data, user, api_key):
        conversation_id = json_data.get('conversation_id')
        message_id = json_data.get('message_id')
        inner_json_obj = {"conversation_id": conversation_id, "message_id": message_id,
                          "user": user, "api_key": api_key, "answer": json_data.get('answer', '')}
        metadata = json_data.get('metadata') or {}
        usage = metadata.get('usage') or {}
        if usage:
            inner_json_obj['total_tokens'] = usage.get('total_tokens')
        retriever_resources = metadata.get('retriever_resources') or []
        if retriever_resources:
            grouped_docs = {}
            docs = []
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
        return inner_json_obj

    def get_chunk_response(self, json_data: dict, is_workflow: bool, answer_key: str,
                           token_event: list, user: Union[str, int], api_key: str, events: list, node_types: list):
        event = json_data.get('event')
        event_data = json_data.get('data', {})
        inner_json = {"user": user, "api_key": api_key}
        if event == "error":
            logger.error(f"Dify error: {json_data}")
            inner_json["answer"] = '服务暂不可用，请稍后重试。'
            return inner_json
        if event == "message_end":
            conversation_id = json_data.get('conversation_id')
            message_id = json_data.get('message_id')
            inner_json.update({"conversation_id": conversation_id, "message_id": message_id, })
            metadata = json_data.get('metadata') or {}
            usage = metadata.get('usage') or {}
            if usage and "workflow_finished" not in token_event:
                token_event.append(event)
                inner_json['final_total_tokens'] = usage.get('total_tokens')
            retriever_resources = metadata.get('retriever_resources') or []
            if retriever_resources:
                grouped_docs = {}
                docs = []
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
                inner_json["docs"] = docs
            return inner_json
        if event == "workflow_finished" and "message_end" not in token_event:
            token_event.append(event)
            inner_json["final_total_tokens"] = event_data.get('total_tokens')
            return inner_json
        if events and event not in events:
            return None
        if event == "node_finished" and event_data.get('node_type') in node_types:
            execution_metadata = event_data.get('execution_metadata', {})
            if is_workflow:
                msg = self.get_workflow_output(event_data, answer_key)
                inner_json["answer"] = msg
            else:
                conversation_id = json_data.get('conversation_id')
                message_id = json_data.get('message_id')
                outputs = event_data.get('outputs', {})
                if 'answer' in outputs:
                    msg = outputs.get('answer', '')
                else:
                    msg = outputs.get('text', '')
                inner_json.update({"answer": msg, 'conversation_id': conversation_id, 'message_id': message_id})
            if execution_metadata:
                inner_json['total_tokens'] = execution_metadata.get('total_tokens')
            return inner_json
        elif event == "text_chunk":
            inner_json["answer"] = event_data.get('text', '')
            return inner_json
        elif event == "message" or event == "agent_message" or event == "agent_thought":
            inner_json["conversation_id"] = json_data.get('conversation_id')
            inner_json["message_id"] = json_data.get('message_id')
            if event == "agent_thought":
                thought = json_data.get('thought', '')
                observation = json_data.get('observation', '')
                if observation:
                    tool = json_data.get("tool")
                    tool_input = json_data.get("tool_input")
                    inner_json["thought"] = Message_I18N.API_AGENT_TOOL_SUCCESS_INFO.value.format(
                        tool_name=tool, input_str=tool_input, output_str=observation)
                else:
                    inner_json["thought"] = thought
                inner_json["answer"] = ""
            else:
                msg = json_data.get('answer', '')
                inner_json['answer'] = msg
            return inner_json
        elif event == "tts_message":
            inner_json["answer"] = json_data.get('audio', '')
            return inner_json
        else:
            return None

    def upload_files(self, url, api_key, user, contentObj, file_type, extra_headers):
        result = []
        chat_files = contentObj.get('chat_files')
        if not chat_files:
            logger.debug("chat_files为空，不需要上传")
            return result
        headers = {'Authorization': f'Bearer {api_key}'}
        if 'X-APP-ID' in extra_headers:
            headers['X-APP-ID'] = extra_headers['X-APP-ID']
        if 'X-APP-KEY' in extra_headers:
            headers['X-APP-KEY'] = extra_headers['X-APP-KEY']
        data = {'user': user}
        match = re.search(r'https?://[^?]*?/v1(?=/|$)', url)
        upload_url = f"{match.group(0)}/files/upload" if match else url
        logger.debug(f"上传内部和第三方文件到dify, url={upload_url}, chat_files={chat_files}")
        for a in chat_files:
            logger.debug(f"upload file: {a}")
            with default_oss().get_object(bucket_name=a.get('knowledge_base_name'),
                                          object_name=f"{a.get('path')}/{a.get('filename')}") as o:
                file_prop = analyze_file(a.get('filename'))
                with requests.post(url=upload_url, headers=headers, data=data,
                                   files=[("file", (a.get('filename'), o, file_prop.get('mime_type')))],
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
        return result

    def do_chat(self, params: ApiChatParams) -> Dict:
        params = params.load_config(self.model_names[0])
        role_meta = params.role_meta
        content = params.messages[-1].get('content')
        contentObj = params.extra or {}
        contentObj['question'] = content
        assistant_id = contentObj.get('assistant_id')
        assistant = None
        if assistant_id and assistant_id >= 0:
            assistant = get_assistant_simple_from_db(assistant_id)
        model_config = {}
        if assistant:
            model_config = assistant.get('model_config') or {}
            for k, v in (model_config.get('extra') or {}).items():
                if k not in contentObj:
                    contentObj[k] = v
        url = model_config.get('api_proxy', params.api_proxy)
        api_key = model_config.get('api_key') or contentObj.get('api_key') or params.api_key
        is_workflow = model_config.get('is_workflow') or role_meta.get('is_workflow', False)
        answer_key = model_config.get('output_key') or params.role_meta.get("output_key")
        response_mode = model_config.get('stream', contentObj.get('stream', True))
        events = model_config.get('events', role_meta.get('events', []))
        node_types = model_config.get('node_types', role_meta.get('node_types', []))
        user = model_config.get('user') or role_meta.get("user")
        timeout = model_config.get("timeout") or role_meta.get("timeout", 30)
        file_type = model_config.get('file_type') or role_meta.get("file_type")
        extra_headers = model_config.get("extra_headers") or role_meta.get("extra_headers", {})
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", **extra_headers}
        query = contentObj.get('question', '')
        inputs = self.get_inputs(role_meta, model_config)
        token_info = contentObj.get('token_info')
        parse_inputs_expr(inputs, query, contentObj, assistant)
        inputs['cookie'] = contentObj.get('cookie')
        inputs['token_info'] = json.dumps(token_info, ensure_ascii=False)
        final_user = user or token_info.get('userId') or '1'
        data = {
            "inputs": inputs,
            "query": query,
            "response_mode": "streaming" if response_mode else "blocking",
            "user": str(final_user),
            "conversation_id": contentObj.get('conversation_id'),
        }
        text = ""
        mark = f'###[{self.model_names[0]}]###'
        try:
            files = self.upload_files(url, api_key, user, contentObj, file_type, extra_headers)
            data['files'] = files
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"请求dify接口参数：{filter_sensitive_data(data)}")
            data.update({"input_data": inputs, "mode": data.get('response_mode')})
            with requests.post(url, stream=response_mode, headers=headers, timeout=timeout, json=data,
                               verify=False) as response:
                if response.status_code != 200:
                    logger.error(response.text)
                response.raise_for_status()
                if response_mode:
                    token_events = []
                    for chunk in response.iter_lines():
                        if chunk is None or len(chunk) == 0:
                            continue
                        chunk = chunk.decode('utf-8')
                        logger.debug(f"接收到流式响应: {chunk}")
                        if chunk.startswith('data:'):
                            json_str = chunk[6:].strip()
                            try:
                                if json_str == '[DONE]':
                                    continue
                                json_data = json.loads(json_str)
                                result = self.get_chunk_response(json_data, is_workflow, answer_key, token_events,
                                                                 final_user, api_key, events, node_types)
                                if not result:
                                    continue
                                text += mark + json.dumps(result) + mark
                                yield {"error_code": 0, "text": text}
                            except json.JSONDecodeError:
                                pass
                else:
                    json_data = response.json()
                    logger.debug(f"dify接口返回数据: {json_data}")
                    if is_workflow:
                        response_data = json_data.get('data', {})
                        answer = self.get_workflow_output(response_data=response_data, answer_key=answer_key)
                        inner_json_obj = {"user": final_user, "api_key": api_key, "answer": answer,
                                          "total_tokens": response_data.get('total_tokens')}
                        yield {"error_code": 0, "text": mark + json.dumps(inner_json_obj) + mark}
                    else:
                        inner_json_obj = self.get_block_response(json_data, final_user, api_key)
                        yield {"error_code": 0, "text": mark + json.dumps(inner_json_obj) + mark}
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
