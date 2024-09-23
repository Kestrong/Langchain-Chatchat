import asyncio
import json
from collections import OrderedDict
from typing import AsyncIterable, List, Optional
from urllib.parse import urlencode

from fastapi import Body, Request
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
                     RERANKER_MAX_LENGTH)
from server.callback_handler.conversation_callback_handler import ConversationCallbackHandler
from server.callback_handler.task_callback_handler import TaskCallbackHandler
from server.chat.chat_type import ChatType
from server.chat.task_manager import task_manager
from server.chat.utils import History, UN_FORMAT_ONLINE_LLM_MODELS, wrap_event_response
from server.db.repository import add_message_to_db
from server.knowledge_base.kb_doc_api import search_docs
from server.knowledge_base.kb_service.base import KBServiceFactory
from server.memory.message_i18n import Message_I18N
from server.reranker.reranker import LangchainReranker
from server.utils import BaseResponse, get_prompt_template
from server.utils import embedding_device
from server.utils import wrap_done, get_ChatOpenAI, get_model_path


async def knowledge_base_chat(query: str = Body(..., description="用户输入", examples=["你好"]),
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

    if model_name in UN_FORMAT_ONLINE_LLM_MODELS:
        return BaseResponse(code=500,
                            msg=Message_I18N.API_CHAT_TYPE_NOT_SUPPORT.value.format(
                                chat_type=ChatType.KNOWLEDGE_BASE_CHAT.value,
                                model_name=model_name))

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
                                       conversation_id=conversation_id, store=store_message)
        conversation_callback = ConversationCallbackHandler(model_name=model_name, conversation_id=conversation_id,
                                                            message_id=message_id, query=query,
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
        )
        docs = []
        for knowledge_base_name in knowledge_base_names:
            docs_part = await run_in_threadpool(search_docs,
                                                query=query,
                                                knowledge_base_name=knowledge_base_name,
                                                top_k=top_k,
                                                score_threshold=score_threshold)
            for d in docs_part:
                d.metadata['kb_name'] = knowledge_base_name
                docs.append(d)
        docs.sort(key=lambda x: x.score)
        if len(docs) > top_k:
            docs = docs[:top_k]

        # 加入reranker
        if USE_RERANKER:
            reranker_model_path = get_model_path(RERANKER_MODEL)
            reranker_model = LangchainReranker(top_n=top_k,
                                               device=embedding_device(),
                                               max_length=RERANKER_MAX_LENGTH,
                                               model_name_or_path=reranker_model_path
                                               )
            print("-------------before rerank-----------------")
            print(docs)
            docs = reranker_model.compress_documents(documents=docs,
                                                     query=query)
            print("------------after rerank------------------")
            print(docs)

        docs_map = OrderedDict()
        for doc in docs:
            source = doc.metadata['source']
            if source not in docs_map:
                docs_map[source] = []
            docs_map[source].append(doc)
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
                parameters = urlencode({"knowledge_base_name": doc.metadata.get("kb_name"), "file_name": filename,
                                        "preview": True})
                url = "/knowledge_base/download_doc?" + parameters
                source_documents.append({"filename": filename, "url": url})
                exist_file.append(filename)
        conversation_callback.docs = source_documents

        prompt_template = get_prompt_template("knowledge_base_chat", prompt_name)
        input_msg = History(role="user", content=prompt_template).to_msg_template(False)
        chat_prompt = ChatPromptTemplate.from_messages([i.to_msg_template() for i in history] + [input_msg])

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
                yield json.dumps({"answer": token, "message_id": message_id, "conversation_id": conversation_id},
                                 ensure_ascii=False)
            yield json.dumps({"docs": source_documents, "message_id": message_id, "conversation_id": conversation_id},
                             ensure_ascii=False)
        else:
            answer = ""
            async for token in callback.aiter():
                answer += str(token)
            yield json.dumps({"answer": answer, "message_id": message_id, "conversation_id": conversation_id,
                              "docs": source_documents},
                             ensure_ascii=False)
        await task

    return EventSourceResponse(
        wrap_event_response(knowledge_base_chat_iterator(query, top_k, history, model_name, prompt_name)))
