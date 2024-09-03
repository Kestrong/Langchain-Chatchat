import json
import time
import uuid
from typing import List, Dict, Literal

import requests
from fastchat import conversation as conv
from fastchat.conversation import Conversation

from configs import logger
from server.db.repository import get_assistant_simple_from_db
from server.model_workers import ApiModelWorker, ApiChatParams


class LingxiFaultWorker(ApiModelWorker):

    def __init__(
            self,
            *,
            model_names: List[str] = ["lingxi-fault-api"],
            controller_addr: str = None,
            worker_addr: str = None,
            version: Literal["iotqwen-v1"] = "lingxi-fault-v1",
            **kwargs,
    ):
        kwargs.update(model_names=model_names, controller_addr=controller_addr, worker_addr=worker_addr)
        super().__init__(**kwargs)
        self.version = version

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
            role_meta.update(model_config)
        url = model_config.get('api_proxy', params.api_proxy)
        api_key = model_config.get('api_key', params.api_key)
        secret_key = model_config.get('secret_key', params.secret_key)
        timestamp = str(int(round(time.time() * 1000)))
        seqid = str(uuid.uuid1())
        headers = {"X-APP-ID": api_key, "X-APP-KEY": secret_key, "Content-Type": "application/json"}
        data = {"timestamp": timestamp, "seqid": seqid, "messages": [{"role": contentObj.get('question', '')}]}
        try:
            with requests.post(url, stream=False, headers=headers, timeout=role_meta.get("timeout", 30),
                               json=data) as response:
                response.raise_for_status()
                json_data = response.json()
                if "10000" == json_data.get("code"):
                    yield {"error_code": 0, "text": json_data.get("data", {}).get("output", "")}
                else:
                    yield {"error_code": 0, "text": json_data.get("messages")}
        except Exception as e:
            logger.error(f"{e}")
            yield {"error_code": 0, "text": "调用灵晞故障处置大模型失败。"}

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
