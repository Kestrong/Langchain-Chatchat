import asyncio
import json
from typing import AsyncIterable, Optional, List, Dict, Any

from fastapi import Body
from langchain.agents import AgentExecutor, LLMSingleActionAgent
from langchain.agents.structured_chat.output_parser import StructuredChatOutputParserWithRetries
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferWindowMemory
from sse_starlette.sse import EventSourceResponse

from configs import LLM_MODELS, TEMPERATURE, HISTORY_LEN, logger
from server.agent import create_model_container, ModelContainer
from server.agent.callbacks import AgentExecutorAsyncIteratorCallbackHandler, AgentStatus
from server.agent.custom_agent.ChatGLM3Agent import initialize_glm3_agent
from server.agent.custom_template import CustomOutputParser, CustomPromptTemplate
from server.agent.tools.http_request import _http_request
from server.agent.tools_select import get_all_tools, get_tool, create_dynamic_tool
from server.callback_handler.conversation_callback_handler import ConversationCallbackHandler
from server.callback_handler.task_callback_handler import TaskCallbackHandler
from server.chat.chat_type import ChatType
from server.chat.task_manager import task_manager
from server.chat.utils import History, UN_FORMAT_ONLINE_LLM_MODELS, wrap_event_response
from server.db.repository import add_message_to_db, get_assistant_simple_from_db
from server.memory.message_i18n import Message_I18N
from server.utils import wrap_done, get_ChatOpenAI, get_prompt_template, BaseResponse, get_tool_config


def get_available_tools(tool_names: List[str], api_names: List[str], model_container: ModelContainer, ):
    if tool_names is not None and len(tool_names) > 0:
        available_tools = []
        for tool_name in tool_names:
            if tool_name == 'http_request':
                apis = model_container.TOOL_CONFIG.get("http_request",
                                                       get_tool_config().TOOL_CONFIG.get("http_request", {})).get(
                    "apis", [])
                available_tools.extend([create_dynamic_tool(api, _http_request) for api in apis if
                                        not api_names or api.get("name") in api_names])
            else:
                t = get_tool(tool_name)
                if t:
                    available_tools.append(t)
    else:
        available_tools = get_all_tools()
    return available_tools


async def agent_chat(query: str = Body(..., description="用户输入", examples=["恼羞成怒"]),
                     conversation_id: str = Body("", description="对话框ID"),
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
                     prompt_name: str = Body("default",
                                             description="使用的prompt模板名称(在configs/prompt_config.py中配置)"),
                     tool_names: List[str] = Body([], description="工具的名称"),
                     api_names: List[str] = Body([], description="api的名称"),
                     store_message: bool = Body(True, description="是否保存消息到数据库"),
                     ):
    if model_name in UN_FORMAT_ONLINE_LLM_MODELS:
        return BaseResponse(code=500,
                            msg=Message_I18N.API_CHAT_TYPE_NOT_SUPPORT.value.format(chat_type=ChatType.AGENT_CHAT.value,
                                                                                    model_name=model_name))

    history = [History.from_data(h) for h in history]
    model_container = create_model_container()
    available_tools = get_available_tools(tool_names, api_names, model_container)

    if not available_tools:
        return BaseResponse(code=500, msg=Message_I18N.API_TOOL_NOT_FOUND.value)
    available_tool_names = [t.name for t in available_tools]

    async def agent_chat_iterator(
            query: str,
            history: Optional[List[History]],
            model_name: str = LLM_MODELS[0],
            prompt_name: str = prompt_name,
    ) -> AsyncIterable[str]:
        nonlocal max_tokens
        callback = AgentExecutorAsyncIteratorCallbackHandler()
        if isinstance(max_tokens, int) and max_tokens <= 0:
            max_tokens = None

        callbacks = [callback]
        message_id = add_message_to_db(chat_type=ChatType.AGENT_CHAT.value, query=query,
                                       conversation_id=conversation_id,
                                       store=store_message)
        conversation_callback = ConversationCallbackHandler(model_name=model_name, conversation_id=conversation_id,
                                                            message_id=message_id, chat_type=ChatType.AGENT_CHAT.value,
                                                            query=query, agent=True)
        task_callback = TaskCallbackHandler(conversation_id=conversation_id, message_id=message_id, agent=True)
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

        prompt_template = get_prompt_template("agent_chat", prompt_name)
        prompt_template_agent = CustomPromptTemplate(
            template=prompt_template,
            tools=available_tools,
            template_format='jinja2',
            input_variables=["input", "intermediate_steps"]
        )
        llm_chain = LLMChain(llm=model, prompt=prompt_template_agent)
        memory = ConversationBufferWindowMemory(k=max(HISTORY_LEN * 2, len(history) if history else 0))
        for message in history:
            if message.role == 'user':
                memory.chat_memory.add_user_message(message.content)
            else:
                memory.chat_memory.add_ai_message(message.content)
        if "chatglm3" in model_name or "zhipu-api" in model_name:
            agent_executor = initialize_glm3_agent(
                llm=model,
                tools=available_tools,
                callback_manager=None,
                prompt=prompt_template,
                input_variables=["input", "intermediate_steps"],
                memory=memory,
                verbose=True,
            )
        else:
            output_parser = StructuredChatOutputParserWithRetries.from_llm(llm=model, base_parser=CustomOutputParser())
            output_parser.output_fixing_parser.max_retries = 3
            agent = LLMSingleActionAgent(
                llm_chain=llm_chain,
                output_parser=output_parser,
                stop=["Observation:", "\nObservation", "<|endoftext|>", "<|im_start|>", "<|im_end|>"],
                allowed_tools=available_tool_names,
            )
            agent_executor = AgentExecutor.from_agent_and_tools(agent=agent,
                                                                tools=available_tools,
                                                                verbose=True,
                                                                memory=memory,
                                                                )
        while True:
            try:
                task = asyncio.create_task(wrap_done(
                    agent_executor.acall(query, callbacks=callbacks, include_run_info=True),
                    callback.done))
                break
            except:
                pass
        task_manager.put(message_id, task)

        d = {"message_id": message_id, "conversation_id": conversation_id, "answer": ""}
        yield json.dumps(d, ensure_ascii=False)
        if stream:
            async for chunk in callback.aiter():
                # Use server-sent-events to stream the response
                data = json.loads(chunk)
                if data["status"] == AgentStatus.llm_start or data["status"] == AgentStatus.llm_end:
                    continue
                elif data["status"] == AgentStatus.error:
                    use_tool_name = data["tool_name"]
                    use_tool = [a for a in available_tools if a.name == use_tool_name]
                    thought = Message_I18N.API_AGENT_TOOL_ERROR_INFO.value.format(
                        tool_name=f"{use_tool[0].title}({use_tool[0].name})" if use_tool else use_tool_name,
                        error=data["error"])
                    yield json.dumps({"thought": thought, "message_id": message_id, "conversation_id": conversation_id},
                                     ensure_ascii=False)
                elif data["status"] == AgentStatus.tool_end:
                    use_tool_name = data["tool_name"]
                    use_tool = [a for a in available_tools if a.name == use_tool_name]
                    thought = Message_I18N.API_AGENT_TOOL_SUCCESS_INFO.value.format(
                        tool_name=f"{use_tool[0].title}({use_tool[0].name})" if use_tool else use_tool_name,
                        input_str=str(data.get("input_str")),
                        output_str=str(data.get("output_str")))
                    yield json.dumps({"thought": thought, "message_id": message_id, "conversation_id": conversation_id},
                                     ensure_ascii=False)
                elif data["status"] == AgentStatus.agent_finish:
                    final_answer = data["final_answer"]
                    yield json.dumps({"answer": final_answer, "message_id": message_id,
                                      "conversation_id": conversation_id}, ensure_ascii=False)
                else:
                    yield json.dumps(
                        {"thought": data["llm_token"], "message_id": message_id, "conversation_id": conversation_id},
                        ensure_ascii=False)
        else:
            answer = ""
            thought = ""
            async for chunk in callback.aiter():
                data = json.loads(chunk)
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
                    answer = data["final_answer"]
                else:
                    thought += data["llm_token"]

            yield json.dumps({"thought": thought, "answer": answer, "message_id": message_id,
                              "conversation_id": conversation_id}, ensure_ascii=False)
        await task

    return EventSourceResponse(wrap_event_response(agent_chat_iterator(query=query,
                                                                       history=history,
                                                                       model_name=model_name,
                                                                       prompt_name=prompt_name),
                                                   ))


async def call_tool(
        assistant_id: int = Body(-1, description="助手ID"),
        tool_name: str = Body(examples=["calculate"], description="工具名称"),
        api_name: str = Body(default="", description="接口名称"),
        tool_input: Dict[str, Any] = Body({}, examples=[{"query": "3+5/2"}]),
) -> BaseResponse:
    try:
        if not tool_name:
            return BaseResponse(code=500, msg=Message_I18N.API_TOOL_NOT_FOUND.value)
        if tool_name == 'http_request' and not api_name:
            return BaseResponse(code=500, msg=Message_I18N.API_TOOL_NOT_FOUND.value)
        model_container = create_model_container()
        if assistant_id >= 0:
            assistant = get_assistant_simple_from_db(assistant_id=assistant_id)
            tool_config = assistant.get("tool_config")
            if tool_config and len(tool_config) > 0:
                model_container.TOOL_CONFIG.update(tool_config)
        available_tools = get_available_tools(tool_names=[tool_name],
                                              api_names=[api_name],
                                              model_container=model_container)
        if not available_tools:
            return BaseResponse(code=500, msg=Message_I18N.API_TOOL_NOT_FOUND.value)
        result = await available_tools[0].ainvoke(tool_input)
        return BaseResponse(code=200, data=result)
    except Exception as e:
        logger.error(f"{e}")
        return BaseResponse(code=500, msg=Message_I18N.COMMON_CALL_FAILED.value)
