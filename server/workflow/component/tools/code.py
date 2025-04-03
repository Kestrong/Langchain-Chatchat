from typing import Dict, Any, Union

from langchain_experimental.utilities import PythonREPL

from server.workflow.component.base.component import Component
from server.workflow.utils.inputs import TextInput
from server.workflow.utils.outputs import DictOutput


class PythonREPLComponent(Component):
    display_name = "Python REPL"
    description = "execute python code."
    name = "python_repl"
    tag = "Tool"
    icon: Union[str, None]

    inputs = [
        TextInput(
            name='python_code',
            display_name='Python',
            required=True,
            info='python code.'
        )
    ]

    outputs = [
        DictOutput(
            name='result',
            display_name='Result',
        )
    ]

    async def _run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        py_repl = PythonREPL()
        inputs = self.get_context()[self.id]["inputs"]
        python_code = inputs.get("python_code")
        result = py_repl.run(python_code)
        del inputs["python_code"]
        return {"result": result}
