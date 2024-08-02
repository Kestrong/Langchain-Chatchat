import sys
from typing import List, Literal, Dict

from fastchat import conversation as conv
from fastchat.conversation import Conversation
from openai import OpenAI

from configs import logger, log_verbose
from server.model_workers.base import *
from server.model_workers.base import ApiEmbeddingsParams


class QwenWorker(ApiModelWorker):
    DEFAULT_EMBED_MODEL = "text-embedding-v1"

    def __init__(
            self,
            *,
            version: Literal["qwen-turbo", "qwen-plus"] = "qwen-turbo",
            model_names: List[str] = ["qwen-api"],
            controller_addr: str = None,
            worker_addr: str = None,
            **kwargs,
    ):
        kwargs.update(model_names=model_names, controller_addr=controller_addr, worker_addr=worker_addr)
        kwargs.setdefault("context_len", 16384)
        super().__init__(**kwargs)
        self.version = version

    def do_chat(self, params: ApiChatParams) -> Dict:
        params.load_config(self.model_names[0])
        if log_verbose:
            logger.info(f'{self.__class__.__name__}:params: {params}')

        client = OpenAI(
            api_key=params.api_key,  # 如果您没有配置环境变量，请在此处用您的API Key进行替换
            base_url=params.api_base_url,  # 填写DashScope服务的base_url
        )
        try:
            with client.chat.completions.create(
                    model=params.version,
                    temperature=params.temperature,
                    messages=params.messages,
                    stream=True,
                    max_tokens=params.max_tokens,
                    top_p=params.top_p
            ) as responses:
                text = ''
                for resp in responses:
                    if resp.choices and resp.choices[0].delta and resp.choices[0].delta.content:
                        text += resp.choices[0].delta.content
                        yield {
                            "error_code": 0,
                            "text": text,
                        }
        except Exception as e:
            data = {
                "error_code": 500,
                "text": f'{e}'
            }
            self.logger.error(f"请求千问 API 时发生错误：{data}")
            yield data

    def do_embeddings(self, params: ApiEmbeddingsParams) -> Dict:
        params.load_config(self.model_names[0])
        if log_verbose:
            logger.info(f'{self.__class__.__name__}:params: {params}')
        client = OpenAI(
            api_key=params.api_key,  # 如果您没有配置环境变量，请在此处用您的API Key进行替换
            base_url=params.api_base_url,  # 填写DashScope服务的base_url
        )
        result = []
        i = 0
        while i < len(params.texts):
            texts = params.texts[i:i + 25]
            try:
                with client.embeddings.create(
                        model=params.embed_model or self.DEFAULT_EMBED_MODEL,
                        input=texts,  # 最大25行
                ) as resp:
                    embeddings = [x.embedding for x in resp.data]
                    result += embeddings
            except Exception as e:
                data = {
                    "error_code": 500,
                    "text": f'{e}'
                }
                self.logger.error(f"请求千问 API 时发生错误：{data}")
                return data
            i += 25
        return {"code": 200, "data": result}

    def get_embeddings(self, params):
        print("embedding")
        print(params)

    def make_conv_template(self, conv_template: str = None, model_path: str = None) -> Conversation:
        return conv.Conversation(
            name=self.model_names[0],
            system_message="你是一个聪明、对人类有帮助的人工智能，你可以对人类提出的问题给出有用、详细、礼貌的回答。",
            messages=[],
            roles=["user", "assistant", "system"],
            sep="\n### ",
            stop_str="###",
        )


if __name__ == "__main__":
    import uvicorn
    from server.utils import MakeFastAPIOffline
    from fastchat.serve.model_worker import app

    worker = QwenWorker(
        controller_addr="http://127.0.0.1:20001",
        worker_addr="http://127.0.0.1:20007",
    )
    sys.modules["fastchat.serve.model_worker"].worker = worker
    MakeFastAPIOffline(app)
    uvicorn.run(app, port=20007)
