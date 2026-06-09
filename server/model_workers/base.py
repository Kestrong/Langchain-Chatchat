import fastchat.constants
from fastchat.conversation import Conversation

from configs import LOG_PATH, TEMPERATURE, MAX_TOKENS_INPUT
from server.chat.utils import un_format_online_llm_model, calculate_token_len, get_tiktoken_num

fastchat.constants.LOGDIR = LOG_PATH
from fastchat.serve.base_model_worker import BaseModelWorker
import uuid
import json
from pydantic import BaseModel, root_validator
import asyncio
from server.utils import get_model_worker_config
from typing import Dict, List, Optional, Union, Any

__all__ = ["ApiModelWorker", "ApiModelParams", "ApiChatParams", "ApiCompletionParams", "ApiChatWithFeedbackParams",
           "ApiEmbeddingsParams"]


class ApiConfigParams(BaseModel):
    '''
    在线API配置参数，未提供的值会自动从model_config.ONLINE_LLM_MODEL中读取
    '''
    api_base_url: Optional[str] = None
    api_proxy: Optional[str] = None
    api_key: Optional[str] = None
    secret_key: Optional[str] = None
    group_id: Optional[str] = None  # for minimax
    is_pro: bool = False  # for minimax

    APPID: Optional[str] = None  # for xinghuo
    APISecret: Optional[str] = None  # for xinghuo
    is_v2: bool = False  # for xinghuo

    worker_name: Optional[str] = None
    override_fields: dict = {}

    class Config:
        extra = "allow"

    @root_validator(pre=True)
    def validate_config(cls, v: Dict) -> Dict:
        if config := get_model_worker_config(v.get("worker_name")):
            for n in cls.__fields__:
                if n in config:
                    v[n] = config[n]
        return v

    def load_config(self, worker_name: str):
        self.worker_name = worker_name
        if config := get_model_worker_config(worker_name):
            for n in self.__fields__:
                if n in config and not self.override_fields.get(n):
                    setattr(self, n, config[n])
        return self


class ApiModelParams(ApiConfigParams):
    '''
    模型配置参数
    '''
    version: Optional[str] = None
    version_url: Optional[str] = None
    api_version: Optional[str] = None  # for azure
    deployment_name: Optional[str] = None  # for azure
    resource_name: Optional[str] = None  # for azure

    temperature: float = TEMPERATURE
    max_tokens: Optional[int] = None
    top_p: Optional[float] = 0.8
    enable_thinking: Optional[bool] = None
    provider: Optional[str] = None


class ApiChatParams(ApiModelParams):
    '''
    chat请求参数
    '''
    messages: List[Dict[str, Union[str, List]]]
    system_message: Optional[str] = None  # for minimax
    role_meta: Dict = {}  # for minimax
    extra: Optional[Dict[str, Any]] = None # for extra input


class ApiChatWithFeedbackParams(ApiChatParams):
    feedbackUrl: str = None


class ApiCompletionParams(ApiModelParams):
    prompt: str


class ApiEmbeddingsParams(ApiConfigParams):
    texts: List[str]
    embed_model: Optional[str] = None
    to_query: bool = False  # for minimax
    role_meta: Dict = {}  # for minimax


class ApiModelWorker(BaseModelWorker):
    DEFAULT_EMBED_MODEL: str = None  # None means not support embedding

    def __init__(
            self,
            model_names: List[str],
            controller_addr: str = None,
            worker_addr: str = None,
            context_len: int = MAX_TOKENS_INPUT,
            no_register: bool = False,
            **kwargs,
    ):
        kwargs.setdefault("worker_id", uuid.uuid4().hex[:8])
        kwargs.setdefault("model_path", "")
        kwargs.setdefault("limit_worker_concurrency", 5)
        super().__init__(model_names=model_names,
                         controller_addr=controller_addr,
                         worker_addr=worker_addr,
                         **kwargs)
        import fastchat.serve.base_model_worker
        import sys
        self.logger = fastchat.serve.base_model_worker.logger
        # 恢复被fastchat覆盖的标准输出
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)

        self.context_len = context_len
        self.semaphore = asyncio.Semaphore(self.limit_worker_concurrency)
        self.version = None

        if not no_register and self.controller_addr:
            self.init_heart_beat()

    def count_token(self, params):
        prompt = params["prompt"]
        length = 0
        if isinstance(prompt, list):
            for p in prompt:
                length += calculate_token_len(p.get("role", ""), p.get("content", ""))
        else:
            length += get_tiktoken_num(prompt)
        return {"count": length, "error_code": 0}

    def generate_stream_gate(self, params: Dict):
        self.call_ct += 1

        try:
            prompt = params["prompt"]
            if isinstance(prompt, list):
                messages = prompt
            else:
                messages = [{"role": self.user_role, "content": prompt}]

            p = ApiChatParams(
                messages=self.validate_messages(messages),
                temperature=params.get("temperature"),
                top_p=params.get("top_p"),
                max_tokens=params.get("max_new_tokens"),
                version=self.version,
                enable_thinking=params.get("enable_thinking"),
                extra=params.get("extra"),
                override_fields={"top_p": params.get("top_p") is not None,
                                 "max_tokens": params.get("max_new_tokens") is not None,
                                 "temperature": params.get("temperature") is not None,
                                 "enable_thinking": params.get("enable_thinking") is not None},
            )
            for resp in self.do_chat(p):
                yield self._jsonify(resp)
        except Exception as e:
            yield self._jsonify({"error_code": 500, "text": f"{self.model_names[0]}请求API时发生错误：{e}"})

    def generate_gate(self, params):
        try:
            for x in self.generate_stream_gate(params):
                ...
            return json.loads(x[:-1].decode())
        except Exception as e:
            return {"error_code": 500, "text": str(e)}

    # 需要用户自定义的方法

    def do_chat(self, params: ApiChatParams) -> Dict:
        '''
        执行Chat的方法，默认使用模块里面的chat函数。
        要求返回形式：{"error_code": int, "text": str}
        '''
        return {"error_code": 500, "text": f"{self.model_names[0]}未实现chat功能"}

    # def do_completion(self, p: ApiCompletionParams) -> Dict:
    #     '''
    #     执行Completion的方法，默认使用模块里面的completion函数。
    #     要求返回形式：{"error_code": int, "text": str}
    #     '''
    #     return {"error_code": 500, "text": f"{self.model_names[0]}未实现completion功能"}

    def do_embeddings(self, params: ApiEmbeddingsParams) -> Dict:
        '''
        执行Embeddings的方法，默认使用模块里面的embed_documents函数。
        要求返回形式：{"code": int, "data": List[List[float]], "msg": str}
        '''
        return {"code": 500, "msg": f"{self.model_names[0]}未实现embeddings功能"}

    def get_embeddings(self, params):
        # fastchat对LLM做Embeddings限制很大，似乎只能使用openai的。
        # 在前端通过OpenAIEmbeddings发起的请求直接出错，无法请求过来。
        print("get_embedding")
        print(params)

    def make_conv_template(self, conv_template: str = None, model_path: str = None) -> Conversation:
        raise NotImplementedError

    def validate_messages(self, messages: List[Dict]) -> List[Dict]:
        '''
        有些API对mesages有特殊格式，可以重写该函数替换默认的messages。
        之所以跟prompt_to_messages分开，是因为他们应用场景不同、参数不同
        '''
        return messages

    # help methods
    @property
    def user_role(self):
        return self.conv.roles[0]

    @property
    def ai_role(self):
        return self.conv.roles[1]

    def _jsonify(self, data: Dict) -> str:
        '''
        将chat函数返回的结果按照fastchat openai-api-server的格式返回
        '''
        return json.dumps(data, ensure_ascii=False).encode() + b"\0"

    @classmethod
    def can_embedding(cls):
        return cls.DEFAULT_EMBED_MODEL is not None

    def format_online_llm(self):
        return True
