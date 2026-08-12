import inspect
from typing import Dict, Any, Union

from server.workflow.component.base.component import Component
from server.workflow.utils.inputs import TextInput, DictInput
from server.workflow.utils.outputs import DictOutput, IntOutput


async def exec_python_async(python_code: str, args: Dict[str, Any], _globals: Dict[str, Any],
                            _locals: Dict[str, Any]) -> Any:
    """执行异步 Python 代码"""
    try:
        exec(python_code, _globals, _locals)
        func = _locals.get('main')
        if not callable(func):
            return "Error: 'main' function not found in code"

        result = func(**args)
        if inspect.iscoroutine(result):
            return await result
        return result
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"


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
        ),
        IntOutput(
            display_name="${WORKFLOW_OUTPUT_DISPLAYNAME_TOTAL_TOKENS}",
            name="total_tokens",
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

        result = await exec_python_async(python_code, args, _globals, _locals)
        total_tokens = None
        if isinstance(result, dict) and "total_tokens" in result:
            total_tokens = result.pop("total_tokens")
        return {"result": result, "total_tokens": total_tokens}
