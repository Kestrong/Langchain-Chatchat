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
from starlette.requests import Request

from configs import LLM_MODELS, TEMPERATURE, TOP_P, HISTORY_LEN, logger
from server.callback_handler.conversation_callback_handler import ConversationCallbackHandler
from server.callback_handler.task_callback_handler import TaskCallbackHandler
from server.chat.chat_type import ChatType
from server.chat.task_manager import task_manager
from server.chat.utils import History, parse_llm_token_inner_json, \
    un_format_online_llm_model, choose_response, unify_chat_files, get_tiktoken_num, has_input_memory_key
from server.db.repository import add_message_to_db, filter_message
from server.memory.conversation_db_buffer_memory import ConversationBufferDBMemory
from server.memory.conversation_window_buffer_memory import ConversationBufferWindowMemory
from server.memory.token_info_memory import get_token
from server.model_workers import ApiModelParams
from server.utils import get_prompt_template, BaseResponse, parse_json_md
from server.utils import wrap_done, get_ChatOpenAI


def process_extra(stream: bool, model_name: str, conversation_id: Union[str, None], extra: dict,
                  request: Request, ):
    if un_format_online_llm_model(model_name):
        extra["token"] = get_token()
        extra['stream'] = stream
        extra["cookie"] = request.headers.get('cookie') if request else None
        if conversation_id:
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


async def chat(query: str = Body(..., description="用户输入", examples=["恼羞成怒"]),
               tag: str = Body(default="", description="会话标签"),
               assistant_id: int = Body(-1, description="助手ID"),
               knowledge_id: str = Body("", description="临时知识库ID"),
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
    message_id = uuid.uuid4().hex
    if not conversation_id:
        conversation_id = uuid.uuid4().hex
    chat_files = unify_chat_files(third_party_files=extra.pop('files', []), knowledge_id=knowledge_id, request=request)
    extra['chat_files'] = chat_files
    un_format = un_format_online_llm_model(model_name)
    chat_type = ChatType.LLM_CHAT.value

    async def chat_iterator() -> AsyncIterable[str]:
        nonlocal history, max_tokens
        callback = AsyncIteratorCallbackHandler()
        callbacks = []

        # 负责保存llm response到message db
        realtime_token_save = extra.get("realtime_token_save", False)
        add_message_to_db(chat_type=chat_type, query=query, conversation_id=conversation_id,
                          response='' if realtime_token_save else None, store=store_message, message_id=message_id,
                          assistant_id=assistant_id, tag=tag, metadata={'chat_files': chat_files} if chat_files else {})
        conversation_callback = ConversationCallbackHandler(model_name=model_name, conversation_id=conversation_id,
                                                            message_id=message_id, chat_type=chat_type,
                                                            query=query, realtime_token_save=realtime_token_save,
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

        process_extra(stream=stream, model_name=model_name, extra=extra, conversation_id=conversation_id,
                      request=request)

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
        in_tuple = History(role="user", content=query, chat_files=chat_files).get_content_tuple(
            format_openai=not un_format)
        input_content, image_urls, input_len, _ = in_tuple
        input_template = History(role="user", content=prompt_template, ).to_msg_template(format_openai=not un_format,
                                                                                         image_urls=image_urls)
        prompt_length = input_len + get_tiktoken_num(prompt_template)
        if history:  # 优先使用前端传入的历史消息
            history = [History.from_data(h) for h in history]
            if isinstance(history[-1].content, str) and history[-1].content == query:
                history = history[:-1]
            memory = ConversationBufferWindowMemory(model_name=model_name,
                                                    message_limit=max(HISTORY_LEN * 2, len(history) if history else 0),
                                                    prompt_length=prompt_length)
            memory.return_messages = not has_input_memory_key(input_template.input_variables, memory.memory_variables)
            for h in history:
                if h.role in ["user", "human"]:
                    memory.chat_memory.add_user_message(h.to_msg_tuple(format_openai=not un_format)[1])
                else:
                    memory.chat_memory.add_ai_message(h.content)
            chat_prompt = ChatPromptTemplate.from_messages(
                memory.buffer_history(input_template.input_variables) + [input_template])
        elif conversation_id and history_len > 0:  # 前端要求从数据库取历史消息
            # 根据conversation_id 获取message 列表进而拼凑 memory
            memory = ConversationBufferDBMemory(conversation_id=conversation_id, model_name=model_name,
                                                prompt_length=prompt_length, message_limit=history_len)
            memory.return_messages = not has_input_memory_key(input_template.input_variables, memory.memory_variables)
            chat_prompt = ChatPromptTemplate.from_messages(
                memory.buffer_history(input_template.input_variables) + [input_template])
        else:
            chat_prompt = ChatPromptTemplate.from_messages([input_template])
            memory = ConversationBufferWindowMemory(model_name=model_name, return_messages=False, message_limit=0,
                                                    prompt_length=prompt_length)

        chain = LLMChain(prompt=chat_prompt, llm=model, memory=memory)

        # Begin a task that runs in the background.
        task = asyncio.create_task(wrap_done(
            chain.acall({"input": input_content}, callbacks=callbacks),
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

    return await choose_response(stream, chat_iterator(), request)


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
