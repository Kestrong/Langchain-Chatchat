from __future__ import annotations

import json
import re
from typing import List, Literal, Union

from langchain.agents import Tool
from langchain.agents.structured_chat.output_parser import StructuredChatOutputParser
from langchain.schema import AgentAction, AgentFinish
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_core.prompts import BaseChatPromptTemplate
from langchain_core.prompts.string import DEFAULT_FORMATTER_MAPPING

from configs import logger


class CustomPromptTemplate(BaseChatPromptTemplate):
    template: str
    tools: List[Tool]
    template_format: Literal["f-string", "jinja2"] = "f-string"
    """The format of the prompt template. Options are: 'f-string', 'jinja2'."""

    def format_messages(self, **kwargs) -> List[BaseMessage]:
        # Get the intermediate steps (AgentAction, Observation tuples)
        # Format them in a particular way
        intermediate_steps = kwargs.pop("intermediate_steps", [])
        thoughts = ""
        for action, observation in intermediate_steps:
            thoughts += action.log
            thoughts += f"\nObservation: {observation}\nThought: "
        # Set the agent_scratchpad variable to that value
        if thoughts:
            kwargs[
                "agent_scratchpad"
            ] = f"These were previous tasks you completed:\n{thoughts}\n\n"
        else:
            kwargs["agent_scratchpad"] = ""
        # Create a tools variable from the list of tools provided

        tools = []
        for t in self.tools:
            desc = re.sub(r"\n+", " ", t.description)
            text = (
                f"{t.name}: Call this tool to interact with the {t.name} API. What is the {t.name} API useful for?"
                f" {desc}"
                f" Parameters: {t.args}"
            )
            tools.append(text)
        kwargs["tools"] = "\n\n".join(tools)
        # kwargs["tools"] = "\n".join([str(format_tool_to_openai_function(tool)) for tool in self.tools])
        # Create a list of tool names for the tools provided
        kwargs["tool_names"] = ", ".join([tool.name for tool in self.tools])
        return [HumanMessage(content=DEFAULT_FORMATTER_MAPPING[self.template_format](self.template, **kwargs))]


def validate_json(json_data: str):
    try:
        json.loads(json_data)
        return True
    except ValueError:
        return False


def parse_json(json_string: str, fallback: bool = True) -> Union[str, dict]:
    json_input = None
    try:
        json_input = json.loads(json_string)
    except:
        # ollama部署的qwen，返回的json键值可能为单引号，可能缺少最后的引号和括号
        if not json_string.endswith('"}'):
            fixed_json_string = (json_string + '"}').replace("'", '"')

            fixed = True
            if not validate_json(fixed_json_string):
                # ollama部署的qwen，返回的json可能有注释，需要去掉注释
                fixed_json_string = (re.sub(r'//.*', '', (json_string + '"}').replace("'", '"'))
                                     .strip()
                                     .replace('\n', ''))
                if not validate_json(fixed_json_string):
                    fixed = False
            if fixed:
                json_string = fixed_json_string

            try:
                json_input = json.loads(json_string)
            except Exception as e:
                if not fallback:
                    raise e
                json_input = json_string

    # 有概率key为command而非query，需修改
    if isinstance(json_input, dict) and "command" in json_input:
        json_input["query"] = json_input.pop("command")

    return json_input


class CustomOutputParser(StructuredChatOutputParser):
    begin: bool = False

    def __init__(self):
        super().__init__()
        self.begin = True

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        logger.debug(f"原始输入:{text},结束")
        if s := (re.findall(r"\n*Action\s*:\s*```\s*({.+})\s*```", text, flags=re.DOTALL) or
                 re.findall(r"\n*Action\s*:\s*({.+})", text, flags=re.DOTALL)):
            action = parse_json(json_string=s[0], fallback=False)
            tool = action.get("action")
            if tool == "Final Answer":
                return AgentFinish({"output": action.get("action_input", "")}, log=text)
            else:
                return AgentAction(
                    tool=tool, tool_input=action.get("action_input", {}), log=text
                )
        elif s := re.findall(
                r"\n*Action\s*:\s*(.+)\n*Action\sInput\s*:\s*(.+)", text, flags=re.DOTALL
        ):
            s = s[-1]
            json_string: str = s[1]
            json_input = parse_json(json_string)

            return AgentAction(tool=s[0].strip(), tool_input=json_input, log=text)
        elif s := re.findall(r"\n*Final\sAnswer\s*:\s*(.+)", text, flags=re.DOTALL):
            s = s[-1]
            return AgentFinish({"output": s}, log=text)
        else:
            return AgentFinish({"output": text}, log=text)
            # raise OutputParserException(f"Could not parse LLM output: {text}")
