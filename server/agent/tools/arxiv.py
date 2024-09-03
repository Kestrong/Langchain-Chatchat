# LangChain 的 ArxivQueryRun 工具
from langchain.tools.arxiv.tool import ArxivQueryRun
from pydantic import BaseModel, Field

from server.agent.tools_select import register_tool


class ArxivInput(BaseModel):
    title: str = Field(description="Query for title search")


@register_tool(title='Arxiv论文',
               description="A wrapper around Arxiv.org for searching and retrieving scientific articles in various fields.",
               args_schema=ArxivInput)
def arxiv(title: str):
    tool = ArxivQueryRun()
    return tool.run(tool_input=title)
