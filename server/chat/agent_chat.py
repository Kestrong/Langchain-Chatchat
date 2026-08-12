import asyncio
import json
import uuid
from typing import AsyncIterable, Optional, List, Dict, Any, Union

from fastapi import Body
from starlette.requests import Request

from configs import LLM_MODELS, TEMPERATURE, HISTORY_LEN, logger, TOP_P
from server.agent import create_model_container
from server.agent.callbacks import AgentExecutorAsyncIteratorCallbackHandler, AgentStatus
from server.agent.tools_select import get_available_tools
from server.callback_handler.conversation_callback_handler import ConversationCallbackHandler
from server.callback_handler.task_callback_handler import TaskCallbackHandler
from server.callback_handler.token_callback_handler import TokenCallbackHandler
from server.chat.chat import process_extra
from server.chat.chat_type import ChatType
from server.chat.customize_agent.customize_agent_type import customize_agent_types
from server.chat.task_manager import task_manager
from server.chat.utils import History, un_format_online_llm_model, create_agent_executor, \
    parse_llm_token_inner_json, choose_response, unify_chat_files, get_tiktoken_num
from server.db.repository import add_message_to_db
from server.memory.conversation_db_buffer_memory import ConversationBufferDBMemory
from server.memory.conversation_window_buffer_memory import ConversationBufferWindowMemory
from server.memory.message_i18n import Message_I18N
from server.utils import wrap_done, get_ChatOpenAI, get_prompt_template, BaseResponse


async def agent_chat(query: str = Body(..., description="用户输入", examples=["恼羞成怒"]),
                     tag: str = Body(default="", description="会话标签"),
                     extra: Dict[str, Any] = Body({}, description="额外的属性"),
                     assistant_id: int = Body(-1, description="助手ID"),
                     knowledge_id: str = Body("", description="临时知识库ID"),
                     conversation_id: str = Body("", description="对话框ID"),
                     history_len: int = Body(-1, description="从数据库中取历史消息的数量"),
                     history: List[History] = Body([],
                                                   description="历史对话",
                                                   examples=[[
                                                       {"role": "user", "content": "请使用知识库工具查询今天北京天气"},
                                                       {"role": "assistant",
                                                        "content": "使用天气查询工具查询到今天北京多云，10-14摄氏度，东北风2级，易感冒"}]]
                                                   ),
                     stream: bool = Body(False, description="流式输出"),
                     model_name: str = Body(LLM_MODELS[0], description="LLM 模型名称。"),
                     temperature: float = Body(TEMPERATURE, description="LLM 采样温度", ge=0.0, le=1.0),
                     max_tokens: Optional[int] = Body(None, description="限制LLM生成Token数量，默认None代表模型最大值"),
                     top_p: float = Body(TOP_P, description="LLM 核采样。勿与temperature同时设置", gt=0.0, lt=1.0),
                     prompt_name: str = Body("default",
                                             description="使用的prompt模板名称(在configs/prompt_config.py中配置)"),
                     tool_names: List[str] = Body([], description="工具的名称"),
                     store_message: bool = Body(True, description="是否保存消息到数据库"),
                     request: Request = None
                     ):
    if not conversation_id:
        conversation_id = uuid.uuid4().hex
    customize_agent_type = extra.get("customize_agent_type") if extra else None
    if customize_agent_type and customize_agent_type in customize_agent_types:
        return await customize_agent_types.get(customize_agent_type)(query=query, history_len=history_len, tag=tag,
                                                                     history=history, tool_names=tool_names,
                                                                     stream=stream, model_name=model_name, extra=extra,
                                                                     temperature=temperature, assistant_id=assistant_id,
                                                                     conversation_id=conversation_id, top_p=top_p,
                                                                     store_message=store_message, max_tokens=max_tokens,
                                                                     prompt_name=prompt_name, request=request,
                                                                     knowledge_id=knowledge_id)
    un_format = un_format_online_llm_model(model_name)
    chat_type = ChatType.AGENT_CHAT.value
    history = [History.from_data(h) for h in history]
    model_container = create_model_container()
    available_tools, _ = await get_available_tools(tool_names)

    if not available_tools:
        return BaseResponse(code=500, msg=Message_I18N.API_TOOL_NOT_FOUND.value)
    chat_files = unify_chat_files(third_party_files=extra.pop('files', []), knowledge_id=knowledge_id, request=request)

    async def agent_chat_iterator(
            query: str,
            history: Optional[List[History]],
            model_name: str = LLM_MODELS[0],
            prompt_name: str = prompt_name,
    ) -> AsyncIterable[str]:
        nonlocal max_tokens
        callback = AgentExecutorAsyncIteratorCallbackHandler(model_name=model_name, )
        if isinstance(max_tokens, int) and max_tokens <= 0:
            max_tokens = None

        callbacks = [callback]
        message_id = add_message_to_db(chat_type=chat_type, query=query, conversation_id=conversation_id, tag=tag,
                                       store=store_message, assistant_id=assistant_id,
                                       metadata={'chat_files': chat_files} if chat_files else {}, )
        conversation_callback = ConversationCallbackHandler(model_name=model_name, conversation_id=conversation_id,
                                                            message_id=message_id, chat_type=chat_type,
                                                            query=query, agent=True, stream=stream)
        task_callback = TaskCallbackHandler(conversation_id=conversation_id, message_id=message_id, agent=True)
        token_callback = TokenCallbackHandler(model_name=model_name, message_id=message_id)
        callbacks.extend([conversation_callback, task_callback, token_callback])
        model_container.CALLBACK_HANDLERS.append(token_callback)
        # Enable langchain-chatchat to support langfuse
        import os
        langfuse_secret_key = os.environ.get('LANGFUSE_SECRET_KEY')
        langfuse_public_key = os.environ.get('LANGFUSE_PUBLIC_KEY')
        langfuse_host = os.environ.get('LANGFUSE_HOST')
        if langfuse_secret_key and langfuse_public_key and langfuse_host:
            from langfuse.callback import CallbackHandler
            langfuse_handler = CallbackHandler()
            callbacks.append(langfuse_handler)

        process_extra(stream=stream, model_name=model_name, extra=extra, conversation_id=conversation_id,
                      request=request)

        model_container.EXTRA_ARGS.update(extra)

        model = get_ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            callbacks=[],
            top_p=top_p,
            enable_thinking=False,
            extra_body={"extra": extra} if un_format else None,
        )

        prompt_template = get_prompt_template(chat_type, prompt_name)
        in_tuple = History(role="user", content=query, chat_files=chat_files).get_content_tuple(
            format_openai=not un_format)
        input_content, image_urls, input_len, _ = in_tuple
        input_template = History(role="user", content=prompt_template, ).to_msg_template(format_openai=not un_format,
                                                                                         image_urls=image_urls)
        prompt_length = input_len + get_tiktoken_num(prompt_template + str(available_tools))
        memory = ConversationBufferWindowMemory(model_name=model_name, return_messages=True,
                                                message_limit=max(HISTORY_LEN * 2, len(history) if history else 0),
                                                prompt_length=prompt_length)
        if history:
            for message in history:
                if message.role in ["user", "human"]:
                    memory.chat_memory.add_user_message(message.to_msg_tuple(format_openai=not un_format)[1])
                else:
                    memory.chat_memory.add_ai_message(message.content)
        elif conversation_id and history_len > 0:
            memory = ConversationBufferDBMemory(conversation_id=conversation_id,
                                                model_name=model_name, return_messages=True,
                                                prompt_length=prompt_length,
                                                message_limit=history_len)
        agent_executor = create_agent_executor(model, memory, available_tools, input_template)
        while True:
            try:
                task = asyncio.create_task(wrap_done(
                    agent_executor.acall({"input": input_content}, callbacks=callbacks, include_run_info=True),
                    callback.done))
                break
            except:
                pass
        task_manager.put(message_id, task)

        d = {"event": "agent_message", "message_id": message_id, "conversation_id": conversation_id, "answer": ""}
        yield json.dumps(d, ensure_ascii=False)
        if not extra.get('backend'):
            if stream:
                async for chunk in callback.aiter():
                    # Use server-sent-events to stream the response
                    data = json.loads(parse_llm_token_inner_json(model_name, chunk)["answer"])
                    if data["status"] == AgentStatus.llm_start or data["status"] == AgentStatus.llm_end:
                        continue
                    elif data["status"] == AgentStatus.error:
                        use_tool_name = data.get("tool_name") or "unknown"
                        use_tool = [a for a in available_tools if a.name == use_tool_name]
                        thought = Message_I18N.API_AGENT_TOOL_ERROR_INFO.value.format(
                            tool_name=f"{use_tool[0].title}({use_tool[0].name})" if use_tool else use_tool_name,
                            error=data["error"])
                        yield json.dumps(
                            {"event": "agent_thought", "thought": thought, "message_id": message_id,
                             "conversation_id": conversation_id}, ensure_ascii=False)
                    elif data["status"] == AgentStatus.tool_end:
                        use_tool_name = data["tool_name"]
                        use_tool = [a for a in available_tools if a.name == use_tool_name]
                        thought = Message_I18N.API_AGENT_TOOL_SUCCESS_INFO.value.format(
                            tool_name=f"{use_tool[0].title}({use_tool[0].name})" if use_tool else use_tool_name,
                            input_str=str(data.get("input_str")),
                            output_str=str(data.get("output_str")))
                        yield json.dumps(
                            {"event": "agent_thought", "thought": thought, "message_id": message_id,
                             "conversation_id": conversation_id},
                            ensure_ascii=False)
                    elif data["status"] == AgentStatus.agent_finish:
                        final_answer = data["final_answer"]
                        yield json.dumps({"event": "agent_message", "answer": final_answer, "message_id": message_id,
                                          "conversation_id": conversation_id}, ensure_ascii=False)
                    else:
                        yield json.dumps(
                            {"event": "agent_thought", "thought": data["llm_token"], "message_id": message_id,
                             "conversation_id": conversation_id},
                            ensure_ascii=False)
                yield json.dumps({"event": "message_end", "message_id": message_id, "conversation_id": conversation_id,
                                  "total_tokens": token_callback.total_tokens}, ensure_ascii=False)
            else:
                answer = ""
                thought = ""
                async for chunk in callback.aiter():
                    data = json.loads(parse_llm_token_inner_json(model_name, chunk)["answer"])
                    if data["status"] == AgentStatus.llm_start or data["status"] == AgentStatus.llm_end:
                        continue
                    elif data["status"] == AgentStatus.error:
                        use_tool_name = data["tool_name"]
                        use_tool = [a for a in available_tools if a.name == use_tool_name]
                        thought += Message_I18N.API_AGENT_TOOL_ERROR_INFO.value.format(
                            tool_name=f"{use_tool[0].title}({use_tool[0].name})" if use_tool else use_tool_name,
                            error=data["error"])
                    elif data["status"] == AgentStatus.tool_end:
                        use_tool_name = data["tool_name"]
                        use_tool = [a for a in available_tools if a.name == use_tool_name]
                        thought += Message_I18N.API_AGENT_TOOL_SUCCESS_INFO.value.format(
                            tool_name=f"{use_tool[0].title}({use_tool[0].name})" if use_tool else use_tool_name,
                            input_str=str(data.get("input_str")),
                            output_str=str(data.get("output_str")))
                    elif data["status"] == AgentStatus.agent_finish:
                        answer += data["final_answer"]
                    else:
                        thought += data["llm_token"]

                yield json.dumps(
                    {"event": "agent_message", "thought": thought, "answer": answer, "message_id": message_id,
                     "conversation_id": conversation_id, "total_tokens": token_callback.total_tokens},
                    ensure_ascii=False)
        await task

    return await choose_response(stream, agent_chat_iterator(query=query,
                                                             history=history,
                                                             model_name=model_name,
                                                             prompt_name=prompt_name), request)


async def do_call_tool_chain(walk_results: List[Any], tool_name: str, child_tool_name: str,
                             extra: Union[Dict[str, Any], Any]):
    available_tools, _ = await get_available_tools(tool_name_ens=[tool_name])
    if len(available_tools) == 0:
        return None
    api_results = []
    for a in available_tools:
        if child_tool_name and child_tool_name != a.name:
            continue
        tool_input = {}
        if isinstance(extra, dict):
            tool_input.update(extra)
        else:
            for k, v in a.args.items():
                if k not in tool_input and isinstance(extra, type(v.get("type"))):
                    tool_input[k] = extra
                    break
        result = await a.ainvoke(tool_input)
        api_results.append(result)
    if len(available_tools) == 1:
        api_results = api_results[0]
    results = api_results
    walk_results.append(api_results)
    return results


async def call_tool(
        tool_name: str = Body(examples=["calculate"], description="工具名称"),
        child_tool_name: str = Body(default=None, description="子工具名称"),
        tool_input: Dict[str, Any] = Body({}, examples=[{"expression": "3+5/2"}]),
) -> BaseResponse:
    try:
        if not tool_name:
            return BaseResponse(code=500, msg=Message_I18N.API_TOOL_NOT_FOUND.value)
        model_container = create_model_container()
        if tool_input:
            model_container.EXTRA_ARGS.update(tool_input)
        walk_results = []
        result = await do_call_tool_chain(walk_results=walk_results,
                                          tool_name=tool_name,
                                          child_tool_name=child_tool_name,
                                          extra=tool_input)
        walk_results.reverse()
        logger.debug(f"walk_results:{walk_results}")
        return BaseResponse(code=200, data=result)
    except Exception as e:
        logger.error(f"{e}")
        return BaseResponse(code=500, msg=Message_I18N.COMMON_CALL_FAILED.value)
