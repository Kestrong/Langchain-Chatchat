from typing import Dict, Any, Union

import httpx

from configs import logger, log_verbose
from server.utils import get_httpx_client
from server.workflow.component.base.component import Component
from server.workflow.utils.inputs import TextInput, IntegerInput, DictInput
from server.workflow.utils.outputs import DictOutput, IntOutput


class HttpCallerComponent(Component):
    display_name = "${WORKFLOW_DISPLAYNAME_HTTPCALLER}"
    description = "${WORKFLOW_DESCRIPTION_HTTPCALLER}"
    name = "http_caller"
    tag = "${WORKFLOW_TAG_TOOL}"
    icon: Union[str, None]

    inputs = [
        TextInput(
            name='url',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_URL}",
            required=True,
            info="${WORKFLOW_INPUT_INFO_URL}",
        ),
        TextInput(
            name='method',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_METHOD}",
            required=True,
            options=["GET", "POST", "PATCH", "PUT", "DELETE"],
            info="${WORKFLOW_INPUT_INFO_METHOD}",
            value='POST'
        ),
        IntegerInput(
            name="timeout",
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_TIMEOUT}",
            info="${WORKFLOW_INPUT_INFO_TIMEOUT}",
            value=5
        ),
        DictInput(
            name='cookies',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_COOKIES}",
            info="${WORKFLOW_INPUT_INFO_COOKIES}",
        ),
        DictInput(
            name='headers',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_HEADERS}",
            info="${WORKFLOW_INPUT_INFO_HEADERS}",
        ),
        DictInput(
            name='body',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_BODY}",
            info="${WORKFLOW_INPUT_INFO_BODY}",
        ),
        DictInput(
            name='params',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_PARAMS}",
            info="${WORKFLOW_INPUT_INFO_PARAMS}",
        ),
    ]

    outputs = [
        DictOutput(
            name='data',
            display_name="${WORKFLOW_OUTPUT_DISPLAYNAME_DATA}",
        ),
        IntOutput(
            display_name="${WORKFLOW_OUTPUT_DISPLAYNAME_TOTAL_TOKENS}",
            name="total_tokens",
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
        total_tokens = None

        try:
            async with get_httpx_client(follow_redirects=True, timeout=timeout, use_async=True) as client:
                response = await client.request(method=method, url=url, cookies=cookies, headers=headers, params=params,
                                                json=data)
                try:
                    result = response.json()
                    if isinstance(result, dict) and "total_tokens" in result:
                        total_tokens = result.pop("total_tokens")
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
                    "total_tokens": total_tokens,
                }
        except httpx.TimeoutException:
            return {
                "data": {
                    "source": url,
                    "headers": headers,
                    "status_code": 408,
                    "error": "Request timed out",
                },
                "total_tokens": None,
            }
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error making request to {url}", exc_info=exc if log_verbose else None)
            return {
                "data": {
                    "source": url,
                    "headers": headers,
                    "status_code": 500,
                    "error": str(exc),
                },
                "total_tokens": None,
            }
