import asyncio
import json
from typing import AsyncIterable, Optional, List

from fastapi import Body
from langchain.agents import LLMSingleActionAgent, AgentExecutor
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferWindowMemory
from sse_starlette.sse import EventSourceResponse

from configs import LLM_MODELS, TEMPERATURE, HISTORY_LEN, Agent_MODEL
from server.agent import model_container
from server.agent.callbacks import AgentExecutorAsyncIteratorCallbackHandler, AgentStatus
from server.agent.custom_agent.ChatGLM3Agent import initialize_glm3_agent
from server.agent.custom_template import CustomOutputParser, CustomPromptTemplate
from server.agent.tools_select import get_tools, get_tool_names
from server.callback_handler.conversation_callback_handler import ConversationCallbackHandler
from server.callback_handler.task_callback_handler import TaskCallbackHandler
from server.chat.chat_type import ChatType
from server.chat.task_manager import task_manager
from server.chat.utils import History, UN_FORMAT_ONLINE_LLM_MODELS, wrap_event_response
from server.db.repository import add_message_to_db
from server.knowledge_base.kb_service.base import get_kb_details
from server.utils import wrap_done, get_ChatOpenAI, get_prompt_template, BaseResponse


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
                     tool_name: str = Body("", description="工具的名称"),
                     store_message: bool = Body(True, description="是否保存消息到数据库"),
                     ):
    if model_name in UN_FORMAT_ONLINE_LLM_MODELS:
        return BaseResponse(code=500, msg=f"对不起，agent对话不支持该模型:{model_name}")

    history = [History.from_data(h) for h in history]
    tools, tool_names = get_tools(tool_name=tool_name), get_tool_names(tool_name=tool_name)
    if not tools:
        return BaseResponse(code=500, msg="对不起，没有工具可以调用。")

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

        for t in tool_names:
            if t.lower().__contains__("knowledgebase"):
                kb_list = {x["kb_name"]: x for x in get_kb_details()}
                model_container.DATABASE = {name: details['kb_info'] for name, details in kb_list.items()}
                break

        if Agent_MODEL:
            model_agent = get_ChatOpenAI(
                model_name=Agent_MODEL,
                temperature=temperature,
                max_tokens=max_tokens,
                callbacks=[callback],
            )
            model_container.MODEL = model_agent
        else:
            model_container.MODEL = model

        prompt_template = get_prompt_template("agent_chat", prompt_name)
        prompt_template_agent = CustomPromptTemplate(
            template=prompt_template,
            tools=tools,
            template_format='jinja2',
            input_variables=["input", "intermediate_steps"]
        )
        output_parser = CustomOutputParser()
        llm_chain = LLMChain(llm=model, prompt=prompt_template_agent)
        memory = ConversationBufferWindowMemory(k=max(HISTORY_LEN * 2, len(history) if history else 0))
        for message in history:
            if message.role == 'user':
                memory.chat_memory.add_user_message(message.content)
            else:
                memory.chat_memory.add_ai_message(message.content)
        if "chatglm3" in model_container.MODEL.model_name or "zhipu-api" in model_container.MODEL.model_name:
            agent_executor = initialize_glm3_agent(
                llm=model,
                tools=tools,
                callback_manager=None,
                prompt=prompt_template,
                input_variables=["input", "intermediate_steps"],
                memory=memory,
                verbose=True,
            )
        else:
            agent = LLMSingleActionAgent(
                llm_chain=llm_chain,
                output_parser=output_parser,
                stop=["Observation:", "\nObservation", "<|endoftext|>", "<|im_start|>", "<|im_end|>"],
                allowed_tools=tool_names,
            )
            agent_executor = AgentExecutor.from_agent_and_tools(agent=agent,
                                                                tools=tools,
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
                tools_use = []
                # Use server-sent-events to stream the response
                data = json.loads(chunk)
                if data["status"] == AgentStatus.llm_start or data["status"] == AgentStatus.llm_end:
                    continue
                elif data["status"] == AgentStatus.error:
                    use_tool_name = data["tool_name"]
                    fm_use_tool_name = [f"{t.title}({t.name})" for t in get_tools(use_tool_name)]
                    tools_use.append("\n```\n")
                    tools_use.append("工具名称: " + f"{fm_use_tool_name[0]}" if fm_use_tool_name else use_tool_name)
                    tools_use.append("工具状态: " + "调用失败")
                    tools_use.append("错误信息: " + data["error"])
                    tools_use.append("重新开始尝试")
                    tools_use.append("\n```\n")
                    yield json.dumps({"tools": tools_use, "message_id": message_id, "conversation_id": conversation_id},
                                     ensure_ascii=False)
                elif data["status"] == AgentStatus.tool_end:
                    use_tool_name = data["tool_name"]
                    fm_use_tool_name = [f"{t.title}({t.name})" for t in get_tools(use_tool_name)]
                    tools_use.append("\n```\n")
                    tools_use.append("工具名称: " + f"{fm_use_tool_name[0]}" if fm_use_tool_name else use_tool_name)
                    tools_use.append("工具状态: " + "调用成功")
                    tools_use.append("工具输入: " + data["input_str"])
                    tools_use.append("工具输出: " + data["output_str"])
                    tools_use.append("\n```\n")
                    yield json.dumps({"tools": tools_use, "message_id": message_id, "conversation_id": conversation_id},
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
            tool_use = ""
            llm_tokens = ""
            async for chunk in callback.aiter():
                data = json.loads(chunk)
                if data["status"] == AgentStatus.llm_start or data["status"] == AgentStatus.llm_end:
                    continue
                if data["status"] == AgentStatus.error:
                    tool_use += "\n```\n"
                    tool_use += "工具名称: " + data["tool_name"] + "\n"
                    tool_use += "工具状态: " + "调用失败" + "\n"
                    tool_use += "错误信息: " + data["error"] + "\n"
                    tool_use += "\n```\n"
                if data["status"] == AgentStatus.tool_end:
                    tool_use += "\n```\n"
                    tool_use += "工具名称: " + data["tool_name"] + "\n"
                    tool_use += "工具状态: " + "调用成功" + "\n"
                    tool_use += "工具输入: " + data["input_str"] + "\n"
                    tool_use += "工具输出: " + data["output_str"] + "\n"
                    tool_use += "\n```\n"
                if data["status"] == AgentStatus.agent_finish:
                    answer = data["final_answer"]
                else:
                    llm_tokens = data["llm_token"]

            yield json.dumps({"thought": llm_tokens, "answer": answer,
                              "message_id": message_id, "tools": tool_use,
                              "conversation_id": conversation_id}, ensure_ascii=False)
        await task

    return EventSourceResponse(wrap_event_response(agent_chat_iterator(query=query,
                                                                       history=history,
                                                                       model_name=model_name,
                                                                       prompt_name=prompt_name),
                                                   ))
