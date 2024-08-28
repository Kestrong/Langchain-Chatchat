"""
更简单的单参数输入工具实现，用于查询现在天气的情况
"""
import requests
from pydantic import BaseModel, Field

from configs import SENIVERSE_API_KEY
from server.agent.tools_select import register_tool


def weather(location: str, api_key: str):
    url = f"https://api.seniverse.com/v3/weather/now.json?key={api_key}&location={location}&language=zh-Hans&unit=c"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        weather = {
            "temperature": data["results"][0]["now"]["temperature"],
            "description": data["results"][0]["now"]["text"],
        }
        return weather
    else:
        raise Exception(
            f"Failed to retrieve weather: {response.status_code}")


class WeatherInput(BaseModel):
    location: str = Field(description="City name,include city and county")


@register_tool(title='天气查询', description="use this tool to search weather of city ",
               args_schema=WeatherInput)
def weathercheck(location: str):
    return weather(location, SENIVERSE_API_KEY)
