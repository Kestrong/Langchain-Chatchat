import asyncio
import json
import uuid
from typing import AsyncIterable, Optional

from fastapi import Body
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from starlette.requests import Request

from configs import LLM_MODELS, TEMPERATURE, TOP_P
from server.callback_handler.conversation_callback_handler import ConversationCallbackHandler
from server.callback_handler.task_callback_handler import TaskCallbackHandler
from server.chat.chat import process_extra
from server.chat.chat_type import ChatType
from server.chat.utils import parse_llm_token_inner_json, \
    choose_response, un_format_online_llm_model
from server.db.repository import add_message_to_db
from server.utils import get_prompt_template
from server.utils import wrap_done, get_ChatOpenAI


async def completion(query: str = Body(..., description="用户输入", examples=["恼羞成怒"]),
                     tag: str = Body(default="", description="会话标签"),
                     assistant_id: int = Body(-1, description="助手ID"),
                     extra: dict = Body({}, description="额外的属性"),
                     stream: bool = Body(False, description="流式输出"),
                     model_name: str = Body(LLM_MODELS[0], description="LLM 模型名称。"),
                     temperature: float = Body(TEMPERATURE, description="LLM 采样温度", ge=0.0, le=1.0),
                     max_tokens: Optional[int] = Body(1024, description="限制LLM生成Token数量，默认None代表模型最大值"),
                     top_p: float = Body(TOP_P, description="LLM 核采样。勿与temperature同时设置", gt=0.0, lt=1.0),
                     prompt_name: str = Body("default",
                                             description="使用的prompt模板名称(在configs/prompt_config.py中配置)"),
                     store_message: bool = Body(True, description="是否保存消息到数据库"),
                     request: Request = None
                     ):
    un_format = un_format_online_llm_model(model_name)
    chat_type = ChatType.COMPLETION.value

    async def completion_iterator(query: str,
                                  model_name: str = LLM_MODELS[0],
                                  prompt_name: str = prompt_name,
                                  ) -> AsyncIterable[str]:
        nonlocal max_tokens
        callback = AsyncIteratorCallbackHandler()
        if isinstance(max_tokens, int) and max_tokens <= 0:
            max_tokens = None
        conversation_id = uuid.uuid4().hex
        message_id = uuid.uuid4().hex
        add_message_to_db(chat_type=chat_type, query=query, conversation_id=uuid.uuid4().hex,
                          store=store_message, message_id=message_id,
                          assistant_id=assistant_id, tag=tag, )
        conversation_callback = ConversationCallbackHandler(model_name=model_name, conversation_id=conversation_id,
                                                            message_id=message_id, chat_type=chat_type, query=query,
                                                            stream=stream)
        task_callback = TaskCallbackHandler(conversation_id=conversation_id, message_id=message_id)
        callbacks = [conversation_callback, task_callback]
        process_extra(stream=stream, model_name=model_name, extra=extra, conversation_id=None, request=request)

        model = get_ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            callbacks=[callback],
            top_p=top_p,
            enable_thinking=extra.get("enable_thinking"),
            extra_body={"extra": extra} if un_format else None,
        )
        prompt_template = get_prompt_template(chat_type, prompt_name)
        prompt = PromptTemplate.from_template(prompt_template, template_format="jinja2")
        chain = LLMChain(prompt=prompt, llm=model)

        # Begin a task that runs in the background.
        task = asyncio.create_task(wrap_done(
            chain.acall({"input": query}, callbacks=callbacks),
            callback.done),
        )
        if not extra.get('backend'):
            if stream:
                async for token in callback.aiter():
                    # Use server-sent-events to stream the response
                    yield json.dumps(parse_llm_token_inner_json(model_name, token), ensure_ascii=False)
            else:
                answer = ""
                async for token in callback.aiter():
                    answer += str(token)
                yield json.dumps(parse_llm_token_inner_json(model_name, answer), ensure_ascii=False)

        await task

    return await choose_response(stream, completion_iterator(query=query,
                                                             model_name=model_name,
                                                             prompt_name=prompt_name), request)
