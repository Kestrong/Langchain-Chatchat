# LangChain 的 Shell 工具
import re

from langchain.tools import ShellTool
from pydantic import BaseModel, Field

from server.agent.tools_select import register_tool
from server.memory.message_i18n import Message_I18N


class ShellInput(BaseModel):
    query: str = Field(description="一个能在Linux命令行运行的Shell命令")


# 命令注入模式 —— 始终拦截
INJECTION_PATTERNS = [
    r'[;|`]',  # 命令分隔符
    r'&&|\|\|',  # 逻辑链
    r'\$\(',  # 命令替换
    r'>/dev/',  # 写入设备文件
]


@register_tool(title='命令行',
               description="Use Shell to execute Linux commands, such as curl/pwd/ping/find/ls and etc.",
               args_schema=ShellInput)
def shell(tool_config: dict, query: str):
    shell_config: dict = tool_config

    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, query):
            raise ValueError(Message_I18N.TOOL_SHELL_REJECT.value.format(query=query))

    disallow_command = shell_config.get("disallow_command", [])
    if disallow_command:
        for c in disallow_command:
            if re.search(c, query, re.IGNORECASE):
                raise ValueError(Message_I18N.TOOL_SHELL_REJECT.value.format(query=query))

    allow_command = shell_config.get("allow_command", [])
    if allow_command:
        if not any(re.search(c, query, re.IGNORECASE) for c in allow_command):
            raise ValueError(Message_I18N.TOOL_SHELL_REJECT.value.format(query=query))

    tool = ShellTool()
    return tool.run(tool_input=query)


if __name__ == '__main__':
    from server.utils import get_tool_config
    tool_config = get_tool_config().TOOL_CONFIG.get("shell")
    for a in ["rm -rf /tmp/"]:
        print(shell(tool_config, a))
