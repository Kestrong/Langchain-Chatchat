import asyncio
import json
import textwrap
from typing import Dict, Any, List, Optional

from fastapi import Body
from langchain.agents import LLMSingleActionAgent, AgentExecutor
from langchain.agents.structured_chat.output_parser import StructuredChatOutputParserWithRetries
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferWindowMemory
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
from sse_starlette import EventSourceResponse

from configs import TEMPERATURE, LLM_MODELS, HISTORY_LEN
from server.agent import create_model_container, text2sql, AgentExecutorAsyncIteratorCallbackHandler, AgentStatus, \
    CustomOutputParser, CustomPromptTemplate
from server.agent.custom_agent.ChatGLM3Agent import initialize_glm3_agent
from server.callback_handler.conversation_callback_handler import ConversationCallbackHandler
from server.callback_handler.task_callback_handler import TaskCallbackHandler
from server.chat.chat_type import ChatType
from server.chat.task_manager import task_manager
from server.chat.utils import History, wrap_event_response
from server.db.repository import add_message_to_db, update_message
from server.memory.conversation_db_buffer_memory import ConversationBufferDBMemory
from server.utils import wrap_done, get_prompt_template, get_ChatOpenAI


async def bss_bi_agent(query: str = Body(..., description="用户输入", examples=["恼羞成怒"]),
                       extra: Dict[str, Any] = Body({}, description="额外的属性"),
                       assistant_id: int = Body(-1, description="助手ID"),
                       conversation_id: str = Body("", description="对话框ID"),
                       history_len: int = Body(-1, description="从数据库中取历史消息的数量"),
                       history: List[History] = Body([],
                                                     description="历史对话",
                                                     examples=[[
                                                         {"role": "user",
                                                          "content": "请使用知识库工具查询今天北京天气"},
                                                         {"role": "assistant",
                                                          "content": "使用天气查询工具查询到今天北京多云，10-14摄氏度，东北风2级，易感冒"}]]
                                                     ),
                       stream: bool = Body(False, description="流式输出"),
                       model_name: str = Body(LLM_MODELS[0], description="LLM 模型名称。"),
                       temperature: float = Body(TEMPERATURE, description="LLM 采样温度", ge=0.0, le=1.0),
                       max_tokens: Optional[int] = Body(None,
                                                        description="限制LLM生成Token数量，默认None代表模型最大值"),
                       prompt_name: str = Body("default",
                                               description="使用的prompt模板名称(在configs/prompt_config.py中配置)"),
                       tool_names: List[str] = Body([], description="工具的名称"),
                       api_names: List[str] = Body([], description="api的名称"),
                       store_message: bool = Body(True, description="是否保存消息到数据库"),
                       ):
    if isinstance(max_tokens, int) and max_tokens <= 0:
        max_tokens = None
    model_container = create_model_container()
    if extra:
        model_container.TOOL_ARGS.update(extra)
    model_container.TOOL_ARGS["query"] = query

    async def agent_chat_iterator():
        message_id = add_message_to_db(chat_type=ChatType.AGENT_CHAT.value, query=query,
                                       conversation_id=conversation_id,
                                       store=store_message, assistant_id=assistant_id)
        waiting_tips = extra.get("waiting_tips", "正在查询相关信息，请耐心等待，我们将尽快为您提供答案...")
        yield json.dumps(obj={"thought": waiting_tips, "message_id": message_id,
                              "conversation_id": conversation_id}, ensure_ascii=False)
        if extra and extra.get("sql_cmd"):

            async def co():
                return text2sql(query)

            task = asyncio.create_task(co())
            task_manager.put(message_id, task)
            sql_result = await task
            metadata = None
            if sql_result.startswith('{') and sql_result.endswith('}'):
                result = json.loads(sql_result)
                if 'metadata' in result:
                    metadata = result["metadata"]
                    del result["metadata"]
                result = json.dumps(result, ensure_ascii=False)
            else:
                result = sql_result
            update_message(message_id=message_id, response=result, metadata=metadata)
            yield json.dumps({"answer": result, "message_id": message_id,
                              "conversation_id": conversation_id}, ensure_ascii=False)
        else:
            from server.chat.agent_chat import get_available_tools
            available_tools = get_available_tools(tool_names=['text2sql'], api_names=[],
                                                  tool_config=model_container.TOOL_CONFIG)
            available_tool_names = [t.name for t in available_tools]
            callback = AgentExecutorAsyncIteratorCallbackHandler()
            conversation_callback = ConversationCallbackHandler(model_name=model_name, conversation_id=conversation_id,
                                                                message_id=message_id,
                                                                chat_type=ChatType.AGENT_CHAT.value,
                                                                query=query, agent=True)
            task_callback = TaskCallbackHandler(conversation_id=conversation_id, message_id=message_id, agent=True)
            callbacks = [callback, conversation_callback, task_callback]
            model = get_ChatOpenAI(
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            def parse_history_message(content: str):
                if content.startswith("{") and content.endswith("}"):
                    content_obj = json.loads(content)
                    return json.dumps(content_obj.get('summarize'), ensure_ascii=False)
                return content

            memory = ConversationBufferWindowMemory(k=max(HISTORY_LEN * 2, len(history) if history else 0))
            history_var = []
            if history:
                history_var = history
                for message in history:
                    if message.role == 'user':
                        memory.chat_memory.add_user_message(message.content)
                    else:
                        memory.chat_memory.add_user_message(parse_history_message(message.content))
            elif conversation_id and history_len > 0:
                memory_ = ConversationBufferDBMemory(conversation_id=conversation_id,
                                                     llm=model,
                                                     message_limit=history_len)
                for a in memory_.buffer:
                    if isinstance(a, HumanMessage):
                        memory.chat_memory.add_user_message(a.content)
                        history_var.append({"role": a.type, "content": a.content})
                    else:
                        memory.chat_memory.add_ai_message(parse_history_message(a.content))
                        history_var.append({"role": a.type, "content": parse_history_message(a.content)})
            step_prompt0 = """你是一个资深的数据库专家，请根据以下输入的问题并联系历史对话上下文，请严格按照以下步骤一步步判断：
1. 判断该问题是否跟sql查询或者数据查询分析有关，如果无关请直接返回“否”，否则返回“是”；
2. 如果要将该问题转换成SQL查询并在数据库里面执行，假设你已经知道要查询哪些表以及对应的表结构，请判断问题是否有给出查询条件，例如：时间范围、员工姓名、省份其中一个条件，如果没有请直接返回“否”，否则返回“是”；
历史对话内容: {{ history }}
问题: {{ input }}
你的答案只能为“是”或“否”其中的一个，不允许输出其他任何文字。"""
            step_template0 = PromptTemplate(input_variables=["input", "history"],
                                            template=textwrap.dedent(step_prompt0).strip(),
                                            template_format="jinja2")
            step_chain0 = LLMChain(llm=model, prompt=step_template0)
            continue_flag = True
            flag = step_chain0.predict(input=query, history=f"{history_var}")
            if flag in ["\"否\"", "“否”", "否", "NO", "no", "No"]:
                continue_flag = False
                d = {"message_id": message_id, "conversation_id": conversation_id,
                     "answer": "请确保您的提问跟数据库的查询与分析有关，您可以提问有关告警或者调度单查询方面的问题。请确保您提供了明确的查询条件，例如：\n1. 查询某人上周的告警信息；\n2. 查询某区域本月的调度单明细。"}
                update_message(message_id=message_id, response=d.get("answer"), metadata=None)
                yield json.dumps(d, ensure_ascii=False)

            if continue_flag:
                model.callbacks = [callback]
                prompt_template = get_prompt_template("agent_chat", prompt_name)
                prompt_template_agent = CustomPromptTemplate(
                    template=prompt_template,
                    tools=available_tools,
                    template_format='jinja2',
                    input_variables=["input", "intermediate_steps", "history"]
                )
                llm_chain = LLMChain(llm=model, prompt=prompt_template_agent)
                if "chatglm3" in model_name or "zhipu-api" in model_name:
                    agent_executor = initialize_glm3_agent(
                        llm=model,
                        tools=available_tools,
                        callback_manager=None,
                        prompt=prompt_template,
                        input_variables=["input", "intermediate_steps", "history"],
                        memory=memory,
                        verbose=True,
                    )
                else:
                    output_parser = StructuredChatOutputParserWithRetries.from_llm(llm=model,
                                                                                   base_parser=CustomOutputParser())
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
                                                                        max_iterations=3
                                                                        )
                    model_container.TOOL_ARGS['retry'] = agent_executor.max_iterations
                while True:
                    try:
                        task = asyncio.create_task(wrap_done(
                            agent_executor.acall(query, callbacks=callbacks, include_run_info=True),
                            callback.done))
                        break
                    except:
                        pass
                task_manager.put(message_id, task)

                if stream:
                    async for chunk in callback.aiter():
                        # Use server-sent-events to stream the response
                        data = json.loads(chunk)
                        if data["status"] == AgentStatus.llm_start or data["status"] == AgentStatus.llm_end:
                            continue
                        elif data["status"] == AgentStatus.agent_finish:
                            final_answer = data["final_answer"]
                            yield json.dumps({"answer": final_answer, "message_id": message_id,
                                              "conversation_id": conversation_id}, ensure_ascii=False)
                else:
                    answer = ""
                    async for chunk in callback.aiter():
                        data = json.loads(chunk)
                        if data["status"] == AgentStatus.llm_start or data["status"] == AgentStatus.llm_end:
                            continue
                        elif data["status"] == AgentStatus.agent_finish:
                            answer += data["final_answer"]

                    yield json.dumps({"answer": answer, "message_id": message_id,
                                      "conversation_id": conversation_id}, ensure_ascii=False)
                await task

    return EventSourceResponse(wrap_event_response(agent_chat_iterator()))
