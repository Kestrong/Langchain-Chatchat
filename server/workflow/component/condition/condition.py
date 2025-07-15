from typing import Dict, Any, List, Union

from server.workflow.component.base.component import Component
from server.workflow.utils.inputs import ListInput, TextInput
from server.workflow.utils.outputs import BooleanOutput


class IfElseComponent(Component):
    display_name = "${WORKFLOW_DISPLAYNAME_IFELSE}"
    description = "${WORKFLOW_DESCRIPTION_IFELSE}"
    name = "conditional_router"
    tag = "${WORKFLOW_TAG_CONDITION}"
    icon: Union[str, None]

    inputs = [
        ListInput(
            name="conditions",
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_CONDITIONS}",
            info="${WORKFLOW_INPUT_INFO_CONDITIONS}",
            value=[]
        ),
        TextInput(
            name="relation",
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_RELATION}",
            info="${WORKFLOW_INPUT_INFO_RELATION}",
            value='AND'
        )
    ]

    outputs = [
        BooleanOutput(
            display_name="${WORKFLOW_OUTPUT_DISPLAYNAME_CONDITION_RESULT}",
            name="condition_result",
        )
    ]

    async def _run(self, state: Dict[str, Any]):
        inputs = self.get_context()[self.id]["inputs"]
        conditions: List[dict] = inputs.get("conditions", [])
        relation = inputs.get("relation", "AND")
        if not conditions:
            return {"condition_result": True}
        matches = []
        for condition in conditions:
            left = condition.get("left")
            right = condition.get("right")
            if left and isinstance(left, str):
                if left.startswith("{{") and left.endswith("}}"):
                    left = self.parse_expr(left)
                    condition['left'] = left
            if right and isinstance(right, str):
                if right.startswith("{{") and right.endswith("}}"):
                    right = self.parse_expr(right)
                    condition['right'] = right
            if condition['operator'] == '==':
                matches.append(left == right)
            elif condition['operator'] == '!=':
                matches.append(left != right)
            elif condition['operator'] == '<':
                matches.append(left < right)
            elif condition['operator'] == '>':
                matches.append(left > right)
            elif condition['operator'] == '<=':
                matches.append(left <= right)
            elif condition['operator'] == '>=':
                matches.append(left >= right)
            elif condition['operator'] == 'in':
                matches.append(left in right)
            elif condition['operator'] == 'notin':
                matches.append(left not in right)
            elif condition['operator'] == 'is empty':
                if left:
                    matches.append(False)
                else:
                    matches.append(True)
            elif condition['operator'] == 'is not empty':
                if left:
                    matches.append(True)
                else:
                    matches.append(False)
            else:
                matches.append(False)

        if relation.upper() == 'AND':
            final_match = all(matches)
        else:
            final_match = any(matches)

        if final_match:
            return {"condition_result": True}
        return {"condition_result": False}
