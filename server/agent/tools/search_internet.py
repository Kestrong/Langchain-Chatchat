import asyncio

from pydantic import BaseModel, Field

from configs import VECTOR_SEARCH_TOP_K, DEFAULT_SEARCH_ENGINE
from server.agent.tools_select import register_tool
from server.chat.search_engine_chat import lookup_search_engine


async def search_engine_iter(query: str):
    docs = await lookup_search_engine(query, DEFAULT_SEARCH_ENGINE, VECTOR_SEARCH_TOP_K, split_result=True)
    contents = "\n".join([doc.page_content for doc in docs])
    return contents


class SearchInternetInput(BaseModel):
    query: str = Field(description="Query for Internet search")


@register_tool(title='互联网搜索', description="Use this tool to use search engine to search the internet",
               args_schema=SearchInternetInput, )
def search_internet(query: str):
    return asyncio.run(search_engine_iter(query))


if __name__ == "__main__":
    result = search_internet("今天星期几")
    print("答案:", result)
