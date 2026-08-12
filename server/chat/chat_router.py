from typing import List, Optional, Union, Dict, Any

from fastapi import Body, BackgroundTasks
from starlette.requests import Request

from configs import LLM_MODELS, TEMPERATURE, VECTOR_SEARCH_TOP_K, SCORE_THRESHOLD, HISTORY_LEN, TOP_P
from server.chat.agent_chat import agent_chat
from server.chat.chat import chat
from server.chat.chat_type import ChatType
from server.chat.completion import completion
from server.chat.knowledge_base_chat import knowledge_base_chat
from server.chat.search_engine_chat import search_engine_chat
from server.chat.utils import History
from server.chat.workflow_chat import do_workflow_chat
from server.db.repository import get_assistant_detail_from_db
from server.knowledge_base.oss import default_oss
from server.utils import get_chat_file_kb


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
                      request: Request = None,
                      background_tasks: BackgroundTasks = None,
                      ):
    assistant = None
    workflow_config = None
    if assistant_id >= 0:
        assistant = get_assistant_detail_from_db(assistant_id=assistant_id)
        workflow_config = assistant.get("workflow_config", {})
    if chat_type == ChatType.WORKFLOW_CHAT.value or (workflow_config is not None and len(workflow_config) > 0):
        return await do_workflow_chat(query=query, stream=stream, assistant_id=assistant_id, knowledge_id=knowledge_id,
                                      conversation_id=conversation_id, extra=extra, store_message=store_message,
                                      workflow_config=workflow_config, tag=tag, request=request)
    return await do_chat_router(query=query, chat_type=chat_type, extra=extra, conversation_id=conversation_id,
                                assistant_id=assistant_id, assistant=assistant, knowledge_id=knowledge_id,
                                knowledge_base_names=knowledge_base_names, search_engine_name=search_engine_name,
                                top_k=top_k, score_threshold=score_threshold, history_len=history_len, history=history,
                                stream=stream, model_name=model_name, tag=tag, top_p=top_p,
                                temperature=temperature, max_tokens=max_tokens, prompt_name=prompt_name,
                                store_message=store_message, split_result=split_result, tool_names=tool_names,
                                request=request, background_tasks=background_tasks)


def check_file_type(knowledge_id: str = "", third_party_files: list = None, uploader: dict = None):
    if not uploader:
        return True
    allowed_types = uploader.get("allowed_types")
    if not allowed_types:
        return True
    msg = f"File type not allowed. Please upload files in {allowed_types} format."
    if knowledge_id:
        files = default_oss().list_objects(bucket_name=get_chat_file_kb(), object_name=knowledge_id)
        for filename in files:
            ext = filename.rsplit('.', 1)[-1].strip() if filename and '.' in filename else ''
            if ext not in allowed_types:
                raise ValueError(msg)
    if third_party_files:
        for f in third_party_files:
            filename = f.get("name")
            ext = filename.rsplit('.', 1)[-1].strip() if filename and '.' in filename else ''
            if ext not in allowed_types:
                raise ValueError(msg)


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
                         request: Request = None,
                         background_tasks: BackgroundTasks = None,
                         ):
    if assistant is None and assistant_id >= 0:
        assistant = get_assistant_detail_from_db(assistant_id=assistant_id)
    if assistant:
        check_file_type(knowledge_id=knowledge_id, third_party_files=extra.get("files"),
                        uploader=assistant.get("model_config", {}).get("uploader", {}))
        if assistant.get('extra') is not None:
            extra.update(assistant.get('extra'))
        extra['assistant_id'] = assistant_id
        if default_value_from_assistant:
            if assistant.get('model_name'):
                model_name = assistant.get('model_name')
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
                tool_names = tool_config_db.get("tool_names", [])

    if chat_type == ChatType.SEARCH_ENGINE_CHAT.value or (
            search_engine_name is not None and search_engine_name != ''):

        return await search_engine_chat(query=query, conversation_id=conversation_id, store_message=store_message,
                                        search_engine_name=search_engine_name, top_k=top_k, assistant_id=assistant_id,
                                        history_len=history_len, history=history, stream=stream, model_name=model_name,
                                        temperature=temperature, max_tokens=max_tokens, prompt_name=prompt_name,
                                        split_result=split_result, tag=tag, extra=extra, top_p=top_p, request=request,
                                        knowledge_id=knowledge_id)

    elif chat_type == ChatType.AGENT_CHAT.value or tool_names:

        return await agent_chat(query=query, history_len=history_len, history=history, stream=stream,
                                model_name=model_name, temperature=temperature, tool_names=tool_names,
                                conversation_id=conversation_id, extra=extra, top_p=top_p, knowledge_id=knowledge_id,
                                store_message=store_message, max_tokens=max_tokens, prompt_name=prompt_name,
                                assistant_id=assistant_id, tag=tag, request=request, )

    elif chat_type == ChatType.KNOWLEDGE_BASE_CHAT.value or knowledge_base_names:

        return await knowledge_base_chat(query=query, conversation_id=conversation_id, assistant_id=assistant_id,
                                         knowledge_base_names=knowledge_base_names, top_k=top_k, extra=extra,
                                         score_threshold=score_threshold, history_len=history_len, history=history,
                                         stream=stream, model_name=model_name, temperature=temperature, tag=tag,
                                         max_tokens=max_tokens, prompt_name=prompt_name, store_message=store_message,
                                         top_p=top_p, background_tasks=background_tasks, request=request,
                                         knowledge_id=knowledge_id)

    elif chat_type == ChatType.COMPLETION.value:

        return await completion(query=query, assistant_id=assistant_id, tag=tag, extra=extra, stream=stream,
                                top_p=top_p, model_name=model_name, temperature=temperature, max_tokens=max_tokens,
                                prompt_name=prompt_name, store_message=store_message, request=request, )

    else:

        return await chat(query=query, extra=extra, conversation_id=conversation_id, tag=tag, top_p=top_p,
                          history_len=history_len, history=history, stream=stream, request=request,
                          model_name=model_name, temperature=temperature, max_tokens=max_tokens,
                          prompt_name=prompt_name, store_message=store_message, assistant_id=assistant_id,
                          knowledge_id=knowledge_id)
