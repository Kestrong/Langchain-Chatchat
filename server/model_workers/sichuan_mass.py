import hashlib
import json
import random
import threading
import time
from typing import List, Dict, Literal

import requests
from fastchat import conversation as conv
from fastchat.conversation import Conversation

from configs import logger
from server.db.repository import get_assistant_simple_from_db, get_model_metadata_from_db
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
        self.lock = threading.Lock()
        self.token = None
        self.token_expired_at = -1

    def get_token(self, url, systemKey, systemSecret, accComId, userCode, secret, timeout):
        if self.token and self.token_expired_at > time.time():
            return self.token
        with self.lock:
            if self.token and self.token_expired_at > time.time():
                return self.token
            nonce = random.randint(10000, 99999)
            timestamp = int(round(time.time() * 1000))
            md5 = hashlib.md5()
            md5.update((f"{systemKey}:{systemSecret}:{timestamp}:{nonce}" + "{" + secret + "}").encode())
            signature = md5.hexdigest()
            get_token_request = {
                "systemKey": systemKey,
                "systemSecret": systemSecret,
                "secret": secret,
                "timestamp": timestamp,
                "nonce": nonce,
                "signature": signature,
                "accComId": accComId,
                "userCode": userCode
            }
            headers = {
                "content-type": "application/json;charset=utf-8",
                "Accept": "application/json",
                "charset": "utf-8",
            }
            get_token_url = f'{url}/support/user/v1/getToken'
            logger.debug(f"getToken request: {get_token_request}, headers: {headers}")
            with requests.post(get_token_url, timeout=timeout, json=get_token_request, headers=headers,
                               verify=False) as response:
                if response.status_code != 200:
                    logger.error(response.text)
                response.raise_for_status()
                encoding = response.encoding
                if encoding is None:
                    encoding = requests.utils.get_encoding_from_headers(response.headers)
                if encoding is None:
                    encoding = "utf-8"
                resultStr = response.content.decode(encoding)
                response_data = json.loads(resultStr)
                token = response_data["resultObject"]["token"]
                self.token = token
                self.token_expired_at = time.time() + response_data["resultObject"]["expireTime"] - 600
                return self.token

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
        systemKey = model_config.get('systemKey') or role_meta.get("systemKey")
        systemSecret = model_config.get('systemSecret') or role_meta.get("systemSecret")
        accComId = model_config.get('accComId') or role_meta.get("accComId")
        userCode = model_config.get('userCode') or role_meta.get("userCode")
        secret = model_config.get('secret') or role_meta.get("secret")
        relAppId = model_config.get('relAppId') or role_meta.get("relAppId")
        stream = model_config.get('stream', contentObj.get('stream', True))
        timeout = model_config.get("timeout") or role_meta.get("timeout", 30)
        text = ''
        try:
            token = self.get_token(url, systemKey, systemSecret, accComId, userCode, secret, timeout)
            headers = {
                "content-type": "application/json;charset=utf-8",
                "Accept": "application/json",
                "charset": "utf-8",
                "systemKey": systemKey,
                "token": token,
            }
            chat_request = {
                "histories": [{"obj": a.get("role"), "value": a.get("content")} for a in params.messages[0:-1]],
                "chatContent": contentObj.get('question', '').replace('\n', ' '),
                "relAppId": relAppId,
                "stream": stream
            }
            logger.debug(f"chat request: {chat_request}, header: {headers}")
            chat_url = f'{url}/core/chat/openChat'
            response = None
            try:
                response = requests.post(chat_url, timeout=timeout, json=chat_request, headers=headers,
                                         stream=stream, verify=False)
                if response.status_code == 401 or response.status_code == 403:
                    logger.error(response.text)
                    with self.lock:
                        if self.token and token == self.token:
                            self.token = None
                            self.token_expired_at = -1
                    try:
                        response.close()
                    except Exception:
                        pass
                    headers['token'] = self.get_token(url, systemKey, systemSecret, accComId, userCode, secret, timeout)
                    response = requests.post(chat_url, timeout=timeout, json=chat_request, headers=headers,
                                             stream=stream, verify=False)
                if response.status_code != 200:
                    logger.error(response.text)
                response.raise_for_status()
                if stream:
                    event_type = None
                    for line in response.iter_lines():
                        logger.debug(f"chat response: {line}")
                        if not line:
                            continue
                        decoded_line = line.decode('utf-8')
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
                                    content = response_data["choices"][0]["delta"].get("content", "")
                                    if content:
                                        text += content
                                        yield {"error_code": 0, "text": text}
                            except json.JSONDecodeError:
                                pass
                else:
                    encoding = response.encoding
                    if encoding is None:
                        encoding = requests.utils.get_encoding_from_headers(response.headers)
                    if encoding is None:
                        encoding = "utf-8"
                    resultStr = response.content.decode(encoding)
                    response_data = json.loads(resultStr)
                    text = response_data["choices"][0]["message"]["content"]
                    yield {"error_code": 0, "text": text}
            finally:
                if response:
                    try:
                        response.close()
                    except Exception:
                        pass
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
