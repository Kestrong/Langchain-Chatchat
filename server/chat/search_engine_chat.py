import asyncio
import json
from typing import AsyncIterable
from typing import List, Optional, Dict

from fastapi import Body
from fastapi.concurrency import run_in_threadpool
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.chains import LLMChain
from langchain.docstore.document import Document
from langchain.prompts.chat import ChatPromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.utilities.bing_search import BingSearchAPIWrapper
from langchain.utilities.duckduckgo_search import DuckDuckGoSearchAPIWrapper
from markdownify import markdownify
from sse_starlette import EventSourceResponse
from strsimpy.normalized_levenshtein import NormalizedLevenshtein

from configs import (BING_SEARCH_URL, BING_SUBSCRIPTION_KEY, METAPHOR_API_KEY,
                     LLM_MODELS, SEARCH_ENGINE_TOP_K, TEMPERATURE, OVERLAP_SIZE)
from server.callback_handler.conversation_callback_handler import ConversationCallbackHandler
from server.callback_handler.task_callback_handler import TaskCallbackHandler
from server.chat.chat_type import ChatType
from server.chat.task_manager import task_manager
from server.chat.utils import History, UN_FORMAT_ONLINE_LLM_MODELS, wrap_event_response
from server.db.repository import add_message_to_db
from server.memory.message_i18n import Message_I18N
from server.utils import BaseResponse, get_prompt_template
from server.utils import wrap_done, get_ChatOpenAI


def bing_search(text, result_len=SEARCH_ENGINE_TOP_K, **kwargs):
    if not (BING_SEARCH_URL and BING_SUBSCRIPTION_KEY):
        return [{"snippet": "please set BING_SUBSCRIPTION_KEY and BING_SEARCH_URL in os ENV",
                 "title": "env info is not found",
                 "link": "https://python.langchain.com/en/latest/modules/agents/tools/examples/bing_search.html"}]
    search = BingSearchAPIWrapper(bing_subscription_key=BING_SUBSCRIPTION_KEY,
                                  bing_search_url=BING_SEARCH_URL)
    return search.results(text, result_len)


def duckduckgo_search(text, result_len=SEARCH_ENGINE_TOP_K, **kwargs):
    search = DuckDuckGoSearchAPIWrapper()
    return search.results(text, result_len)


def metaphor_search(
        text: str,
        result_len: int = SEARCH_ENGINE_TOP_K,
        split_result: bool = False,
        chunk_size: int = 500,
        chunk_overlap: int = OVERLAP_SIZE,
) -> List[Dict]:
    from metaphor_python import Metaphor

    if not METAPHOR_API_KEY:
        return []

    client = Metaphor(METAPHOR_API_KEY)
    search = client.search(text, num_results=result_len, use_autoprompt=True)
    contents = search.get_contents().contents
    for x in contents:
        x.extract = markdownify(x.extract)

    # metaphor 返回的内容都是长文本，需要分词再检索
    if split_result:
        docs = [Document(page_content=x.extract,
                         metadata={"link": x.url, "title": x.title})
                for x in contents]
        text_splitter = RecursiveCharacterTextSplitter(["\n\n", "\n", ".", " "],
                                                       chunk_size=chunk_size,
                                                       chunk_overlap=chunk_overlap)
        splitted_docs = text_splitter.split_documents(docs)

        # 将切分好的文档放入临时向量库，重新筛选出TOP_K个文档
        if len(splitted_docs) > result_len:
            normal = NormalizedLevenshtein()
            for x in splitted_docs:
                x.metadata["score"] = normal.similarity(text, x.page_content)
            splitted_docs.sort(key=lambda x: x.metadata["score"], reverse=True)
            splitted_docs = splitted_docs[:result_len]

        docs = [{"snippet": x.page_content,
                 "link": x.metadata["link"],
                 "title": x.metadata["title"]}
                for x in splitted_docs]
    else:
        docs = [{"snippet": x.extract,
                 "link": x.url,
                 "title": x.title}
                for x in contents]

    return docs


SEARCH_ENGINES = {"bing": bing_search,
                  "duckduckgo": duckduckgo_search,
                  "metaphor": metaphor_search,
                  }


def search_result2docs(search_results):
    docs = []
    for result in search_results:
        doc = Document(page_content=result["snippet"] if "snippet" in result.keys() else "",
                       metadata={"source": result["link"] if "link" in result.keys() else "",
                                 "filename": result["title"] if "title" in result.keys() else ""})
        docs.append(doc)
    return docs


async def lookup_search_engine(
        query: str,
        search_engine_name: str,
        top_k: int = SEARCH_ENGINE_TOP_K,
        split_result: bool = False,
):
    search_engine = SEARCH_ENGINES[search_engine_name]
    results = await run_in_threadpool(search_engine, query, result_len=top_k, split_result=split_result)
    docs = search_result2docs(results)
    return docs


async def search_engine_chat(query: str = Body(..., description="用户输入", examples=["你好"]),
                             conversation_id: str = Body("", description="对话框ID"),
                             search_engine_name: str = Body(..., description="搜索引擎名称", examples=["duckduckgo"]),
                             top_k: int = Body(SEARCH_ENGINE_TOP_K, description="检索结果数量"),
                             history: List[History] = Body([],
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
                             max_tokens: Optional[int] = Body(None,
                                                              description="限制LLM生成Token数量，默认None代表模型最大值"),
                             prompt_name: str = Body("default",
                                                     description="使用的prompt模板名称(在configs/prompt_config.py中配置)"),
                             split_result: bool = Body(False,
                                                       description="是否对搜索结果进行拆分（主要用于metaphor搜索引擎）"),
                             store_message: bool = Body(True, description="是否保存消息到数据库"),
                             ):
    if search_engine_name not in SEARCH_ENGINES.keys():
        return BaseResponse(code=500, msg=Message_I18N.API_SEARCHENGINE_NOT_SUPPORT.value.format(
            search_engine_name=search_engine_name))

    if search_engine_name == "bing" and not BING_SUBSCRIPTION_KEY:
        return BaseResponse(code=500, msg=f"要使用Bing搜索引擎，需要设置 `BING_SUBSCRIPTION_KEY`")

    if model_name in UN_FORMAT_ONLINE_LLM_MODELS:
        return BaseResponse(code=500, msg=Message_I18N.API_CHAT_TYPE_NOT_SUPPORT.value.format(
            chat_type=ChatType.SEARCH_ENGINE_CHAT.value, model_name=model_name))

    history = [History.from_data(h) for h in history]

    async def search_engine_chat_iterator(query: str,
                                          search_engine_name: str,
                                          top_k: int,
                                          history: Optional[List[History]],
                                          model_name: str = LLM_MODELS[0],
                                          prompt_name: str = prompt_name,
                                          ) -> AsyncIterable[str]:
        nonlocal max_tokens
        callback = AsyncIteratorCallbackHandler()
        if isinstance(max_tokens, int) and max_tokens <= 0:
            max_tokens = None

        callbacks = [callback]
        message_id = add_message_to_db(chat_type=ChatType.SEARCH_ENGINE_CHAT.value, query=query,
                                       conversation_id=conversation_id, store=store_message)
        conversation_callback = ConversationCallbackHandler(model_name=model_name, conversation_id=conversation_id,
                                                            message_id=message_id, query=query,
                                                            chat_type=ChatType.SEARCH_ENGINE_CHAT.value, )
        task_callback = TaskCallbackHandler(conversation_id=conversation_id, message_id=message_id)
        callbacks.extend([conversation_callback, task_callback])
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

        docs = await lookup_search_engine(query, search_engine_name, top_k, split_result=split_result)
        context = ""
        source_documents = []
        exist_file = []
        for inum, doc in enumerate(docs):
            context += doc.page_content + "\n"
            filename = doc.metadata["filename"]
            if filename not in exist_file:
                source_documents.append({"filename": filename, "url": doc.metadata["source"]})
                exist_file.append(filename)
        conversation_callback.docs = source_documents

        prompt_template = get_prompt_template("search_engine_chat", prompt_name)
        input_msg = History(role="user", content=prompt_template).to_msg_template(False)
        chat_prompt = ChatPromptTemplate.from_messages(
            [i.to_msg_template() for i in history] + [input_msg])

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
                yield json.dumps({"message_id": message_id, "conversation_id": conversation_id, "answer": token},
                                 ensure_ascii=False)
            yield json.dumps({"message_id": message_id, "conversation_id": conversation_id, "docs": source_documents},
                             ensure_ascii=False)
        else:
            answer = ""
            async for token in callback.aiter():
                answer += str(token)
            yield json.dumps({"message_id": message_id, "conversation_id": conversation_id, "answer": answer,
                              "docs": source_documents}, ensure_ascii=False)
        await task

    return EventSourceResponse(wrap_event_response(search_engine_chat_iterator(query=query,
                                                                               search_engine_name=search_engine_name,
                                                                               top_k=top_k,
                                                                               history=history,
                                                                               model_name=model_name,
                                                                               prompt_name=prompt_name),
                                                   ))
