from typing import Dict, Any, Union

import httpx

from configs import logger
from server.utils import get_httpx_client
from server.workflow.component.base.component import Component
from server.workflow.utils.inputs import TextInput, IntegerInput, DictInput
from server.workflow.utils.outputs import DictOutput


class HttpCallerComponent(Component):
    display_name = "Http Caller"
    description = "send a http request to the server."
    name = "http_caller"
    tag = "Tool"
    icon: Union[str, None]

    inputs = [
        TextInput(
            name='url',
            display_name='Url',
            required=True,
            info='server url.'
        ),
        TextInput(
            name='method',
            display_name='Method',
            required=True,
            options=["GET", "POST", "PATCH", "PUT", "DELETE"],
            info='The HTTP method to use (GET, POST, PATCH, PUT, DELETE).',
            value='POST'
        ),
        IntegerInput(
            name="timeout",
            display_name="Timeout",
            value=5,
            info="The timeout to use for the request.",
        ),
        DictInput(
            name='cookies',
            display_name='Cookies',
            info='The cookies to send with the request as a dictionary.'
        ),
        DictInput(
            name='headers',
            display_name='Headers',
            info='The headers to send with the request as a dictionary.'
        ),
        DictInput(
            name='body',
            display_name='Body',
            info='The body to send with the request as a dictionary(for POST, PATCH, PUT).'
        ),
        DictInput(
            name='params',
            display_name='Params',
            info='The query parameters to append to the URL.'
        ),
    ]

    outputs = [
        DictOutput(
            name='data',
            display_name='Data',
        )
    ]

    async def _run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        inputs = self.get_context()[self.id]["inputs"]
        url = inputs.get("url")
        method = inputs.get("method")
        if method not in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
            raise ValueError(f"Unsupported method: {method}")
        timeout = inputs.get("timeout")
        headers = inputs.get("headers")
        cookies = inputs.get("cookies")
        body = inputs.get("body")
        params = inputs.get("params")
        data = body or None

        try:
            async with get_httpx_client(follow_redirects=True, timeout=timeout, use_async=True) as client:
                response = await client.request(method=method, url=url, cookies=cookies, headers=headers, params=params,
                                                json=data)
                try:
                    result = response.json()
                except Exception:  # noqa: BLE001
                    logger.opt(exception=True).debug("Error decoding JSON response")
                    result = response.text
                return {
                    "data": {
                        "source": url,
                        "headers": headers,
                        "status_code": response.status_code,
                        "result": result,
                    },
                }
        except httpx.TimeoutException:
            return {
                "data": {
                    "source": url,
                    "headers": headers,
                    "status_code": 408,
                    "error": "Request timed out",
                },
            }
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=True).debug(f"Error making request to {url}")
            return {
                "data": {
                    "source": url,
                    "headers": headers,
                    "status_code": 500,
                    "error": str(exc),
                },
            }
