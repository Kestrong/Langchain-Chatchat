import os

from common.exceptions import ChatBusinessException
from configs import CIAM_ADMIN_HOST, CIAM_ADMIN_ENABLED, logger
from server.memory.token_info_memory import get_token
from server.utils import get_httpx_client


def list_resources() -> list:
    if not CIAM_ADMIN_ENABLED:
        return []

    url = f"{CIAM_ADMIN_HOST}/iam/token/listResources"
    headers = {"Authorization": get_token()}
    params = {"resourceTypes": "2", "namespaceCode": "flm-chat"}

    with get_httpx_client(timeout=os.environ.get("CLIENT_TIMEOUT", 15)) as client:
        response = client.get(url=url, params=params, headers=headers)
        if not response.is_success:
            logger.error(response.text)
        response.raise_for_status()
        data = response.json()
        if data.get("statusCode") == 500:
            raise ChatBusinessException(data.get("message"))
        resources = [
            item for item in data.get("data", {}).get("list", [])
            if "flm-chat-assistant-data" in item.get("resourceCode", "")
        ]
        return resources


def get_resource_action_codes() -> list:
    resources = list_resources()
    action_codes = []
    for resource in resources:
        resource_actions = resource.get("resourceActions", [])
        for resource_action in resource_actions:
            action_code = resource_action.get("actionCode")
            if action_code:
                action_codes.append(action_code)
    return action_codes
