from typing import Dict, Any, Union

from server.workflow.component.base.component import Component
from server.workflow.utils.outputs import TextOutput


class ChatOutputComponent(Component):
    name = 'chat_output'
    display_name = 'Chat Output'
    description = 'Get chat outputs from the Playground.'
    tag = 'Output'
    icon: Union[str, None]

    inputs = []

    outputs = [
        TextOutput(
            display_name="Answer",
            name="answer",
        )
    ]

    async def _run(self, state: Dict[str, Any]):
        return {}
