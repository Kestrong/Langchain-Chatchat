# LangChain 的 Shell 工具
import re

from langchain.tools import ShellTool
from pydantic import BaseModel, Field

from server.agent.tools_select import register_tool
from server.memory.message_i18n import Message_I18N
from server.utils import get_tool_config


class ShellInput(BaseModel):
    query: str = Field(description="一个能在Linux命令行运行的Shell命令")


@register_tool(title='命令行',
               description="Use Shell to execute Linux commands, such as curl/pwd/ping/find/ls and etc.",
               args_schema=ShellInput)
def shell(query: str):
    tool_config = get_tool_config().TOOL_CONFIG
    shell_config: dict = tool_config.get("shell", {})
    disallow_command = shell_config.get("disallow_command", [])
    allow_command = shell_config.get("allow_command", [])
    if disallow_command:
        for c in disallow_command:
            if re.match(c, query, re.IGNORECASE):
                raise ValueError(Message_I18N.TOOL_SHELL_REJECT.value.format(query=query))
    if allow_command:
        flag = False
        for c in allow_command:
            if re.match(c, query, re.IGNORECASE):
                flag = True
                break
        if not flag:
            raise ValueError(Message_I18N.TOOL_SHELL_REJECT.value.format(query=query))

    tool = ShellTool()
    return tool.run(tool_input=query)


if __name__ == '__main__':
    for a in ["rm -rf /tmp/"]:
        print(shell(a))
