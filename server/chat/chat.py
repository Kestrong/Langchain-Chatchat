import asyncio
import json
import uuid
from typing import AsyncIterable, Dict, Any
from typing import List, Optional, Union

from fastapi import Body
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.chains import LLMChain
from langchain.prompts.chat import ChatPromptTemplate
from langchain_core.prompts import PromptTemplate
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

from configs import LLM_MODELS, TEMPERATURE, logger, TOP_P
from server.callback_handler.conversation_callback_handler import ConversationCallbackHandler
from server.callback_handler.task_callback_handler import TaskCallbackHandler
from server.chat.chat_type import ChatType
from server.chat.task_manager import task_manager
from server.chat.utils import History, EMPTY_LLM_CHAT_PROMPT, parse_llm_token_inner_json, \
    wrap_event_response, un_format_online_llm_model
from server.db.repository import add_message_to_db, filter_message
from server.memory.conversation_db_buffer_memory import ConversationBufferDBMemory
from server.model_workers import ApiModelParams
from server.utils import get_prompt_template, BaseResponse, parse_json_md
from server.utils import wrap_done, get_ChatOpenAI


async def chat(query: str = Body(..., description="用户输入", examples=["恼羞成怒"]),
               tag: str = Body(default="", description="会话标签"),
               assistant_id: int = Body(-1, description="助手ID"),
               extra: dict = Body({}, description="额外的属性"),
               conversation_id: str = Body("", description="对话框ID"),
               history_len: int = Body(-1, description="从数据库中取历史消息的数量"),
               history: Union[int, List[History]] = Body([],
                                                         description="历史对话，设为一个整数可以从数据库中读取历史消息",
                                                         examples=[[
                                                             {"role": "user",
                                                              "content": "我们来玩成语接龙，我先来，生龙活虎"},
                                                             {"role": "assistant", "content": "虎头虎脑"}]]
                                                         ),
               stream: bool = Body(False, description="流式输出"),
               model_name: str = Body(LLM_MODELS[0], description="LLM 模型名称。"),
               temperature: float = Body(TEMPERATURE, description="LLM 采样温度", ge=0.0, le=2.0),
               max_tokens: Optional[int] = Body(None, description="限制LLM生成Token数量，默认None代表模型最大值"),
               top_p: float = Body(TOP_P, description="LLM 核采样。勿与temperature同时设置", gt=0.0, lt=1.0),
               prompt_name: str = Body("default", description="使用的prompt模板名称(在configs/prompt_config.py中配置)"),
               store_message: bool = Body(True, description="是否保存消息到数据库"),
               request: Request = None
               ):
    origin_query = query
    message_id = uuid.uuid4().hex
    if not conversation_id:
        conversation_id = uuid.uuid4().hex
    if un_format_online_llm_model(model_name):
        extra['question'] = query
        extra['stream'] = stream
        extra["cookie"] = request.headers.get('cookie')
        apiModelParams = ApiModelParams(messages=[]).load_config(worker_name=model_name)
        if apiModelParams.provider in ['DifyWorker', 'FuXiWorker', 'QimingWorker']:
            if not extra.get("conversation_id"):
                m = filter_message(conversation_id=conversation_id, limit=1, not_response=False, reverse=True,
                                   meta_data_key_exists=['third_conversation_id'])
                if m:
                    extra['conversation_id'] = m[0].get('meta_data', {}).get('third_conversation_id')
                else:
                    logger.warning(f"conversation_id[{conversation_id}] not found any associate messages")
        else:
            extra['conversation_id'] = conversation_id
            extra['message_id'] = message_id
        query = json.dumps(extra)

    async def chat_iterator() -> AsyncIterable[str]:
        nonlocal history, max_tokens
        callback = AsyncIteratorCallbackHandler()
        callbacks = [callback]

        # 负责保存llm response到message db
        realtime_token_save = extra.get("realtime_token_save", False)
        add_message_to_db(chat_type=ChatType.LLM_CHAT.value, query=origin_query,
                          response='' if realtime_token_save else None, conversation_id=conversation_id,
                          store=store_message, message_id=message_id, assistant_id=assistant_id, tag=tag)
        conversation_callback = ConversationCallbackHandler(model_name=model_name, conversation_id=conversation_id,
                                                            message_id=message_id, chat_type=ChatType.LLM_CHAT.value,
                                                            query=origin_query, realtime_token_save=realtime_token_save,
                                                            stream=stream)
        task_callback = TaskCallbackHandler(conversation_id=conversation_id, message_id=message_id)
        callbacks.extend([conversation_callback, task_callback])
        # message_id = uuid.uuid4().hex

        # Enable langchain-chatchat to support langfuse
        import os
        langfuse_secret_key = os.environ.get('LANGFUSE_SECRET_KEY')
        langfuse_public_key = os.environ.get('LANGFUSE_PUBLIC_KEY')
        langfuse_host = os.environ.get('LANGFUSE_HOST')
        if langfuse_secret_key and langfuse_public_key and langfuse_host:
            from langfuse.callback import CallbackHandler
            langfuse_handler = CallbackHandler()
            callbacks.append(langfuse_handler)

        if isinstance(max_tokens, int) and max_tokens <= 0:
            max_tokens = None

        model = get_ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            callbacks=[callback],
            top_p=top_p,
            enable_thinking=extra.get("enable_thinking")
        )

        prompt_template = get_prompt_template("llm_chat", prompt_name)
        input_msg = History(role="user", content=prompt_template).to_msg_template(False)
        if history:  # 优先使用前端传入的历史消息
            history = [History.from_data(h) for h in history]
            chat_prompt = ChatPromptTemplate.from_messages([i.to_msg_template() for i in history] + [input_msg])
        elif conversation_id and history_len > 0:  # 前端要求从数据库取历史消息
            # 根据conversation_id 获取message 列表进而拼凑 memory
            memory = ConversationBufferDBMemory(conversation_id=conversation_id,
                                                llm=model,
                                                message_limit=history_len)
            chat_prompt = ChatPromptTemplate.from_messages(memory.buffer + [input_msg])
        else:
            chat_prompt = ChatPromptTemplate.from_messages([input_msg])

        if un_format_online_llm_model(model_name):
            chat_prompt = EMPTY_LLM_CHAT_PROMPT

        chain = LLMChain(prompt=chat_prompt, llm=model)

        # Begin a task that runs in the background.
        task = asyncio.create_task(wrap_done(
            chain.acall({"input": query}, callbacks=callbacks),
            callback.done),
        )

        task_manager.put(message_id, task)

        d = {"message_id": message_id, "conversation_id": conversation_id, "answer": ""}
        yield json.dumps(d, ensure_ascii=False)
        if not extra.get('backend'):
            if stream:
                async for token in callback.aiter():
                    # Use server-sent-events to stream the response
                    d.update(parse_llm_token_inner_json(model_name, token))
                    yield json.dumps(d, ensure_ascii=False)
            else:
                answer = ""
                async for token in callback.aiter():
                    answer += str(token)
                d.update(parse_llm_token_inner_json(model_name, answer))
                yield json.dumps(d, ensure_ascii=False)

            await task

    return EventSourceResponse(wrap_event_response(chat_iterator()))


def recommend_question(query: str = Body(..., description="用户输入", examples=["今天天气很好"]),
                       context: Dict[str, Any] = Body({}, description="额外的属性帮助大模型理解问题和生成内容"),
                       model_name: str = Body(LLM_MODELS[0], description="LLM模型名称"),
                       prompt: str = Body("default", description="使用的prompt，为空使用默认的")) -> BaseResponse:
    model = get_ChatOpenAI(
        model_name=model_name,
        temperature=TEMPERATURE,
        streaming=True,
    )
    if prompt is None or prompt.strip() == '':
        prompt = 'default'
    prompt = get_prompt_template('recommend_question', prompt)
    template = PromptTemplate(input_variables=["question", "context"], template=prompt, template_format="jinja2")
    chain = LLMChain(llm=model, prompt=template)
    result = chain.predict_and_parse(**{"question": query, "context": context})
    if result and isinstance(result, list):
        if isinstance(result[0], list):
            result = result[0]
    return BaseResponse(code=200, data=json.loads(parse_json_md(result)))
