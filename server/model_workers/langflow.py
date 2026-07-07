import json
from typing import List, Dict, Literal
from uuid import uuid4

import requests
from fastchat import conversation as conv
from fastchat.conversation import Conversation

from configs import logger
from server.db.repository import get_model_metadata_from_db, get_assistant_simple_from_db
from server.memory.token_info_memory import get_token_info
from server.model_workers import ApiModelWorker, ApiChatParams
from server.model_workers.dify import parse_inputs_expr


class LangflowWorker(ApiModelWorker):
    def __init__(
            self,
            *,
            model_names: List[str] = ["langflow-api"],
            controller_addr: str = None,
            worker_addr: str = None,
            version: Literal["langflow-v1"] = "langflow-v1",
            **kwargs,
    ):
        kwargs.update(model_names=model_names, controller_addr=controller_addr, worker_addr=worker_addr)
        super().__init__(**kwargs)
        self.version = version

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
            model_config = assistant.get('model_config', {})
            for k, v in (model_config.get('extra') or {}).items():
                if k not in contentObj:
                    contentObj[k] = v
        url = model_config.get('api_proxy', params.api_proxy)
        api_key = model_config.get('api_key') or contentObj.get('api_key') or params.api_key
        stream = model_config.get('stream', contentObj.get('stream'))
        flow_id = model_config.get('flow_id') or role_meta.get("flow_id")
        session_id = contentObj.get('conversation_id', uuid4())
        langflow_url = url.format(flow_id=flow_id)
        timeout = model_config.get("timeout") or role_meta.get("timeout", 30)
        extra_headers = model_config.get("extra_headers") or role_meta.get("extra_headers", {})
        headers = {
            "Content-Type": "application/json",
            "accept": "application/json",
            "x-api-key": api_key,
            **extra_headers
        }
        query = contentObj.get('question', '')
        inputs = model_config.get('inputs') or role_meta.get("inputs", {})
        cookie = contentObj.get('cookie')
        token_info = json.dumps(get_token_info(contentObj.get('token')), ensure_ascii=False)
        tweaks = contentObj.get('tweaks', inputs.get('tweaks', {}))
        parse_inputs_expr(tweaks, query, contentObj, assistant)

        data = {
            "input_value": query,
            "input_type": contentObj.get('input_type') or inputs.get('input_type', 'chat'),
            "output_type": contentObj.get('output_type') or inputs.get('output_type', 'chat'),
            "output_component": contentObj.get('output_component') or inputs.get('output_component', 'chat_output'),
            "session_id": session_id,
            "tweaks": tweaks
        }
        query_params = {"stream": str(stream).lower()}

        text = ""

        try:
            logger.debug(f"请求Langflow接口参数：{data}")
            logger.debug(f"请求Langflow URL: {url}")

            for key, value in tweaks.items():
                if isinstance(value, dict):
                    if 'cookie' in value and value.get('cookie') == "{cookie}":
                        value['cookie'] = cookie
                    if 'token_info' in value and value.get('token_info') == "{token_info}":
                        value['token_info'] = token_info

            with requests.post(langflow_url, headers=headers, params=query_params, json=data, stream=stream,
                               verify=False, timeout=timeout) as response:
                if response.status_code != 200:
                    logger.error(f"Langflow API请求失败: {response.status_code} - {response.text}")
                    response.raise_for_status()

                if stream:
                    # 流式响应处理
                    for chunk in response.iter_lines():
                        if chunk is None or len(chunk) == 0:
                            continue
                        if chunk.startswith(b'data:'):
                            json_str = chunk.decode('utf-8')[6:]  # 移除 "data: " 前缀
                            try:
                                json_data = json.loads(json_str)
                                event = json_data.get('event')

                                if event == "token":
                                    # 处理token事件
                                    token_text = json_data.get('data', {}).get('chunk', '')
                                    text += token_text
                                    yield {"error_code": 0, "text": text}
                                elif event == "end":
                                    break
                            except json.JSONDecodeError:
                                logger.warning(f"无法解析JSON: {json_str}")
                                continue
                else:
                    # 非流式响应处理
                    json_data = response.json()
                    outputs = json_data.get('outputs', [])
                    if outputs:
                        first_output = outputs[0]
                        output_results = first_output.get('outputs', [])
                        if output_results:
                            first_result = output_results[0]
                            results_message = first_result.get('results', {}).get('message', {})
                            answer_text = results_message.get('text', '')
                            text += answer_text
                            yield {"error_code": 0, "text": text}
                    else:
                        yield {"error_code": 0, "text": text}

        except Exception as e:
            logger.error(f"Langflow API调用出错: {e}")
            if text == '':
                model_label = (get_model_metadata_from_db(self.model_names[0]).get(self.model_names[0], {})
                               .get('label', 'langflow-api'))
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
