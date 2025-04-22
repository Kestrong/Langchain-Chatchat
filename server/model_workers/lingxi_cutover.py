import json
from typing import List, Dict, Literal

import requests
from fastchat import conversation as conv
from fastchat.conversation import Conversation

from configs import logger
from server.db.repository import get_assistant_simple_from_db, get_model_metadata_from_db
from server.model_workers import ApiModelWorker, ApiChatParams


class LingxiCutOverWorker(ApiModelWorker):

    def __init__(
            self,
            *,
            model_names: List[str] = ["lingxi-cutover-api"],
            controller_addr: str = None,
            worker_addr: str = None,
            version: Literal["iotqwen-v1"] = "lingxi-cutover-v1",
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
        url = model_config.get('api_proxy', params.api_proxy)
        headers = {"x-access-token": contentObj.get('token')}
        data = {
            "attachmentUrl": "string",
            "endTime": 0,
            "operatorList": [],
            "question": "string",
            "reviewerList": [],
            "scene": "string",
            "startTime": 0,
            "deviceList": [],
            "testLeaderList": [],
            "supporterList": []
        }
        for k in data.keys():
            if k in contentObj:
                data[k] = contentObj[k]
        try:
            timeout = model_config.get('timeout') or role_meta.get("timeout", 30)
            with requests.post(url, stream=False, headers=headers, timeout=timeout, json=data) as response:
                if response.status_code != 200:
                    logger.error(response.text)
                    response.raise_for_status()
                json_data = response.json()
                if "200" == str(json_data.get("code")):
                    files = json_data.get("result", {}).get("files", [])
                    text = "\n".join([f"[{f.get('fileName')}]({f.get('downloadUrl')})" for f in files])
                    yield {"error_code": 0, "text": text}
                else:
                    yield {"error_code": 0, "text": json_data.get("message")}
        except Exception as e:
            logger.error(f"{e}")
            model_label = (get_model_metadata_from_db(self.model_names[0]).get(self.model_names[0], {})
                           .get('label', '灵晞割接方案大模型'))
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
