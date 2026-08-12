import asyncio
import json
from typing import Dict, Any, Optional
from urllib.parse import urlparse, urlunparse

from pydantic import BaseModel, Field

from configs import logger
from server.agent.tools_select import register_tool
from server.utils import get_httpx_client


class MCPClient:
    """支持 sse 和 streamable_http 两种传输协议的 MCP 客户端"""

    def __init__(self, tool_config: dict):
        server_url = tool_config.get("server_url", "").rstrip("/")
        parsed = urlparse(server_url)
        base_url = urlunparse((parsed.scheme, parsed.netloc, "", parsed.query, "", ""))
        path = parsed.path or "/"
        self.server_url = base_url
        self.path = path
        self.timeout = tool_config.get("timeout", 30)
        self.extra_headers = tool_config.get("extra_headers", {})
        self.transport = tool_config.get("transport", "sse")
        self._message_endpoint: Optional[str] = None
        self._initialized = False
        self._session_id: Optional[str] = None

    @property
    def headers(self) -> dict:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self.extra_headers,
        }
        if self._session_id:
            h["Mcp-Session-Id"] = self._session_id
        return h

    async def _send_init(self, client, post_url: str) -> None:
        """发送 initialize 并等待成功响应，再发送 initialized 通知"""
        init_payload = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "MyClient", "version": "1.0.0"},
            },
        }
        resp = await client.post(post_url, headers=self.headers, json=init_payload)
        resp.raise_for_status()

        sid = resp.headers.get("mcp-session-id")
        if sid:
            self._session_id = sid

        # initialized 通知（无 id，服务端不返回响应体）
        notify_payload = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        await client.post(post_url, headers=self.headers, json=notify_payload)
        self._initialized = True
        logger.debug(f"MCP initialized via {self.transport}, session={self._session_id}")

    @staticmethod
    def _extract_result(data: dict) -> Any:
        if "error" in data and data["error"] is not None:
            return {"error": data["error"]}
        return data.get("result")

    # ---------- SSE 传输 ----------
    async def _call_sse(self, client, method: str, params: dict) -> Any:
        answer: Any = None
        request_sent = False

        async with client.stream("GET", url=f"{self.server_url}{self.path}") as sse_resp:
            sse_resp.raise_for_status()
            event_type = None

            async for line in sse_resp.aiter_lines():
                logger.debug(f"[SSE] {line}")
                if not line:
                    continue

                if line.startswith("event:"):
                    event_type = line[6:].strip()

                elif line.startswith("data:"):
                    raw_data = line[5:].strip()

                    if event_type == "endpoint" and not request_sent:
                        self._message_endpoint = raw_data
                        logger.debug(f"MCP endpoint: {self._message_endpoint}")
                        if self._message_endpoint.startswith(("http://", "https://")):
                            post_url = self._message_endpoint
                        else:
                            post_url = f"{self.server_url}/{self._message_endpoint.lstrip('/')}"

                        if not self._initialized:
                            await self._send_init(client, post_url)

                        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
                        biz_resp = await client.post(post_url, headers=self.headers, json=payload)
                        biz_resp.raise_for_status()
                        request_sent = True  # 防止重复发送

                    elif event_type == "message":
                        data = json.loads(raw_data)
                        msg_id = data.get("id")
                        if msg_id is not None and msg_id > 0:
                            answer = self._extract_result(data)
                            await sse_resp.aclose()
                            break

        return answer

    # ---------- Streamable HTTP 传输 ----------
    async def _call_streamable_http(self, client, method: str, params: dict) -> Any:
        url = f"{self.server_url}{self.path}"

        if not self._initialized:
            await self._send_init(client, url)

        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

        resp = await client.post(url, headers=self.headers, json=payload)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")

        # 直接 JSON 响应
        if "application/json" in content_type:
            data = resp.json()
            return self._extract_result(data)

        # SSE 流式响应
        event_type = None
        async for line in resp.aiter_lines():
            logger.debug(f"[StreamableHTTP-SSE] {line}")
            if not line:
                continue
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:") and event_type == "message":
                data = json.loads(line[5:].strip())
                msg_id = data.get("id")
                if msg_id is not None and msg_id > 0:
                    return self._extract_result(data)

        return None

    # ---------- 统一入口 ----------
    async def call(self, method: str, params: dict) -> str:
        logger.debug(f"mcp method:{method}, params:{params}")
        async with get_httpx_client(
                follow_redirects=True, timeout=self.timeout, use_async=True, verify=False
        ) as client:
            if self.transport == "streamable_http":
                result = await self._call_streamable_http(client, method, params)
            else:
                result = await self._call_sse(client, method, params)

        return json.dumps(result, ensure_ascii=False) if result is not None else "{}"


async def mcp_async(tool_config: dict, method: str, params: dict):
    client = MCPClient(tool_config)
    return await client.call(method=method, params=params)


class MCPInput(BaseModel):
    method: str = Field(
        description="MCP server method: tools/list or tools/call",
        default="tools/list",
    )
    params: Dict[str, Any] = Field(
        description='Parameters for tools call, e.g. {"name": "tool_name", "arguments": {}}',
        default_factory=dict,
    )


@register_tool(
    title="MCP工具调用",
    description="Use this tool to access external MCP(Model Context Protocol) services.",
    args_schema=MCPInput,
    dynamic=True,
)
async def mcp(tool_config: dict, **kwargs):
    """
    Interact with external MCP services via a mandatory two-step process:
    1. Call tools/list method to discover available tools.
    2. Execute specific tools via tools/call based on their definitions.
    """
    method = kwargs.get("method", "tools/list")
    params = kwargs.get("params", {})
    return await mcp_async(tool_config, method, params)


if __name__ == "__main__":
    from server.utils import get_tool_config

    mcp_config = get_tool_config().TOOL_CONFIG.get("mcp", {})
    print(f"当前传输协议: {mcp_config.get('transport', 'sse')}")

    result = asyncio.run(mcp_async(tool_config=mcp_config, method="tools/list", params={}))
    print("tools/list 响应:", result)

    result = asyncio.run(
        mcp_async(
            tool_config=mcp_config,
            method="tools/call",
            params={"name": "add", "arguments": {"a": 5, "b": 3}},
        )
    )
    print("tools/call 响应:", result)
