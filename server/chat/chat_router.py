from typing import List, Optional, Union, Dict, Any

from fastapi import Body
from starlette.requests import Request

from configs import LLM_MODELS, TEMPERATURE, VECTOR_SEARCH_TOP_K, SCORE_THRESHOLD, HISTORY_LEN, TOP_P
from server.agent import create_model_container
from server.chat.agent_chat import agent_chat, tool_chat
from server.chat.chat import chat
from server.chat.chat_type import ChatType
from server.chat.completion import completion
from server.chat.file_chat import file_chat
from server.chat.knowledge_base_chat import knowledge_base_chat
from server.chat.search_engine_chat import search_engine_chat
from server.chat.utils import History, un_format_online_llm_model
from server.chat.workflow_chat import do_workflow_chat
from server.db.repository import get_assistant_detail_from_db
from server.memory.token_info_memory import get_token


async def chat_router(query: str = Body(..., description="用户输入", examples=["恼羞成怒"]),
                      chat_type: str = Body(ChatType.LLM_CHAT.value,
                                            description=f"对话类型:{[c.value for c in ChatType]}"),
                      tag: str = Body(default="", description="会话标签"),
                      extra: Dict[str, Any] = Body({}, description="额外的属性"),
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
                      max_tokens: Optional[int] = Body(None,
                                                       description="限制LLM生成Token数量，默认None代表模型最大值"),
                      top_p: float = Body(TOP_P, description="LLM 核采样。勿与temperature同时设置", gt=0.0, lt=1.0),
                      prompt_name: str = Body("default",
                                              description="使用的prompt模板名称(在configs/prompt_config.py中配置)"),
                      store_message: bool = Body(True, description="是否保存消息到数据库"),
                      split_result: bool = Body(False,
                                                description="是否对搜索结果进行拆分（主要用于metaphor搜索引擎）"),
                      tool_names: List[str] = Body([], description="工具的名称"),
                      api_names: List[str] = Body([], description="api的名称"),
                      request: Request = None
                      ):
    assistant = None
    workflow_config = None
    if assistant_id >= 0:
        assistant = get_assistant_detail_from_db(assistant_id=assistant_id)
        workflow_config = assistant.get("workflow_config", {})
    if chat_type == ChatType.WORKFLOW_CHAT.value or (workflow_config is not None and len(workflow_config) > 0):
        return await do_workflow_chat(query=query, stream=stream, assistant_id=assistant_id, knowledge_id=knowledge_id,
                                      conversation_id=conversation_id, extra=extra, store_message=store_message,
                                      workflow_config=workflow_config, tag=tag)
    return await do_chat_router(query=query, chat_type=chat_type, extra=extra, conversation_id=conversation_id,
                                assistant_id=assistant_id, assistant=assistant, knowledge_id=knowledge_id,
                                knowledge_base_names=knowledge_base_names, search_engine_name=search_engine_name,
                                top_k=top_k, score_threshold=score_threshold, history_len=history_len, history=history,
                                stream=stream, model_name=model_name, tag=tag, top_p=top_p,
                                temperature=temperature, max_tokens=max_tokens, prompt_name=prompt_name,
                                store_message=store_message, split_result=split_result, tool_names=tool_names,
                                api_names=api_names, request=request)


async def do_chat_router(query: str,
                         chat_type: str = ChatType.LLM_CHAT.value,
                         tag: str = "",
                         extra: Dict[str, Any] = None,
                         conversation_id: str = None,
                         assistant_id: int = -1,
                         assistant: dict = None,
                         default_value_from_assistant: bool = True,
                         knowledge_id: str = "",
                         knowledge_base_names: List[str] = None,
                         search_engine_name: str = None,
                         top_k: int = VECTOR_SEARCH_TOP_K,
                         score_threshold: float = SCORE_THRESHOLD,
                         history_len: int = -1,
                         history: Union[int, List[History]] = None,
                         stream: bool = False,
                         model_name: str = LLM_MODELS[0],
                         temperature: float = TEMPERATURE,
                         max_tokens: Optional[int] = None,
                         top_p: float = TOP_P,
                         prompt_name: str = "default",
                         store_message: bool = True,
                         split_result: bool = False,
                         tool_names: List[str] = None,
                         api_names: List[str] = None,
                         request: Request = None
                         ):
    if un_format_online_llm_model(model_name):
        extra["knowledge_id"] = knowledge_id
        extra["token"] = get_token()
    if assistant is None and assistant_id >= 0:
        assistant = get_assistant_detail_from_db(assistant_id=assistant_id)
    if assistant:
        if assistant.get('extra') is not None:
            extra.update(assistant.get('extra'))
        extra['assistant_id'] = assistant_id
        if default_value_from_assistant:
            if not knowledge_base_names:
                kbs = assistant.get("knowledge_bases", [])
                if kbs:
                    knowledge_base_names = [kb["kb_name"] for kb in kbs]
            prompt = assistant.get('prompt')
            if prompt is not None and prompt.strip() != '':
                prompt_name = prompt
            config_history_len: int = assistant.get('history_len', HISTORY_LEN)
            if history:
                if config_history_len == 0:
                    history.clear()
                elif 0 < config_history_len < len(history):
                    history = history[-config_history_len:]
            elif history_len > 0:
                history_len = min(history_len, config_history_len) if config_history_len >= 0 else history_len
            elif config_history_len > 0:
                history_len = config_history_len
            top_k = assistant.get("top_k") if assistant.get("top_k", -1) > 0 else top_k
            if assistant.get("score_threshold", -1) > 0:
                score_threshold = assistant.get("score_threshold")
            tool_config_db = assistant.get("tool_config", {})
            if not tool_names and tool_config_db is not None and len(tool_config_db) > 0:
                tool_names = [k for k, v in assistant.get("tool_config").items() if v.get("selected", False)]
                api_names = [t.get("name") for t in assistant.get("tool_config").get("http_request", {}).get("apis", [])
                             if
                             t.get("selected", False)]

    if chat_type == ChatType.SEARCH_ENGINE_CHAT.value or (
            search_engine_name is not None and search_engine_name != ''):

        return await search_engine_chat(query=query, conversation_id=conversation_id, store_message=store_message,
                                        search_engine_name=search_engine_name, top_k=top_k, assistant_id=assistant_id,
                                        history_len=history_len, history=history, stream=stream, model_name=model_name,
                                        temperature=temperature, max_tokens=max_tokens, prompt_name=prompt_name,
                                        split_result=split_result, tag=tag, extra=extra, top_p=top_p)

    elif chat_type == ChatType.AGENT_CHAT.value or tool_names:
        if assistant:
            tool_config = assistant.get("tool_config")
            if tool_config and len(tool_config) > 0:
                model_container = create_model_container()
                model_container.TOOL_CONFIG.update(tool_config)
                if len(tool_names) == 1 and tool_config.get(tool_names[0], {}).get("call_direct", False):
                    return await tool_chat(query=query, knowledge_id=knowledge_id, conversation_id=conversation_id,
                                           extra=extra, tool_names=tool_names, api_names=api_names,
                                           store_message=store_message, assistant_id=assistant_id, tag=tag)

        return await agent_chat(query=query, history_len=history_len, history=history, stream=stream,
                                model_name=model_name, temperature=temperature, tool_names=tool_names,
                                conversation_id=conversation_id, extra=extra, top_p=top_p,
                                store_message=store_message, max_tokens=max_tokens, prompt_name=prompt_name,
                                api_names=api_names, assistant_id=assistant_id, tag=tag)

    elif chat_type == ChatType.FILE_CHAT.value or (knowledge_id and not un_format_online_llm_model(model_name)):

        return await file_chat(query=query, knowledge_id=knowledge_id, history_len=history_len, history=history,
                               stream=stream, model_name=model_name, temperature=temperature, max_tokens=max_tokens,
                               prompt_name=prompt_name, conversation_id=conversation_id, store_message=store_message,
                               assistant_id=assistant_id, tag=tag, extra=extra, top_p=top_p, )

    elif chat_type == ChatType.KNOWLEDGE_BASE_CHAT.value or knowledge_base_names:

        return await knowledge_base_chat(query=query, conversation_id=conversation_id, assistant_id=assistant_id,
                                         knowledge_base_names=knowledge_base_names, top_k=top_k, extra=extra,
                                         score_threshold=score_threshold, history_len=history_len, history=history,
                                         stream=stream, model_name=model_name, temperature=temperature, tag=tag,
                                         max_tokens=max_tokens, prompt_name=prompt_name, store_message=store_message,
                                         top_p=top_p, )

    elif chat_type == ChatType.COMPLETION.value:

        return await completion(query=query, extra=extra, stream=stream, top_p=top_p,
                                model_name=model_name, temperature=temperature, max_tokens=max_tokens,
                                prompt_name=prompt_name)

    else:

        return await chat(query=query, extra=extra, conversation_id=conversation_id, tag=tag, top_p=top_p,
                          history_len=history_len, history=history, stream=stream, request=request,
                          model_name=model_name, temperature=temperature, max_tokens=max_tokens,
                          prompt_name=prompt_name, store_message=store_message, assistant_id=assistant_id)
