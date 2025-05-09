import json
from typing import List, Dict, Literal

import requests
from fastchat import conversation as conv
from fastchat.conversation import Conversation

from configs import logger
from server.db.repository import get_assistant_simple_from_db, get_model_metadata_from_db
from server.model_workers import ApiModelWorker, ApiChatParams


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

    def get_chunk_response(self, json_data, is_workflow, mark, user, api_key, events, node_types):
        event = json_data.get('event')
        if is_workflow:
            if event == "workflow_finished":
                return mark + '[BREAK]' + mark
            elif event == "tts_message":
                return json_data.get('audio', '')
            elif event == "node_finished":
                return mark + json.dumps({"answer": json_data.get('data', {}).get('outputs')}) + mark
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
            elif event == "tts_message":
                return json_data.get('audio', '')
            elif event == "error":
                return json_data.get('message', '')
            else:
                return None

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
        response_mode = model_config.get('stream', contentObj.get('stream', True))
        is_workflow = model_config.get('is_workflow') or role_meta.get('is_workflow', False)
        events = model_config.get('events') or role_meta.get('events', [])
        node_types = model_config.get('node_types') or role_meta.get('node_types', [])
        user = model_config.get('user') or role_meta.get("user")
        timeout = model_config.get("timeout") or role_meta.get("timeout", 30)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        inputs = self.get_inputs(role_meta, model_config)
        data = {
            "inputs": inputs,
            "query": contentObj.get('question', ''),
            "response_mode": "streaming" if response_mode else "blocking",
            "user": user,
            "conversation_id": contentObj.get('conversation_id'),
        }
        logger.debug(f"请求dify接口参数：{data}")
        text = ""
        mark = f'###[{self.model_names[0]}]###'
        try:
            with requests.post(url, stream=response_mode, headers=headers, timeout=timeout, json=data) as response:
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
                                                                 api_key, events, node_types)
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
                        inner_json = json.dumps({"answer": json_data.get('data', {}).get('outputs')})
                        yield {"error_code": 0, "text": mark + inner_json + mark}
                    else:
                        conversation_id = json_data.get('conversation_id')
                        message_id = json_data.get('message_id')
                        inner_json = json.dumps({"conversation_id": conversation_id, "message_id": message_id,
                                                 "user": data.get('user'), "api_key": api_key,
                                                 "answer": json_data.get('answer', '')})
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


class IotQwenWorker(DifyWorker):
    def get_inputs(self, role_meta: dict, model_config: dict):
        user_id = model_config.get('user_id') or role_meta.get('user_id')
        kb_name = model_config.get('kb_name') or role_meta.get('kb_name')
        topk = model_config.get('topk') or role_meta.get('topk')
        score_threshold = model_config.get('score_threshold') or role_meta.get('score_threshold')
        return {"userId": user_id, "kb_name": kb_name,
                "topk": topk, "score_threshold": score_threshold}
