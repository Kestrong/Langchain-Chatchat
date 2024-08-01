from langchain.tools import Tool
from langchain_core.tools import StructuredTool

from server.agent.tools import *

tools = [
    StructuredTool.from_function(
        func=calculate,
        name="calculate",
        description="Useful for when you need to answer questions about simple calculations or math problems",
        args_schema=CalculatorInput,
    ),
    StructuredTool.from_function(
        func=arxiv,
        name="arxiv",
        description="A wrapper around Arxiv.org for searching and retrieving scientific articles in various fields.",
        args_schema=ArxivInput,
    ),
    StructuredTool.from_function(
        func=weathercheck,
        name="weather_check",
        description="use this tool to search weather of city ",
        args_schema=WeatherInput,
    ),
    StructuredTool.from_function(
        func=shell,
        name="shell",
        description="Use Shell to execute Linux commands, such as curl/pwd/ping/find/ls and etc.",
        args_schema=ShellInput,
    ),
    StructuredTool.from_function(
        func=search_knowledgebase_complex,
        name="search_knowledgebase_complex",
        description="Use this tool to search local knowledgebase and get information",
        args_schema=KnowledgeSearchInput,
    ),
    StructuredTool.from_function(
        func=search_internet,
        name="search_internet",
        description="Use this tool to use bing search engine to search the internet",
        args_schema=SearchInternetInput,
    ),
    StructuredTool.from_function(
        func=wolfram,
        name="Wolfram",
        description="Useful for when you need to calculate difficult formulas",
        args_schema=WolframInput,
    ),
    StructuredTool.from_function(
        func=search_youtube,
        name="search_youtube",
        description="use this tools to search youtube videos",
        args_schema=YoutubeInput,
    ),
]

tool_names = [tool.name for tool in tools]
