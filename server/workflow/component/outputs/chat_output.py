from typing import Dict, Any, Union

from server.workflow.component.base.component import Component
from server.workflow.utils.outputs import TextOutput


class ChatOutputComponent(Component):
    name = 'chat_output'
    display_name = "${WORKFLOW_DISPLAYNAME_CHATOUTPUT}"
    description = "${WORKFLOW_DESCRIPTION_CHATOUTPUT}"
    tag = "${WORKFLOW_TAG_OUTPUT}"
    icon: Union[str, None]

    inputs = []

    outputs = [
        TextOutput(
            display_name="${WORKFLOW_OUTPUT_DISPLAYNAME_ANSWER}",
            name="answer",
        )
    ]

    async def _run(self, state: Dict[str, Any]):
        return {}
