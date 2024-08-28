# Langchain 自带的 YouTube 搜索工具封装
from langchain.tools import YouTubeSearchTool
from pydantic import BaseModel, Field

from server.agent.tools_select import register_tool


class YoutubeInput(BaseModel):
    query: str = Field(description="Query for Videos search")


@register_tool(title='油管视频搜索', description="use this tools to search youtube videos",
               args_schema=YoutubeInput)
def search_youtube(query: str):
    tool = YouTubeSearchTool()
    return tool.run(tool_input=query)
