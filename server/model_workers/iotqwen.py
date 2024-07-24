import json
from typing import List, Dict, Literal

import requests
from fastchat import conversation as conv
from fastchat.conversation import Conversation

from configs import logger
from server.db.repository import get_assistant_simple_from_db
from server.model_workers import ApiModelWorker, ApiChatParams


class IotQwenWorker(ApiModelWorker):

    def __init__(
            self,
            *,
            model_names: List[str] = ["iotqwen-api"],
            controller_addr: str = None,
            worker_addr: str = None,
            version: Literal["iotqwen-v1"] = "iotqwen-v1",
            **kwargs,
    ):
        kwargs.update(model_names=model_names, controller_addr=controller_addr, worker_addr=worker_addr)
        super().__init__(**kwargs)
        self.version = version

    def do_chat(self, params: ApiChatParams) -> Dict:
        params = params.load_config(self.model_names[0])
        role_meta = params.role_meta
        content = params.messages[-1].get('content')
        contentObj = json.loads(json.dumps(eval(content)))
        assistant_id = contentObj.get('assistant_id')
        assistant = None
        if assistant_id and assistant_id >= 0:
            assistant = get_assistant_simple_from_db(assistant_id)
        model_config = {}
        if assistant:
            model_config = assistant.get('model_config', {})
            role_meta.update(model_config)
        url = model_config.get('api_proxy', params.api_proxy)
        api_key = model_config.get('api_key', params.api_key)
        response_mode = contentObj.get('stream', True)
        headers = {"Authorization": f"Bearer {api_key}",
                   "Content-Type": "text/event-stream" if response_mode else "application/json"}
        inputs = {"userId": role_meta.get('user_id'), "kb_name": role_meta.get('kb_name'),
                  "topk": role_meta.get('topk'), "score_threshold": role_meta.get('score_threshold')}
        data = {
            "inputs": inputs,
            "query": contentObj.get('question', ''),
            "response_mode": "streaming" if response_mode else "blocking",
            "user": role_meta.get('user'),
            "conversation_id": contentObj.get('conversation_id'),
        }
        logger.debug(f"请求物联网大模型接口参数：{data}")
        text = ""
        mark = f'###[{self.model_names[0]}]###'
        with requests.post(url, stream=response_mode, headers=headers, timeout=30, json=data) as response:
            try:
                response.raise_for_status()
                if response_mode:
                    for chunk in response.iter_lines():
                        if chunk is None or len(chunk) == 0:
                            continue
                        if chunk.startswith(b'data:'):
                            json_str = chunk.decode('utf-8')[6:]
                            try:
                                json_data = json.loads(json_str)
                                if 'event' in json_data and json_data.get('event') == "workflow_finished":
                                    break
                                elif 'event' in json_data and json_data.get('event') == "text_chunk":
                                    msg = json_data.get('data', {}).get('text', '')
                                    text += msg
                                    yield {"error_code": 0, "text": text}
                                elif 'event' in json_data and json_data.get('event') == "message":
                                    conversation_id = json_data.get('conversation_id')
                                    msg = json_data.get('answer', '')
                                    inner_json = json.dumps({"conversation_id": conversation_id, "answer": msg})
                                    text += mark + inner_json + mark
                                    yield {"error_code": 0, "text": text}
                            except json.JSONDecodeError:
                                pass
                else:
                    json_data = response.json()
                    conversation_id = json_data.get('conversation_id')
                    inner_json = json.dumps({"conversation_id": conversation_id, "answer": json_data.get('answer', '')})
                    yield {"error_code": 0, "text": mark + inner_json + mark}
            except Exception as e:
                logger.error(f"{e}")
                if text == '':
                    yield {"error_code": 0, "text": "调用物联网大模型失败或者物联网大模型没有任何回复内容。"}

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
