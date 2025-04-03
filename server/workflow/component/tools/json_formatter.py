import json
from typing import Dict, Any, Union

from server.workflow.component.base.component import Component
from server.workflow.utils.inputs import TextInput
from server.workflow.utils.outputs import DictOutput


class JsonFormatterComponent(Component):
    display_name = "Json Formatter"
    description = "convert string to json object."
    name = "json_formatter"
    tag = "Tool"
    icon: Union[str, None]

    inputs = [
        TextInput(
            name='json_str',
            display_name='Text',
            required=True,
            info='string to be convert into json object.'
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
