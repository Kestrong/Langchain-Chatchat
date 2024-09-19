from __future__ import annotations

import json
import re
from typing import List, Literal, Union

from langchain.agents import Tool
from langchain.agents.structured_chat.output_parser import StructuredChatOutputParser
from langchain.schema import AgentAction, AgentFinish
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_core.prompts import BaseChatPromptTemplate
from langchain_core.prompts.string import DEFAULT_FORMATTER_MAPPING

from configs import logger


class CustomPromptTemplate(BaseChatPromptTemplate):
    template: str
    tools: List[Union[Tool, dict]]
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

        tools_json = []
        for t in self.tools:
            description = t.description if isinstance(t, Tool) else t.get("description")
            desc = re.sub(r"\n+", " ", description)
            name = t.name if isinstance(t, Tool) else t.get("name")
            args = {
                k: {sub_k: sub_v for sub_k, sub_v in v.items() if sub_k != "title"}
                for k, v in (t.args if isinstance(t, Tool) else t.get("parameters")).items()
            }
            simplified_config_langchain = {
                "name": name,
                "description": desc,
                "parameters": args,
            }
            tools_json.append(simplified_config_langchain)
        kwargs["tools"] = "\n".join(
            [json.dumps(tool, indent=4, ensure_ascii=False) for tool in tools_json]
        )
        # kwargs["tools"] = "\n".join([str(format_tool_to_openai_function(tool)) for tool in self.tools])
        # Create a list of tool names for the tools provided
        kwargs["tool_names"] = ", ".join([t.name if isinstance(t, Tool) else t.get("name") for t in self.tools])
        return [HumanMessage(content=DEFAULT_FORMATTER_MAPPING[self.template_format](self.template, **kwargs))]


def validate_json(json_data: str):
    try:
        json.loads(json_data)
        return True
    except ValueError:
        return False


def remove_newlines_from_json(json_str):
    # 正则表达式匹配引号外的换行符
    pattern = r'("[^"]*")|\s+'
    # 使用sub函数替换为空，即删除这些字符
    return (re.sub(pattern, lambda m: m.group(1) if m.group(1) else '', json_str).replace("\n", "\\n")
            .replace("\r", "\\r").replace("\t", "\\t"))


def parse_json(json_string: str, fallback: bool = True) -> Union[str, dict]:
    json_input = None
    try:
        try:
            json_input = json.loads(json_string)
        except Exception as e:
            logger.error(f"{e}")
            json_string = remove_newlines_from_json(json_string)
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
                    logger.error(f'parse json string error:{json_string}')
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
        try:
            if s := (re.findall(r"\n*Action\s*:\s*```(json)?\s*({.+})\s*```", text, flags=re.DOTALL) or
                     re.findall(r"\n*Action\s*:\s*({.+})", text, flags=re.DOTALL) or
                     re.findall(r"\s*({\s*\"action\"\s*:.+?\s*,\s*\"action_input\"\s*:.+\s*})\s*", text,
                                flags=re.DOTALL)):
                action = parse_json(json_string=s[0][1] if isinstance(s[0], tuple) else s[0], fallback=False)
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
        except Exception as e:
            raise OutputParserException(f"Could not parse LLM output: {text}") from e


if __name__ == "__main__":
    text = """
    Action: ```json
    {
      "action": "Final Answer",
      "action_input": "光学晶格是光学领域中一个非常重要的研究领域，研究者们正在努力开发出更加高效的光学晶格，以便更好地控制光的传播、衍射和聚焦。"
    }
    ```
    """
    s = re.findall(r"\s*({\s*\"action\"\s*:.+?\s*,\s*\"action_input\"\s*:.+\s*})\s*", text, flags=re.DOTALL)
    print(s)
