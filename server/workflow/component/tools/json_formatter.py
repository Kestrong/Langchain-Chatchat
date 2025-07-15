import json
from typing import Dict, Any, Union

from server.workflow.component.base.component import Component
from server.workflow.utils.inputs import TextInput
from server.workflow.utils.outputs import DictOutput


class JsonFormatterComponent(Component):
    display_name = "${WORKFLOW_DISPLAYNAME_JSONFORMATTER}"
    description = "${WORKFLOW_DESCRIPTION_JSONFORMATTER}"
    name = "json_formatter"
    tag = "${WORKFLOW_TAG_TOOL}"
    icon: Union[str, None]

    inputs = [
        TextInput(
            name='json_str',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_JSON_STR}",
            required=True,
            info="${WORKFLOW_INPUT_INFO_JSON_STR}",
        )
    ]

    outputs = [
        DictOutput(
            name='json_obj',
            display_name='Json',
        )
    ]

    async def _run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        inputs = self.get_context()[self.id]["inputs"]
        json_str = inputs.get("json_str")
        json_obj = json.loads(json_str)
        return {"json_obj": json_obj}
