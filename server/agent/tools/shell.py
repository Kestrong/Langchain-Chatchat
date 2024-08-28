# LangChain 的 Shell 工具
from langchain.tools import ShellTool
from pydantic import BaseModel, Field

from server.agent.tools_select import register_tool


class ShellInput(BaseModel):
    query: str = Field(description="一个能在Linux命令行运行的Shell命令")


@register_tool(title='命令行工具',
               description="Use Shell to execute Linux commands, such as curl/pwd/ping/find/ls and etc.",
               args_schema=ShellInput)
def shell(query: str):
    tool = ShellTool()
    return tool.run(tool_input=query)
