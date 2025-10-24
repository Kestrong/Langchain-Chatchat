import hashlib
import json
from typing import List, Dict, Literal

import requests
from fastchat import conversation as conv
from fastchat.conversation import Conversation

from configs import logger
from server.db.repository import get_assistant_simple_from_db, get_model_metadata_from_db
from server.memory.token_info_memory import get_token_info
from server.model_workers import ApiModelWorker, ApiChatParams


class SichuanMassWorker(ApiModelWorker):
    def __init__(
            self,
            *,
            model_names: List[str] = ["sichuanmass-api"],
            controller_addr: str = None,
            worker_addr: str = None,
            version: Literal["sichuanmass-v1"] = "sichuanmass-v1",
            **kwargs,
    ):
        kwargs.update(model_names=model_names, controller_addr=controller_addr, worker_addr=worker_addr)
        super().__init__(**kwargs)
        self.version = version

    def uuid_to_12id(self, uuid_str: str) -> str:
        # 大规模使用（>10 亿）时有显著碰撞风险
        uuid_str = uuid_str.strip().lower().replace('-', '')
        hash_bytes = hashlib.sha256(uuid_str.encode()).digest()
        num = int.from_bytes(hash_bytes, 'big')
        chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        s = ''
        for _ in range(12):
            s = chars[num % 62] + s
            num //= 62
        return s[-12:].zfill(12)

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
        api_proxy = model_config.get('api_proxy', params.api_proxy)
        api_key = model_config.get('api_key') or contentObj.get('api_key') or params.api_key
        stream = model_config.get('stream', contentObj.get('stream', True))
        multi_conv = model_config.get('multi_conv', role_meta.get('multi_conv', True))
        enable_thinking = model_config.get('enable_thinking', contentObj.get('enable_thinking', False))
        truncate_mark = model_config.get('truncate_mark') or role_meta.get('truncate_mark', '</think>')
        timeout = model_config.get("timeout") or role_meta.get("timeout", 30)
        refs = model_config.get('refs') or role_meta.get("refs", [])
        agentlink = model_config.get('agentlink') or role_meta.get("agentlink", {})
        agentlink['cookie'] = contentObj.get('cookie')
        agentlink['token_info'] = json.dumps(get_token_info(contentObj.get('token')), ensure_ascii=False)
        text = ''
        mark = f'###[{self.model_names[0]}]###'
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            conversation_id = contentObj.get('conversation_id')
            chat_request = {
                "chatId": self.uuid_to_12id(conversation_id) if multi_conv and conversation_id else None,
                "messages": [{"role": "user", "content": contentObj.get('question', '')}],
                "stream": stream,
                "refs": refs,
                "agentlink": agentlink
            }
            logger.debug(f"multi_conv: {multi_conv}, chat request: {chat_request}, header: {headers}")
            response = requests.post(api_proxy, timeout=timeout, json=chat_request, headers=headers,
                                     stream=stream, verify=False)
            if response.status_code != 200:
                logger.error(response.text)
            response.raise_for_status()
            if stream:
                event_type = None
                temp = ''
                flag = True
                for line in response.iter_lines():
                    logger.debug(f"chat response: {line}")
                    if not line:
                        continue
                    if isinstance(line, bytes):
                        decoded_line = line.decode('utf-8')
                    else:
                        decoded_line = line
                    if decoded_line.startswith('event:'):
                        event_type = decoded_line.split(":")[1].strip()
                    if event_type != 'answer':
                        continue
                    if decoded_line.startswith('data:'):
                        json_str = decoded_line[5:].strip()
                        if json_str == "[DONE]":
                            break
                        try:
                            response_data = json.loads(json_str)
                            if "choices" in response_data and len(response_data["choices"]) > 0:
                                try:
                                    reasoning_content = response_data["choices"][0]["delta"].get("reasoning_content")
                                except Exception:
                                    reasoning_content = None
                                if reasoning_content and enable_thinking:
                                    text += mark + json.dumps({'thought': reasoning_content}) + mark
                                    yield {"error_code": 0, "text": text}
                                content = response_data["choices"][0]["delta"].get("content")
                                if content:
                                    if flag and truncate_mark and enable_thinking:
                                        temp += content
                                        if truncate_mark not in temp:
                                            text += mark + json.dumps({'thought': content}) + mark
                                        else:
                                            truncate_index = content.find(truncate_mark)
                                            answer = text[truncate_index + len(truncate_mark):]
                                            thinking_content = text[:truncate_index + len(truncate_mark)]
                                            text += mark + json.dumps({'thought': thinking_content}) + mark + answer
                                            temp = ''
                                            flag = False
                                    else:
                                        text += content
                                    yield {
                                        "error_code": 0,
                                        "text": text,
                                    }
                        except json.JSONDecodeError:
                            pass
            else:
                response_data = response.json()
                content = response_data["choices"][0]["message"]["content"]
                if enable_thinking and truncate_mark in text:
                    truncate_index = text.find(truncate_mark)
                    answer = text[truncate_index + len(truncate_mark):]
                    thinking_content = text[:truncate_index + len(truncate_mark)]
                    text += mark + json.dumps({'thought': thinking_content}) + mark + answer
                else:
                    text = content
                yield {"error_code": 0, "text": text}
        except Exception as e:
            logger.error(f"{e}")
            if text == '':
                model_label = (get_model_metadata_from_db(self.model_names[0]).get(self.model_names[0], {})
                               .get('label', 'sichuanmass-api'))
                yield {"error_code": 0, "text": f"调用{model_label}失败。"}

    def get_embeddings(self, params):
        print("get_embedding")
        print(params)

    def make_conv_template(self, conv_template: str = None, model_path: str = None) -> Conversation:
        return conv.Conversation(
            name=self.model_names[0],
            system_message="",
            messages=[],
            roles=["Human", "AI", "system"],
            sep="\n### ",
            stop_str="###",
        )

    def format_online_llm(self):
        return False
