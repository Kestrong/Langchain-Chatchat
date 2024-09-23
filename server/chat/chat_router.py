from typing import List, Optional, Union

from fastapi import Body

from configs import LLM_MODELS, TEMPERATURE, VECTOR_SEARCH_TOP_K, SCORE_THRESHOLD
from server.agent import create_model_container
from server.chat.agent_chat import agent_chat
from server.chat.chat import chat
from server.chat.chat_type import ChatType
from server.chat.completion import completion
from server.chat.file_chat import file_chat
from server.chat.knowledge_base_chat import knowledge_base_chat
from server.chat.search_engine_chat import search_engine_chat
from server.chat.utils import History
from server.db.repository import get_assistant_detail_from_db


async def chat_router(query: str = Body(..., description="用户输入", examples=["恼羞成怒"]),
                      chat_type: str = Body(ChatType.LLM_CHAT, description=f"对话类型:{[c.value for c in ChatType]}"),
                      extra: dict = Body({}, description="额外的属性"),
                      conversation_id: str = Body("", description="对话框ID"),
                      assistant_id: int = Body(-1, description="助手ID"),
                      knowledge_id: str = Body("", description="临时知识库ID"),
                      knowledge_base_names: List[str] = Body([], description="知识库名称", examples=[["samples"]]),
                      search_engine_name: str = Body(None, description="搜索引擎名称", examples=["duckduckgo"]),
                      top_k: int = Body(VECTOR_SEARCH_TOP_K, description="匹配向量数"),
                      score_threshold: float = Body(
                          SCORE_THRESHOLD,
                          description="知识库匹配相关度阈值，取值范围在0-1之间，SCORE越小，相关度越高，取到1相当于不筛选，建议设置在0.5左右",
                          ge=0,
                          le=2
                      ),
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
                      # top_p: float = Body(TOP_P, description="LLM 核采样。勿与temperature同时设置", gt=0.0, lt=1.0),
                      prompt_name: str = Body("default",
                                              description="使用的prompt模板名称(在configs/prompt_config.py中配置)"),
                      store_message: bool = Body(True, description="是否保存消息到数据库"),
                      split_result: bool = Body(False,
                                                description="是否对搜索结果进行拆分（主要用于metaphor搜索引擎）"),
                      tool_names: List[str] = Body([], description="工具的名称"),
                      api_names: List[str] = Body([], description="api的名称"),
                      ):
    assistant = None
    if assistant_id >= 0:
        assistant = get_assistant_detail_from_db(assistant_id=assistant_id)
        kbs = assistant.get("knowledge_bases", [])
        if kbs:
            knowledge_base_names = [kb["kb_name"] for kb in kbs]
        prompt = assistant.get('prompt')
        if prompt is not None and prompt.strip() != '':
            prompt_name = '[*safe_prompt*]' + prompt + '[*safe_prompt*]'
        if assistant.get('extra') is not None:
            extra.update(assistant.get('extra'))
        extra['assistant_id'] = assistant_id

    if chat_type == ChatType.KNOWLEDGE_BASE_CHAT.value or knowledge_base_names:

        return await knowledge_base_chat(query=query, conversation_id=conversation_id,
                                         knowledge_base_names=knowledge_base_names, top_k=top_k,
                                         score_threshold=score_threshold, history=history, stream=stream,
                                         model_name=model_name, temperature=temperature, max_tokens=max_tokens,
                                         prompt_name=prompt_name, store_message=store_message)

    elif chat_type == ChatType.SEARCH_ENGINE_CHAT.value or (
            search_engine_name is not None and search_engine_name != ''):

        return await search_engine_chat(query=query, conversation_id=conversation_id, store_message=store_message,
                                        search_engine_name=search_engine_name, top_k=top_k,
                                        history=history, stream=stream, model_name=model_name, temperature=temperature,
                                        max_tokens=max_tokens, prompt_name=prompt_name, split_result=split_result)

    elif chat_type == ChatType.AGENT_CHAT.value or tool_names:
        if assistant:
            tool_config = assistant.get("tool_config")
            if tool_config and len(tool_config) > 0:
                model_container = create_model_container()
                model_container.TOOL_CONFIG.update(tool_config)
        return await agent_chat(query=query, history=history, stream=stream, model_name=model_name,
                                temperature=temperature, tool_names=tool_names, conversation_id=conversation_id,
                                store_message=store_message, max_tokens=max_tokens, prompt_name=prompt_name,
                                api_names=api_names)

    elif chat_type == ChatType.FILE_CHAT.value or knowledge_id:
        return await file_chat(query=query, knowledge_id=knowledge_id, history=history, stream=stream,
                               model_name=model_name, temperature=temperature, max_tokens=max_tokens,
                               prompt_name=prompt_name, conversation_id=conversation_id, store_message=store_message, )

    elif chat_type == ChatType.COMPLETION.value:

        return await completion(query=query, extra=extra, stream=stream,
                                model_name=model_name, temperature=temperature, max_tokens=max_tokens,
                                prompt_name=prompt_name)

    else:

        return await chat(query=query, extra=extra, conversation_id=conversation_id,
                          history_len=history_len, history=history, stream=stream,
                          model_name=model_name, temperature=temperature, max_tokens=max_tokens,
                          prompt_name=prompt_name, store_message=store_message)
