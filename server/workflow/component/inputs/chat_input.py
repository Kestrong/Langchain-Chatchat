from typing import Dict, Any, Union

from server.workflow.component.base.component import Component
from server.workflow.utils.inputs import TextInput, DictInput, BooleanInput, IntegerInput


class ChatInputComponent(Component):
    name = 'chat_input'
    display_name = "${WORKFLOW_DISPLAYNAME_CHATINPUT}"
    description = "${WORKFLOW_DESCRIPTION_CHATINPUT}"
    tag = "${WORKFLOW_TAG_INPUT}"
    icon: Union[str, None]

    inputs = [
        TextInput(
            name='query',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_QUERY}",
            required=True,
            info="${WORKFLOW_INPUT_INFO_QUERY}",
            value=''
        ),
        IntegerInput(
            name='history_len',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_HISTORY_LEN}",
            info="${WORKFLOW_INPUT_INFO_HISTORY_LEN}",
            value=-1
        ),
        TextInput(
            name='conversation_id',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_CONVERSATION_ID}",
            info="${WORKFLOW_INPUT_INFO_CONVERSATION_ID}",
        ),
        TextInput(
            name='knowledge_id',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_KNOWLEDGE_ID}",
            info="${WORKFLOW_INPUT_INFO_KNOWLEDGE_ID}",
        ),
        BooleanInput(
            name="store_message",
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_STORE_MESSAGE}",
            info="${WORKFLOW_INPUT_INFO_STORE_MESSAGE}",
            value=True
        ),
        DictInput(
            name="extra",
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_EXTRA}",
            info="${WORKFLOW_INPUT_INFO_EXTRA}",
            value={}
        )
    ]

    outputs = []

    def prepare_input(self, inputs: Dict[str, Any]):
        if self.inputs and inputs:
            for i in self.inputs:
                if i.name in inputs and inputs[i.name] is not None:
                    i.value = inputs[i.name]

    async def _run(self, state: Dict[str, Any]):
        return {}
