import asyncio
import json
import uuid
from collections import OrderedDict
from typing import AsyncIterable, List, Optional

from fastapi import Body
from fastapi.concurrency import run_in_threadpool
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.chains import LLMChain
from langchain.prompts.chat import ChatPromptTemplate
from sse_starlette.sse import EventSourceResponse

from configs import (LLM_MODELS,
                     VECTOR_SEARCH_TOP_K,
                     SCORE_THRESHOLD,
                     TEMPERATURE,
                     USE_RERANKER,
                     RERANKER_MODEL,
                     RERANKER_MAX_LENGTH, TOP_P)
from server.callback_handler.conversation_callback_handler import ConversationCallbackHandler
from server.callback_handler.task_callback_handler import TaskCallbackHandler
from server.chat.chat_type import ChatType
from server.chat.task_manager import task_manager
from server.chat.utils import History, wrap_event_response, un_format_online_llm_model, parse_llm_token_inner_json
from server.db.repository import add_message_to_db
from server.knowledge_base.kb_doc_api import search_docs
from server.knowledge_base.kb_service.base import KBServiceFactory
from server.memory.conversation_db_buffer_memory import ConversationBufferDBMemory
from server.memory.message_i18n import Message_I18N
from server.utils import BaseResponse, get_prompt_template, truncate_text
from server.utils import embedding_device
from server.utils import wrap_done, get_ChatOpenAI, get_model_path


async def knowledge_base_chat(query: str = Body(..., description="用户输入", examples=["你好"]),
                              tag: str = Body(default="", description="会话标签"),
                              assistant_id: int = Body(-1, description="助手ID"),
                              extra: dict = Body({}, description="额外的属性"),
                              conversation_id: str = Body("", description="对话框ID"),
                              knowledge_base_names: List[str] = Body([], description="知识库名称",
                                                                     examples=[["samples"]]),
                              top_k: int = Body(VECTOR_SEARCH_TOP_K, description="匹配向量数"),
                              score_threshold: float = Body(
                                  SCORE_THRESHOLD,
                                  description="知识库匹配相关度阈值，取值范围在0-1之间，SCORE越小，相关度越高，取到1相当于不筛选，建议设置在0.5左右",
                                  ge=0,
                                  le=2
                              ),
                              history_len: int = Body(-1, description="从数据库中取历史消息的数量"),
                              history: List[History] = Body(
                                  [],
                                  description="历史对话",
                                  examples=[[
                                      {"role": "user",
                                       "content": "我们来玩成语接龙，我先来，生龙活虎"},
                                      {"role": "assistant",
                                       "content": "虎头虎脑"}]]
                              ),
                              stream: bool = Body(False, description="流式输出"),
                              model_name: str = Body(LLM_MODELS[0], description="LLM 模型名称。"),
                              temperature: float = Body(TEMPERATURE, description="LLM 采样温度", ge=0.0, le=1.0),
                              max_tokens: Optional[int] = Body(
                                  None,
                                  description="限制LLM生成Token数量，默认None代表模型最大值"
                              ),
                              top_p: float = Body(TOP_P, description="LLM 核采样。勿与temperature同时设置", gt=0.0,
                                                  lt=1.0),
                              prompt_name: str = Body(
                                  "default",
                                  description="使用的prompt模板名称(在configs/prompt_config.py中配置)"
                              ),
                              store_message: bool = Body(True, description="是否保存消息到数据库"),
                              ):
    if not knowledge_base_names:
        return BaseResponse(code=500, msg=Message_I18N.API_PARAM_NOT_PRESENT.value.format(name='knowledge_base_names'))
    for k in knowledge_base_names:
        kb = KBServiceFactory.get_service_by_name(k)
        if kb is None:
            return BaseResponse(code=500, msg=Message_I18N.API_KB_NOT_EXIST.value.format(kb_name=k))

    history = [History.from_data(h) for h in history]

    if un_format_online_llm_model(model_name):
        return BaseResponse(code=500,
                            msg=Message_I18N.API_CHAT_TYPE_NOT_SUPPORT.value.format(
                                chat_type=ChatType.KNOWLEDGE_BASE_CHAT.value,
                                model_name=model_name))

    if not conversation_id:
        conversation_id = uuid.uuid4().hex

    async def knowledge_base_chat_iterator(
            query: str,
            top_k: int,
            history: Optional[List[History]],
            model_name: str = model_name,
            prompt_name: str = prompt_name,
    ) -> AsyncIterable[str]:
        nonlocal max_tokens
        callback = AsyncIteratorCallbackHandler()
        # 负责保存llm response到message db
        message_id = add_message_to_db(chat_type=ChatType.KNOWLEDGE_BASE_CHAT.value, query=query,
                                       assistant_id=assistant_id, tag=tag,
                                       conversation_id=conversation_id, store=store_message)
        conversation_callback = ConversationCallbackHandler(model_name=model_name, conversation_id=conversation_id,
                                                            message_id=message_id, query=query, stream=stream,
                                                            chat_type=ChatType.KNOWLEDGE_BASE_CHAT.value)
        task_callback = TaskCallbackHandler(conversation_id=conversation_id, message_id=message_id)
        if isinstance(max_tokens, int) and max_tokens <= 0:
            max_tokens = None

        callbacks = [callback, conversation_callback, task_callback]
        # Enable langchain-chatchat to support langfuse
        import os
        langfuse_secret_key = os.environ.get('LANGFUSE_SECRET_KEY')
        langfuse_public_key = os.environ.get('LANGFUSE_PUBLIC_KEY')
        langfuse_host = os.environ.get('LANGFUSE_HOST')
        if langfuse_secret_key and langfuse_public_key and langfuse_host:
            from langfuse.callback import CallbackHandler
            langfuse_handler = CallbackHandler()
            callbacks.append(langfuse_handler)

        model = get_ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            callbacks=[callback],
            top_p=top_p,
            enable_thinking=extra.get("enable_thinking")
        )
        docs = []
        for knowledge_base_name in knowledge_base_names:
            docs_part = await run_in_threadpool(search_docs,
                                                query=query,
                                                knowledge_base_name=knowledge_base_name,
                                                top_k=top_k,
                                                score_threshold=score_threshold,
                                                file_name="",
                                                metadata={})
            for d in docs_part:
                d.metadata['kb_name'] = knowledge_base_name
                docs.append(d)
        docs.sort(key=lambda x: x.score)

        # 加入reranker
        if USE_RERANKER:
            from server.reranker.reranker import LangchainReranker
            reranker_model_path = get_model_path(RERANKER_MODEL)
            reranker_model = LangchainReranker(top_n=max(top_k // 2, 3),
                                               device=embedding_device(),
                                               max_length=RERANKER_MAX_LENGTH,
                                               model_name_or_path=reranker_model_path
                                               )
            docs = reranker_model.compress_documents(documents=docs,
                                                     query=query)

        if len(docs) > top_k:
            docs = docs[:top_k]
        docs_map = OrderedDict()
        for doc in docs:
            key = f"{doc.metadata.get('kb_name')}:{doc.metadata.get('source')}"
            if key not in docs_map:
                docs_map[key] = []
            docs_map[key].append(doc)
        docs = []
        for key, value in docs_map.items():
            if len(value) > 0 and 'index' in value[0].metadata:
                value.sort(key=lambda x: x.metadata['index'])
            docs.extend(value)
        context = ""
        source_documents = []
        exist_file = []
        for inum, doc in enumerate(docs):
            context += doc.page_content + "\n"
            filename = doc.metadata["source"]
            if filename not in exist_file:
                source_documents.append({"filename": filename, "knowledge_base_name": doc.metadata.get("kb_name"),
                                         "page_content": truncate_text(doc.page_content)})
                exist_file.append(filename)
        conversation_callback.docs = source_documents

        prompt_template = get_prompt_template("knowledge_base_chat", prompt_name)
        input_msg = History(role="user", content=prompt_template).to_msg_template(False)
        if history:  # 优先使用前端传入的历史消息
            chat_prompt = ChatPromptTemplate.from_messages([i.to_msg_template() for i in history] + [input_msg])
        elif conversation_id and history_len > 0:  # 前端要求从数据库取历史消息
            # 根据conversation_id 获取message 列表进而拼凑 memory
            memory = ConversationBufferDBMemory(conversation_id=conversation_id,
                                                llm=model,
                                                message_limit=history_len)
            chat_prompt = ChatPromptTemplate.from_messages(memory.buffer + [input_msg])
        else:
            chat_prompt = ChatPromptTemplate.from_messages([input_msg])

        chain = LLMChain(prompt=chat_prompt, llm=model)

        # Begin a task that runs in the background.
        task = asyncio.create_task(wrap_done(
            chain.acall({"context": context, "question": query}, callbacks=callbacks),
            callback.done),
        )

        task_manager.put(message_id, task)

        d = {"message_id": message_id, "conversation_id": conversation_id, "answer": ""}
        yield json.dumps(d, ensure_ascii=False)
        if stream:
            async for token in callback.aiter():
                # Use server-sent-events to stream the response
                d.update(parse_llm_token_inner_json(model_name, token))
                yield json.dumps(d, ensure_ascii=False)
            yield json.dumps({"message_id": message_id, "conversation_id": conversation_id, "docs": source_documents},
                             ensure_ascii=False)
        else:
            answer = ""
            async for token in callback.aiter():
                answer += str(token)
            d.update(parse_llm_token_inner_json(model_name, answer))
            d["docs"] = source_documents
            yield json.dumps(d, ensure_ascii=False)
        await task

    return EventSourceResponse(
        wrap_event_response(knowledge_base_chat_iterator(query, top_k, history, model_name, prompt_name)))
