import json
from typing import List, Tuple, Dict, Union, AsyncIterable

from langchain.agents import LLMSingleActionAgent, AgentExecutor
from langchain.agents.structured_chat.output_parser import StructuredChatOutputParserWithRetries
from langchain.chains import LLMChain
from langchain.prompts.chat import ChatMessagePromptTemplate
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from common.exceptions import ChatBusinessException
from configs import logger, log_verbose
from server.db.repository import update_message
from server.memory.message_i18n import Message_I18N
from server.utils import get_model_worker_config


class History(BaseModel):
    """
    对话历史
    可从dict生成，如
    h = History(**{"role":"user","content":"你好"})
    也可转换为tuple，如
    h.to_msy_tuple = ("human", "你好")
    """
    role: str = Field(...)
    content: str = Field(...)

    def to_msg_tuple(self):
        return "ai" if self.role == "assistant" else "human", self.content

    def to_msg_template(self, is_raw=True) -> ChatMessagePromptTemplate:
        role_maps = {
            "ai": "assistant",
            "human": "user",
        }
        role = role_maps.get(self.role, self.role)
        if is_raw:  # 当前默认历史消息都是没有input_variable的文本。
            content = "{% raw %}" + self.content + "{% endraw %}"
        else:
            content = self.content

        return ChatMessagePromptTemplate.from_template(
            content,
            "jinja2",
            role=role,
        )

    @classmethod
    def from_data(cls, h: Union[List, Tuple, Dict]) -> "History":
        if isinstance(h, (list, tuple)) and len(h) >= 2:
            h = cls(role=h[0], content=h[1])
        elif isinstance(h, dict):
            h = cls(**h)

        return h


def parse_llm_token_inner_json(model_name: str, token: str):
    mark = f'###[{model_name}]###'
    answer = ''
    thought = ''
    extra = {}
    d = {}
    if mark in token:
        parts = token.split(mark)
        for part in parts:
            if part is not None and part.strip() != '':
                if part.startswith('{') and part.endswith('}'):
                    inner_json = json.loads(part)
                    answer += inner_json.get('answer', '')
                    thought += inner_json.get('thought', '')
                    if 'conversation_id' in inner_json:
                        extra['conversation_id'] = inner_json['conversation_id']
                    if 'message_id' in inner_json:
                        extra['message_id'] = inner_json['message_id']
                else:
                    answer += part
    else:
        answer = token
    d["answer"] = answer
    d["thought"] = thought
    if len(extra) > 0:
        d["extra"] = extra
    return d


class MaxInputTokenException(BaseException):
    pass


async def wrap_event_response(event_response: AsyncIterable[str]) -> AsyncIterable[str]:
    d = {}
    try:
        first = True
        async for event in event_response:
            if first:
                try:
                    first = False
                    d.update(json.loads(event))
                except:
                    pass
            yield event
    except MaxInputTokenException as e:
        d["answer"] = f"{e}"
        d["error"] = True
        if d.get("message_id"):
            update_message(message_id=d.get("message_id"), response=d["answer"])
        yield json.dumps(d, ensure_ascii=False)
    except BaseException as e:
        d["error"] = True
        if isinstance(e, ChatBusinessException):
            d["answer"] = str(e)
            e = e.__cause__
            logger.error(f'{e.__class__.__name__}: {e}', exc_info=e if log_verbose else None)
            yield json.dumps(d, ensure_ascii=False)
        else:
            msg = f'{e.__class__.__name__}: {e}'
            logger.error(msg, exc_info=e if log_verbose else None)
            d["answer"] = Message_I18N.WORKER_CHAT_ERROR.value
            if d.get("message_id"):
                update_message(message_id=d.get("message_id"), response=d["answer"], metadata={"error_info": msg},
                               append=True)
            yield json.dumps(d, ensure_ascii=False)


EMPTY_LLM_CHAT_PROMPT = PromptTemplate.from_template("{{ input }}", template_format="jinja2")


# 特殊的在线大模型，不支持知识库、agent对话等模式
def un_format_online_llm_model(model_name: str):
    config = get_model_worker_config(model_name)
    worker_class = config.get("worker_class")
    if worker_class:
        worker = worker_class()
        return not worker.format_online_llm()
    return False


def create_agent_executor(model, memory, available_tools: list, prompt_template: str, max_iterations: int = 5):
    model_name = model.metadata["origin_model_name"]
    if "chatglm3" in model_name or "zhipu-api" in model_name:
        from server.agent.custom_agent.ChatGLM3Agent import initialize_glm3_agent

        agent_executor = initialize_glm3_agent(
            llm=model,
            tools=available_tools,
            callback_manager=None,
            prompt=prompt_template,
            input_variables=["input", "intermediate_steps", "history"],
            memory=memory,
            verbose=True,
            max_iterations=max_iterations
        )
    else:
        from server.agent import CustomPromptTemplate, CustomOutputParser

        prompt_template_agent = CustomPromptTemplate(
            template=prompt_template,
            tools=available_tools,
            template_format='jinja2',
            input_variables=["input", "intermediate_steps", "history"]
        )
        llm_chain = LLMChain(llm=model, prompt=prompt_template_agent)
        output_parser = StructuredChatOutputParserWithRetries.from_llm(llm=model, base_parser=CustomOutputParser())
        output_parser.output_fixing_parser.max_retries = 3
        agent = LLMSingleActionAgent(
            llm_chain=llm_chain,
            output_parser=output_parser,
            stop=["Observation:", "\nObservation", "<|endoftext|>", "<|im_start|>", "<|im_end|>"],
            allowed_tools=[t.name for t in available_tools],
        )
        agent_executor = AgentExecutor.from_agent_and_tools(agent=agent,
                                                            tools=available_tools,
                                                            verbose=True,
                                                            memory=memory,
                                                            max_iterations=max_iterations
                                                            )
    return agent_executor
