"""
This file is a modified version for ChatGLM3-6B the original glm3_agent.py file from the langchain repo.
"""
from __future__ import annotations

import json
import typing
from typing import Any, List, Sequence, Tuple, Optional, Union

import langchain_core
from langchain.agents.agent import Agent
from langchain.agents.agent import AgentExecutor
from langchain.agents.agent import AgentOutputParser
from langchain.agents.structured_chat.base import HUMAN_MESSAGE_TEMPLATE
from langchain.agents.structured_chat.output_parser import StructuredChatOutputParser
from langchain.callbacks.base import BaseCallbackManager
from langchain.chains.llm import LLMChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.output_parsers import OutputFixingParser
from langchain.prompts.chat import ChatPromptTemplate
from langchain.pydantic_v1 import Field
from langchain.schema import AgentAction, AgentFinish, BasePromptTemplate
from langchain.schema.language_model import BaseLanguageModel
from langchain.tools.base import BaseTool
from langchain_core.messages import ToolMessage, FunctionMessage, SystemMessage, ChatMessage, HumanMessage, AIMessage
from langchain_core.prompts import HumanMessagePromptTemplate
from pydantic.schema import model_schema

from configs import logger

SYSTEM_PROMPT = "Answer the following questions as best as you can. You have access to the following tools:\n{tools}\n"
HUMAN_MESSAGE = "Let's start! Human:{input}\n\nThought:{agent_scratchpad}\n"


class StructuredGLM3ChatOutputParser(StructuredChatOutputParser):
    """
    Output parser with retries for the structured chat agent.
    """

    base_parser: AgentOutputParser = Field(default_factory=StructuredChatOutputParser)
    output_fixing_parser: Optional[OutputFixingParser] = None

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        logger.debug(f"原始输入:{text},结束")
        origin_text = text
        special_tokens = ["Action:", "<|observation|>"]
        first_index = min(
            [
                text.find(token) if token in text else len(text)
                for token in special_tokens
            ]
        )
        text = text[:first_index]

        if "tool_call" in text:
            action_end = text.find("```")
            action = text[:action_end].strip()
            params_str_start = text.find("(") + 1
            params_str_end = text.rfind(")")
            params_str = text[params_str_start:params_str_end]

            params_pairs = [
                param.split("=") for param in params_str.split(",") if "=" in param
            ]
            params = {
                pair[0].strip(): pair[1].strip().strip("'\"") for pair in params_pairs
            }
            return AgentAction(tool=action, tool_input=params, log=text)
        else:
            finish_tokens = ['<|assistant|>', '<|user|>']
            index = min(
                [
                    text.find(token) if token in text else len(text)
                    for token in finish_tokens
                ]
            )
            return AgentFinish({"output": text[:index]}, log=text)

    @property
    def _type(self) -> str:
        return "StructuredGLM3ChatOutputParser"


class StructuredGLM3ChatAgent(Agent):
    """Structured Chat Agent."""

    output_parser: AgentOutputParser = Field(
        default_factory=StructuredGLM3ChatOutputParser
    )
    """Output parser for the agent."""

    @property
    def observation_prefix(self) -> str:
        """Prefix to append the observation with."""
        return "<|observation|>"

    @property
    def llm_prefix(self) -> str:
        """Prefix to append the llm call with."""
        return "Action:"

    def _construct_scratchpad(
            self, intermediate_steps: List[Tuple[AgentAction, str]]
    ) -> str:
        agent_scratchpad = super()._construct_scratchpad(intermediate_steps)
        if not isinstance(agent_scratchpad, str):
            raise ValueError("agent_scratchpad should be of type string.")
        if agent_scratchpad:
            return (
                f"These were previous tasks you completed:\n{agent_scratchpad}\n\n"
            )
        else:
            return agent_scratchpad

    @classmethod
    def _get_default_output_parser(
            cls, llm: Optional[BaseLanguageModel] = None, **kwargs: Any
    ) -> AgentOutputParser:
        return StructuredGLM3ChatOutputParser(llm=llm)

    @property
    def _stop(self) -> List[str]:
        return ["<|observation|>"]

    @classmethod
    def create_prompt(
            cls,
            tools: Sequence[BaseTool],
            prompt: str = None,
            input_variables: Optional[List[str]] = None,
            memory_prompts: Optional[List[BasePromptTemplate]] = None,
    ) -> BasePromptTemplate:
        tools_json = []
        tool_names = []
        for tool in tools:
            tool_schema = model_schema(tool.args_schema) if tool.args_schema else {}
            description = (
                tool.description.split(" - ")[1].strip()
                if tool.description and " - " in tool.description
                else tool.description
            )
            parameters = {
                k: {sub_k: sub_v for sub_k, sub_v in v.items() if sub_k != "title"}
                for k, v in tool_schema.get("properties", {}).items()
            }
            simplified_config_langchain = {
                "name": tool.name,
                "description": description,
                "parameters": parameters,
            }
            tools_json.append(simplified_config_langchain)
            tool_names.append(tool.name)
        formatted_tools = "\n".join(
            [json.dumps(tool, indent=4, ensure_ascii=False) for tool in tools_json]
        )

        if input_variables is None:
            input_variables = ["input", "agent_scratchpad"]

        return ChatPromptTemplate(
            input_variables=input_variables,
            input_types={
                "chat_history": typing.List[
                    typing.Union[
                        AIMessage,
                        HumanMessage,
                        ChatMessage,
                        SystemMessage,
                        FunctionMessage,
                        ToolMessage,
                    ]
                ]
            },
            messages=[
                langchain_core.prompts.SystemMessagePromptTemplate(
                    prompt=langchain_core.prompts.PromptTemplate(
                        input_variables=["tools"], template=SYSTEM_PROMPT
                    )
                ),
                langchain_core.prompts.MessagesPlaceholder(
                    variable_name="chat_history", optional=True
                ),
                langchain_core.prompts.HumanMessagePromptTemplate(
                    prompt=langchain_core.prompts.PromptTemplate(
                        input_variables=["agent_scratchpad", "input"],
                        template=HUMAN_MESSAGE,
                    )
                ),
            ],
        ).partial(tools=formatted_tools)

    @classmethod
    def from_llm_and_tools(
            cls,
            llm: BaseLanguageModel,
            tools: Sequence[BaseTool],
            prompt: str = None,
            callback_manager: Optional[BaseCallbackManager] = None,
            output_parser: Optional[AgentOutputParser] = None,
            human_message_template: str = HUMAN_MESSAGE_TEMPLATE,
            input_variables: Optional[List[str]] = None,
            memory_prompts: Optional[List[BasePromptTemplate]] = None,
            **kwargs: Any,
    ) -> Agent:
        """Construct an agent from an LLM and tools."""
        cls._validate_tools(tools)
        prompt = cls.create_prompt(
            tools,
            prompt=prompt,
            input_variables=input_variables,
            memory_prompts=memory_prompts,
        )
        llm_chain = LLMChain(
            llm=llm,
            prompt=prompt,
            callback_manager=callback_manager,
        )
        tool_names = [tool.name for tool in tools]
        _output_parser = output_parser or cls._get_default_output_parser(llm=llm)
        return cls(
            llm_chain=llm_chain,
            allowed_tools=tool_names,
            output_parser=_output_parser,
            **kwargs,
        )

    @property
    def _agent_type(self) -> str:
        raise ValueError


def initialize_glm3_agent(
        tools: Sequence[BaseTool],
        llm: BaseLanguageModel,
        prompt: str = None,
        memory: Optional[ConversationBufferWindowMemory] = None,
        agent_kwargs: Optional[dict] = None,
        *,
        tags: Optional[Sequence[str]] = None,
        **kwargs: Any,
) -> AgentExecutor:
    tags_ = list(tags) if tags else []
    agent_kwargs = agent_kwargs or {}
    agent_obj = StructuredGLM3ChatAgent.from_llm_and_tools(
        llm=llm,
        tools=tools,
        prompt=prompt,
        **agent_kwargs
    )
    return AgentExecutor.from_agent_and_tools(
        agent=agent_obj,
        tools=tools,
        memory=memory,
        tags=tags_,
        **kwargs,
    )
