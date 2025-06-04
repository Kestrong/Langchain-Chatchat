import sys
from typing import List, Literal, Dict

import numpy as np
from fastchat import conversation as conv
from fastchat.conversation import Conversation, SeparatorStyle
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
        think_mark = params.role_meta.get('think_mark')
        if think_mark:
            params.messages[-1]['content'] = params.messages[-1]['content'] + think_mark
        with OpenAI(
                api_key=params.api_key,  # 如果您没有配置环境变量，请在此处用您的API Key进行替换
                base_url=params.api_proxy,  # 填写DashScope服务的base_url
                timeout=params.role_meta.get("timeout", 60),
        ) as client:
            try:
                with client.chat.completions.create(
                        model=params.version,
                        temperature=params.temperature,
                        messages=params.messages,
                        stream=True,
                        max_tokens=params.max_tokens,
                        top_p=params.top_p,
                        extra_body=params.role_meta.get("extra_body", {}),
                        extra_headers=params.role_meta.get("extra_headers", {}),
                ) as responses:
                    text = ''
                    mark = True
                    truncate_mark = params.role_meta.get('truncate_mark')
                    for resp in responses:
                        if resp.choices and resp.choices[0].delta and resp.choices[0].delta.content:
                            text += resp.choices[0].delta.content
                            if mark and truncate_mark:
                                if not text.endswith(truncate_mark):
                                    continue
                                else:
                                    text = ''
                                    mark = False
                            yield {
                                "error_code": 0,
                                "text": text,
                            }
            except Exception as e:
                data = {
                    "error_code": 500,
                    "text": f'{e}'
                }
                self.logger.error(f"请求 {self.model_names[0]} 时发生错误：{data}")
                yield data

    def split_string_by_length(self, s, length):
        return [s[i:i + length] for i in range(0, len(s), length)]

    def do_embeddings(self, params: ApiEmbeddingsParams) -> Dict:
        params.load_config(self.model_names[0])
        if log_verbose:
            logger.info(f'{self.__class__.__name__}:params: {params}')
        overlap_method = params.role_meta.get("overlap_method")
        max_length = params.role_meta.get("max_embedding_length", 512)
        with OpenAI(
                api_key=params.api_key,  # 如果您没有配置环境变量，请在此处用您的API Key进行替换
                base_url=params.api_proxy,  # 填写DashScope服务的base_url
                timeout=params.role_meta.get("timeout", 10),
        ) as client:
            try:
                result = []
                i = 0
                chunk_lens = {}
                chunk_index = {}
                while i < len(params.texts):
                    texts = params.texts[i:i + 25]
                    if overlap_method == "truncate":
                        texts = [x[:max_length] if len(x) > max_length else x for x in texts]
                    elif overlap_method == "chunk":
                        new_texts = []
                        for index, t in enumerate(texts, start=0):
                            if len(t) > max_length:
                                part_len = []
                                chunk_num = 0
                                for chunk in self.split_string_by_length(t, length=max_length):
                                    chunk_num += 1
                                    new_texts.append(chunk)
                                    part_len.append(len(chunk))
                                chunk_lens[len(new_texts) - chunk_num] = part_len
                                chunk_index[len(new_texts) - chunk_num] = chunk_num
                            else:
                                new_texts.append(t)
                        texts = new_texts

                    resp = client.embeddings.create(
                        model=params.embed_model or self.DEFAULT_EMBED_MODEL,
                        input=texts,  # 最大25行
                        extra_headers=params.role_meta.get("extra_headers", {}),
                    )
                    embeddings = [x.embedding for x in resp.data]
                    if overlap_method == "chunk" and len(chunk_index) > 0:
                        new_embeddings = []
                        start_index = 0
                        while start_index < len(embeddings):
                            if start_index not in chunk_index:
                                new_embeddings.append(embeddings[start_index])
                                start_index += 1
                            else:
                                chunk_embeddings = np.average(
                                    np.array(embeddings[start_index:start_index + chunk_index[start_index]]), axis=0,
                                    weights=chunk_lens[start_index])
                                chunk_embeddings = chunk_embeddings / np.linalg.norm(chunk_embeddings)
                                chunk_embeddings = chunk_embeddings.tolist()
                                new_embeddings.append(chunk_embeddings)
                                start_index += chunk_index[start_index]
                        embeddings = new_embeddings
                    chunk_index.clear()
                    chunk_lens.clear()
                    result += embeddings
                    i += 25
            except Exception as e:
                data = {
                    "error_code": 500,
                    "text": f'{e}'
                }
                self.logger.error(f"请求 {self.model_names[0]} 时发生错误：{data}")
                return data
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
            sep_style=SeparatorStyle.ADD_COLON_SINGLE,
            sep="<|im_end|>",
            stop_token_ids=[
                151643,
                151644,
                151645,
            ],  # "<|endoftext|>", "<|im_start|>", "<|im_end|>"
            stop_str="<|endoftext|>",
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
