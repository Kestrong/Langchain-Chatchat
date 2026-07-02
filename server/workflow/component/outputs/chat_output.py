from typing import Dict, Any, Union

from server.workflow.component.base.component import Component, EXPR_PATTERN
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

    async def chunk_answer(self):
        answer_template = self.outputs[0].value or ''
        last_end = 0

        for match in EXPR_PATTERN.finditer(answer_template):
            static_text = answer_template[last_end:match.start()]
            if static_text:
                yield static_text
            var_name = match.group(1)
            yield f"{{{{{var_name}}}}}"
            last_end = match.end()

        remaining_text = answer_template[last_end:]
        if remaining_text:
            yield remaining_text

    async def _run(self, state: Dict[str, Any]):
        return {}
