import asyncio
import json
from typing import Dict, Any

from pydantic import BaseModel, Field

from configs import logger
from server.agent.tools_select import register_tool
from server.utils import get_httpx_client


async def mcp_async(tool_config: dict, method: str, params: dict):
    logger.debug(f"mcp method:{method}, params:{params}")
    mcp_config = tool_config
    server_url = mcp_config.get("server_url")
    timeout = mcp_config.get("timeout") or 30
    extra_headers = mcp_config.get("extra_headers", {})

    async with get_httpx_client(follow_redirects=True, timeout=timeout, use_async=True, verify=False) as client:
        event_type = None
        answer = []
        async with client.stream(method="GET", url=f"{server_url}/sse") as message_response:
            message_response.raise_for_status()
            async for line in message_response.aiter_lines():
                logger.debug(f"mcp server response: {line}")
                if line:
                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        if event_type == "message":
                            data = json.loads(line[5:].strip())
                            id = data.get("id", 0)
                            if id > 0:
                                answer.append(data.get('result') or data.get('error'))
                                await message_response.aclose()
                                break
                        elif event_type == "endpoint":
                            message_endpoint = line[5:].strip()  # 例如: /message?session_id=xxx
                            # 获取到 message_endpoint 之后，先发送初始化请求
                            headers = {
                                "Content-Type": "application/json",
                                "Accept": "application/json",
                                **extra_headers
                            }

                            init_payload = {
                                "jsonrpc": "2.0",
                                "id": 0,  # 初始化通常使用 id: 0
                                "method": "initialize",
                                "params": {
                                    "protocolVersion": "2024-11-05",  # 根据实际 MCP 版本调整
                                    "capabilities": {},
                                    "clientInfo": {"name": "MyClient", "version": "1.0.0"}
                                }
                            }

                            init_response = await client.post(
                                url=f"{server_url}{message_endpoint}",
                                headers=headers,
                                json=init_payload
                            )

                            init_response.raise_for_status()

                            # 发送 initialized 通知（MCP协议要求）
                            initialized_payload = {
                                "jsonrpc": "2.0",
                                "method": "notifications/initialized"
                            }

                            initialized_response = await client.post(
                                url=f"{server_url}{message_endpoint}",
                                headers=headers,
                                json=initialized_payload
                            )

                            initialized_response.raise_for_status()

                            # 构建MCP请求 payload
                            payload = {
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": method,
                                "params": params
                            }

                            logger.debug(
                                f"MCP request: message_endpoint={message_endpoint}, method={method}, params={params}")

                            # 发送POST请求
                            response = await client.post(
                                url=f"{server_url}{message_endpoint}",
                                headers=headers,
                                json=payload
                            )

                            response.raise_for_status()

            return json.dumps(answer)


class MCPInput(BaseModel):
    method: str = Field(description="MCP server method: tools/list or tools/call", default="tools/list")
    params: Dict[str, Any] = Field(
        description="the parameters for tools call, for example: {\"name\": \"tool_name\", \"arguments\":{}}",
        default_factory=dict)


@register_tool(title='MCP工具调用',
               description="Use this tool to access external MCP(Model Context Protocol) services.",
               args_schema=MCPInput, dynamic=True)
async def mcp(tool_config: dict, **kwargs):
    """
    Interact with external MCP services via a mandatory two-step process:
    1. Call tools/list method to discover available tools.
    2. Execute specific tools via tools/call based on their definitions.
    """
    return await mcp_async(tool_config, method=kwargs.pop("method", "tools/list"), params=kwargs)


if __name__ == "__main__":
    # 测试示例
    from server.utils import get_tool_config

    mcp_config = get_tool_config().TOOL_CONFIG.get("mcp", {})
    result = asyncio.run(mcp_async(tool_config=mcp_config, method="tools/list", params={}))
    print("MCP响应:", result)
    result = asyncio.run(mcp_async(tool_config=mcp_config, method="tools/call",
                                   params={"name": "add", "arguments": {"a": 5, "b": 3}}))
    print("MCP响应:", result)
