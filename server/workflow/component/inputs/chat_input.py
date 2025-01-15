from typing import Dict, Any, Union

from server.workflow.component.base.component import Component
from server.workflow.utils.inputs import TextInput, DictInput, BooleanInput, IntegerInput


class ChatInputComponent(Component):
    name = 'chat_input'
    display_name = 'Chat Input'
    description = 'Get chat inputs from the Playground.'
    tag = 'Input'
    icon: Union[str, None]

    inputs = [
        TextInput(
            name='query',
            display_name='Text',
            required=True,
            info='Message to be passed as input.',
            value=''
        ),
        IntegerInput(
            name='history_len',
            display_name='History Length',
            info='The maximum number of history message to pass into llm.',
            value=-1
        ),
        TextInput(
            name='conversation_id',
            display_name='Conversation ID',
            info='The conversation id of the chat. If empty, will auto created.'
        ),
        BooleanInput(
            name="store_message",
            display_name="Store Message",
            info="Store the message in the history.",
            value=True
        ),
        DictInput(
            name="extra",
            display_name="Extra Inputs",
            info="Extra inputs passed to the chat.",
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
