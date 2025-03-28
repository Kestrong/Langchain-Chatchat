import asyncio
import json
import random
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
                    return content_obj.get('summarize')
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
            step_prompt0 = """你是一个资深的python程序员，请仔细阅读以下输入的问题和历史对话上下文。
                        历史对话上下文: {{ history }}
                        问题: {{ input }}
                        请你结合历史对话上下文和问题，让我们一步一步来推理，判断以下python伪代码的输出是什么？
                        指令：请直接输出伪代码运行的结果，不要包含任何其他的内容
                        def function() -> bool:
                            flag1 = False
                            接下来想问的问题 = 推理(历史对话上下文 + 问题)
                            if 接下来想问的问题 关于 数据查询 or 统计分析 or 告警 or 调度单:
                                flag1 = True
                            flag2 = False    
                            if 接下来想问的问题 包含 时间范围 or 员工姓名 or 省市区域:
                                flag2 = True
                            if flag1 and flag2:
                                return True
                            else:
                                return False
                        """
            step_template0 = PromptTemplate(input_variables=["input", "history"],
                                            template=step_prompt0,
                                            template_format="jinja2")
            step_chain0 = LLMChain(llm=model, prompt=step_template0)
            continue_flag = True
            flag = step_chain0.predict(input=query, history=f"{history_var}")
            if "false" in flag.lower():
                continue_flag = False
                question_alarm = ['查看某人上周的告警明细', '查看某人本月的告警统计',
                                  '过去一周告警的分布情况', '今天已处理和未处理的告警按人员分布情况']
                question_schedule = ['查看某区域上周的调度单明细', '查看某区域上月的调度单统计',
                                     '查询某人上月的调度单处理及时性统计']
                question1 = random.choice(question_alarm)
                question2 = random.choice(question_schedule)
                d = {"message_id": message_id, "conversation_id": conversation_id,
                     "answer": f"请确保您的提问跟数据库的查询与分析有关，您可以提问有关告警或者调度单查询方面的问题。请确保您提供了以下查询条件之一：时间范围、员工姓名、省份区域。您也可以尝试提问以下内容：\n1. {question1}；\n2. {question2}。\n\n💡**小提示**：有时候是我没理解您的意思，重新提问一次也许会得到更好的结果。"}
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
