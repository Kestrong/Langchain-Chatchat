# Langchain 自带的 Wolfram Alpha API 封装
from langchain.utilities.wolfram_alpha import WolframAlphaAPIWrapper
from pydantic import BaseModel, Field

from configs import WOLFRAM_ALPHA_API_KEY
from server.agent.tools_select import register_tool

wolfram_alpha_appid = WOLFRAM_ALPHA_API_KEY


class WolframInput(BaseModel):
    query: str = Field(description="需要运算的具体问题")


@register_tool(title='Wolfram数学软件',
               description="Useful for when you need to calculate difficult formulas",
               args_schema=WolframInput)
def wolfram(query: str):
    wolfram = WolframAlphaAPIWrapper(wolfram_alpha_appid=wolfram_alpha_appid)
    ans = wolfram.run(query)
    return ans
