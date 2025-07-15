import concurrent.futures
from typing import Dict, Any, Union

from configs import PYTHON_REPL_TIMEOUT
from server.workflow.component.base.component import Component
from server.workflow.utils.inputs import TextInput, DictInput
from server.workflow.utils.outputs import DictOutput


def exec_python(python_code: str, args: Dict[str, Any], _globals: Dict[str, Any],
                _locals: Dict[str, Any]) -> Any:
    try:
        exec(python_code, _globals, _locals)
        result = _locals['main'](**args)
        return result
    except Exception as e:
        return str(e)


class PythonREPLComponent(Component):
    display_name = "${WORKFLOW_DISPLAYNAME_PYTHONREPL}"
    description = "${WORKFLOW_DESCRIPTION_PYTHONREPL}"
    name = "python_repl"
    tag = "${WORKFLOW_TAG_TOOL}"
    icon: Union[str, None]

    inputs = [
        DictInput(
            name='args',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_ARGS}",
            info="${WORKFLOW_INPUT_INFO_ARGS}",
            value={"arg1": 1, "arg2": 2}
        ),
        TextInput(
            name='python_code',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_PYTHON_CODE}",
            required=True,
            info="${WORKFLOW_INPUT_INFO_PYTHON_CODE}",
            value="""def main(arg1: int, arg2: int) -> dict:
                return arg1 + arg2
            """
        )
    ]

    outputs = [
        DictOutput(
            name='result',
            display_name="${WORKFLOW_OUTPUT_DISPLAYNAME_RESULT}",
        )
    ]

    async def _run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        self.update_input_context()
        inputs = self.get_context()[self.id]["inputs"]
        python_code = inputs.get("python_code")
        del inputs["python_code"]
        args = inputs.get("args")
        _globals = {}
        _locals = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(exec_python, python_code, args, _globals, _locals)
            try:
                # 设置超时时间
                result = future.result(timeout=PYTHON_REPL_TIMEOUT) if PYTHON_REPL_TIMEOUT > 0 else future.result()
            except concurrent.futures.TimeoutError as e:
                result = str(e)
        return {"result": result}
