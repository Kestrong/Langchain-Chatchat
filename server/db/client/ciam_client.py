import os

from common.exceptions import ChatBusinessException

try:
    from configs import CIAM_ADMIN_HOST, CIAM_ADMIN_ENABLED
except ImportError:
    CIAM_ADMIN_HOST = ""
    CIAM_ADMIN_ENABLED = "False"
from configs import logger
from server.memory.token_info_memory import get_token
from server.utils import get_httpx_client


def list_resources(resource_code: str) -> list:
    if CIAM_ADMIN_ENABLED != "True":
        return []

    url = f"{CIAM_ADMIN_HOST}/iam/token/listResources"
    headers = {"Authorization": get_token()}
    params = {"resourceTypes": "2", "namespaceCode": "flm-chat"}

    with get_httpx_client(timeout=int(os.environ.get("CLIENT_TIMEOUT", 15))) as client:
        response = client.get(url=url, params=params, headers=headers)
        if not response.is_success:
            logger.error(response.text)
        response.raise_for_status()
        data = response.json()
        if data.get("statusCode") == 500:
            raise ChatBusinessException(data.get("message"))
        resources = [
            item for item in data.get("data", {}).get("list", [])
            if resource_code in item.get("resourceCode", "")
        ]
        return resources


def get_resource_action_codes(resource_code: str) -> list:
    resources = list_resources(resource_code=resource_code)
    action_codes = []
    for resource in resources:
        resource_actions = resource.get("resourceActions", [])
        for resource_action in resource_actions:
            action_code = resource_action.get("actionCode")
            if action_code:
                action_codes.append(action_code)
    return action_codes
