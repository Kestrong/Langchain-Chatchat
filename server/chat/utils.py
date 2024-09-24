import json
from typing import List, Tuple, Dict, Union, AsyncIterable

from langchain.prompts.chat import ChatMessagePromptTemplate
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from common.exceptions import ChatBusinessException
from configs import logger, log_verbose
from server.db.repository import update_message
from server.memory.message_i18n import Message_I18N


class History(BaseModel):
    """
    对话历史
    可从dict生成，如
    h = History(**{"role":"user","content":"你好"})
    也可转换为tuple，如
    h.to_msy_tuple = ("human", "你好")
    """
    role: str = Field(...)
    content: str = Field(...)

    def to_msg_tuple(self):
        return "ai" if self.role == "assistant" else "human", self.content

    def to_msg_template(self, is_raw=True) -> ChatMessagePromptTemplate:
        role_maps = {
            "ai": "assistant",
            "human": "user",
        }
        role = role_maps.get(self.role, self.role)
        if is_raw:  # 当前默认历史消息都是没有input_variable的文本。
            content = "{% raw %}" + self.content + "{% endraw %}"
        else:
            content = self.content

        return ChatMessagePromptTemplate.from_template(
            content,
            "jinja2",
            role=role,
        )

    @classmethod
    def from_data(cls, h: Union[List, Tuple, Dict]) -> "History":
        if isinstance(h, (list, tuple)) and len(h) >= 2:
            h = cls(role=h[0], content=h[1])
        elif isinstance(h, dict):
            h = cls(**h)

        return h


def parse_llm_token_inner_json(model_name: str, token: str):
    if model_name in UN_FORMAT_ONLINE_LLM_MODELS:
        mark = f'###[{model_name}]###'
        if token.startswith(mark) and token.endswith(mark):
            inner_json = json.loads(token.lstrip(mark).rstrip(mark))
            return {"answer": inner_json.get('answer'), 'extra': {"conversation_id": inner_json.get('conversation_id'),
                                                                  "message_id": inner_json.get('message_id')}}
    return {"answer": token}


class MaxInputTokenException(BaseException):
    pass


async def wrap_event_response(event_response: AsyncIterable[str]) -> AsyncIterable[str]:
    d = {}
    try:
        first = True
        async for event in event_response:
            if first:
                try:
                    first = False
                    d.update(json.loads(event))
                except:
                    pass
            yield event
    except MaxInputTokenException as e:
        d["answer"] = f"{e}"
        if d.get("message_id"):
            update_message(message_id=d.get("message_id"), response=d["answer"])
        yield json.dumps(d, ensure_ascii=False)
    except BaseException as e:
        if isinstance(e, ChatBusinessException):
            d["answer"] = str(e)
            e = e.__cause__
            logger.error(f'{e.__class__.__name__}: {e}', exc_info=e if log_verbose else None)
            yield json.dumps(d, ensure_ascii=False)
        else:
            msg = f'{e.__class__.__name__}: {e}'
            logger.error(msg, exc_info=e if log_verbose else None)
            d["answer"] = Message_I18N.WORKER_CHAT_ERROR.value
            if d.get("message_id"):
                update_message(message_id=d.get("message_id"), response=d["answer"], metadata={"error_info": msg})
            yield json.dumps(d, ensure_ascii=False)


EMPTY_LLM_CHAT_PROMPT = PromptTemplate.from_template("{{ input }}", template_format="jinja2")

# 特殊的在线大模型，不支持知识库、agent对话等模式
UN_FORMAT_ONLINE_LLM_MODELS = ['qiming-api', 'iotqwen-api', 'lingxi-fault-api']
