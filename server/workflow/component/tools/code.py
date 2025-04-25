import multiprocessing
from typing import Dict, Any, Union

from configs import PYTHON_REPL_TIMEOUT
from server.workflow.component.base.component import Component
from server.workflow.utils.inputs import TextInput, DictInput
from server.workflow.utils.outputs import DictOutput


def exec_python(python_code: str, args: Dict[str, Any], _globals: Dict[str, Any],
                _locals: Dict[str, Any], queue: multiprocessing.Queue) -> Any:
    try:
        exec(python_code, _globals, _locals)
        result = _locals['main'](**args)
        queue.put(result)
    except Exception as e:
        queue.put(str(e))


class PythonREPLComponent(Component):
    display_name = "Python REPL"
    description = "execute python code."
    name = "python_repl"
    tag = "Tool"
    icon: Union[str, None]

    inputs = [
        DictInput(
            name='args',
            display_name='Args',
            info='The args for python function.',
            value={"arg1": 1, "arg2": 2}
        ),
        TextInput(
            name='python_code',
            display_name='Python',
            required=True,
            info='python code.',
            value="""def main(arg1: int, arg2: int) -> dict:
                return arg1 + arg2
            """
        )
    ]

    outputs = [
        DictOutput(
            name='result',
            display_name='Result',
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
        queue: multiprocessing.Queue = multiprocessing.Queue()
        p = multiprocessing.Process(
            target=exec_python, args=(python_code, args, _globals, _locals, queue)
        )
        p.start()
        if PYTHON_REPL_TIMEOUT > 0:
            p.join(PYTHON_REPL_TIMEOUT)
        if p.is_alive():
            p.terminate()
        result = queue.get()
        return {"result": result}
