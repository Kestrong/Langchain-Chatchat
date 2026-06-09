import datetime
import json
from typing import List, Literal, Dict

import requests
from fastchat import conversation as conv
from fastchat.conversation import Conversation

from configs import logger, log_verbose
from server.db.repository import get_model_metadata_from_db, get_assistant_simple_from_db
from server.memory.message_i18n import Message_I18N
from server.model_workers.base import *


class FastgptWorker(ApiModelWorker):

    def __init__(
            self,
            *,
            version: Literal["fastgpt-v1"] = "fastgpt-v1",
            model_names: List[str] = ["fastgpt-api"],
            controller_addr: str = None,
            worker_addr: str = None,
            **kwargs,
    ):
        kwargs.update(model_names=model_names, controller_addr=controller_addr, worker_addr=worker_addr)
        super().__init__(**kwargs)
        self.version = version

    def do_chat(self, params: ApiChatParams) -> Dict:
        params.load_config(self.model_names[0])
        if log_verbose:
            logger.info(f'{self.__class__.__name__}:params: {params}')
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
        url = model_config.get('api_proxy', params.api_proxy)
        api_key = model_config.get('api_key', params.api_key)
        extra_headers = model_config.get("extra_headers") or role_meta.get("extra_headers", {})
        headers = {"Authorization": api_key, "Content-Type": "application/json", **extra_headers}
        variables = model_config.get("variables") or role_meta.get("variables", {})
        extra = model_config.get("extra") or role_meta.get("extra", {})
        app_id = model_config.get("appId") or role_meta.get("appId")
        with_quote = model_config.get("with_quote") or role_meta.get("with_quote", True)
        timeout = model_config.get("timeout") or role_meta.get("timeout", 30)
        if variables is None or len(variables) == 0:
            variables = {"cTime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %A")}
        data = {
            "messages": [{
                "dataId": contentObj.get('message_id'),
                "role": "user",
                "content": contentObj.get('question', '')
            }],
            "responseChatItemId": contentObj.get('message_id'),
            "variables": variables,
            "chatId": contentObj.get('conversation_id'),
            "detail": True,
            "stream": True
        }
        data.update(extra)
        text = ""
        mark = f'###[{self.model_names[0]}]###'
        try:
            with requests.post(url, stream=True, headers=headers, json=data, timeout=timeout, verify=False) as response:
                response.raise_for_status()
                done = False
                error = False
                for chunk in response.iter_lines():
                    if chunk is None or len(chunk) == 0:
                        continue
                    if chunk.startswith(b'event:'):
                        event = chunk.decode('utf-8')[6:].strip()
                        if "flowResponses" == event:
                            done = True
                        elif "error" == event:
                            error = True
                    elif chunk.startswith(b'data:'):
                        if error:
                            raise ValueError(chunk)
                        json_str = chunk.decode('utf-8')[6:]
                        if json_str == '[DONE]':
                            continue
                        try:
                            if done:
                                if with_quote:
                                    json_data = json.loads(json_str)
                                    sourceName = set()
                                    for m in json_data:
                                        if 'quoteList' in m:
                                            quoteList = m.get('quoteList')
                                            for q in quoteList:
                                                sourceName.add(f"[{q.get('sourceName')}]()")
                                    if len(sourceName) == 0:
                                        sourceName.add("无")
                                    text += (f'\n___\n**{Message_I18N.API_REFERENCE_NAME.value}：**\n'
                                             + "\n".join(sourceName))
                                    yield {"error_code": 0, "text": text}
                            else:
                                json_data = json.loads(json_str)
                                if 'choices' in json_data:
                                    choices = json_data.get('choices', [])
                                    msg = ''
                                    for choice in choices:
                                        msg += choice.get('delta', {}).get('content', '')
                                    if app_id:
                                        inner_json = json.dumps({"appId": app_id, "answer": msg})
                                        text += mark + inner_json + mark
                                    else:
                                        text += msg
                                    yield {"error_code": 0, "text": text}
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            logger.error(f"{e}")
            if text == '':
                model_label = (get_model_metadata_from_db(self.model_names[0]).get(self.model_names[0], {})
                               .get('label', 'fastgpt-api'))
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
