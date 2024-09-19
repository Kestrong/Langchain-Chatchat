# LangChain 的 ArxivQueryRun 工具
import json

from langchain_core.prompts.string import DEFAULT_FORMATTER_MAPPING
from pydantic import BaseModel, Field

from configs import logger
from server.agent.tools.aes import decrypt_placeholder
from server.agent.tools_select import register_tool
from server.utils import get_httpx_client


class HttpRequestInput(BaseModel):
    api_info: dict = Field(description="api info")
    args: dict = Field(description="request args")


@register_tool(title='Http请求',
               description="Use this tool to send request to http server.",
               args_schema=HttpRequestInput)
def http_request(api_info: dict, args: dict):
    return _http_request(api_info, args)


def _http_request(api_info: dict, args: dict):
    logger.debug(f"http request:{args}")
    with get_httpx_client(follow_redirects=True, timeout=api_info.get("timeout", 5)) as client:
        method = api_info.get("method", "POST")
        url = api_info.get("url")
        headers = {k: decrypt_placeholder(v) for k, v in api_info.get("headers", {})}
        cookies = {k: decrypt_placeholder(v) for k, v in api_info.get("cookies", {})}

        if api_info.get("request_template"):
            args = json.loads(DEFAULT_FORMATTER_MAPPING["jinja2"](api_info.get("request_template"), **args).strip())

        params, json_body = None, None
        if method.upper() == "GET":
            params = args
        else:
            json_body = args

        response = client.request(method=method, url=url, headers=headers, cookies=cookies, params=params,
                                  json=json_body)
        if response.status_code != 200:
            logger.error(response.text)
            response.raise_for_status()
        if api_info.get("response_template"):
            format_response = DEFAULT_FORMATTER_MAPPING["jinja2"](api_info.get("response_template"),
                                                                  **response.json()).strip()
            return format_response
        return response.text


if __name__ == '__main__':
    d = {"a": {"b": ["hi", "i", "am", "jane"]}, "c": "hello", "d": "world", "keyword": "search text"}
    s = "{c} {d}"
    print(s.format(**d))

    template = """
    {{ a.b | join(" ") }}
    """

    format_str = DEFAULT_FORMATTER_MAPPING["jinja2"](template, **d)
    print(format_str.strip())

    json_template = """
    {"keyword": "{{keyword}}"}
    """

    json_format_str = DEFAULT_FORMATTER_MAPPING["jinja2"](json_template, **d)
    print(json_format_str.strip())
