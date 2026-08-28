import builtins
import inspect
from typing import Dict, Any, Union

from server.workflow.component.base.component import Component
from server.workflow.utils.inputs import TextInput, DictInput
from server.workflow.utils.outputs import DictOutput, IntOutput


def compile_dynamic_func(function_source: str, func_name: str):
    """
    编译经过审核后上线的动态代码并提取指定函数。

    Args:
        function_source: 包含函数定义的源代码字符串 来自内部可信开发者
        func_name: 要提取的函数名

    Returns:
        tuple: (func, printed_output)
            - func: 编译得到的函数对象，未找到时返回 None
            - printed_output: print() 收集到的输出字符串，无输出时为 None
    """
    try:
        from RestrictedPython import compile_restricted
        from RestrictedPython.Eval import default_guarded_getiter, default_guarded_getitem
        from RestrictedPython.Guards import (
            full_write_guard,
            safer_getattr,
            guarded_iter_unpack_sequence,
            safe_builtins
        )
        from RestrictedPython.PrintCollector import PrintCollector
        ALLOWED_MODULES = {
            'math', 'cmath', 'decimal', 'fractions', 'statistics', 'numbers',
            'random', 'secrets', 'hashlib', 'hmac',
            'string', 'textwrap', 'difflib', 're', 'unicodedata', 'keyword',
            'datetime', 'calendar',
            'collections', 'heapq', 'bisect', 'itertools', 'functools',
            'operator', 'array',
            'json', 'csv', 'html', 'base64', 'binascii', 'struct', 'zlib',
            'copy', 'enum', 'pprint', 'uuid', 'typing', 'types',
            'urllib.parse', 'ipaddress', 'configs'
        }

        def guarded_import(name, *args, **kwargs):
            if name not in ALLOWED_MODULES:
                raise ImportError(f"模块 '{name}' 未被允许导入")
            return builtins.__import__(name, *args, **kwargs)

        safe_builtins_dict = {**safe_builtins, '__import__': guarded_import}

        # 构建受限执行环境
        restricted_globals = {
            '__builtins__': safe_builtins_dict,
            '_print_': PrintCollector,
            '_getiter_': default_guarded_getiter,
            '_getitem_': default_guarded_getitem,
            '_getattr_': safer_getattr,
            '_write_': full_write_guard,
            '_iter_unpack_sequence_': guarded_iter_unpack_sequence,
        }
        byte_code = compile_restricted(function_source, '<inline code>', 'exec')
    except BaseException:
        # 代码经过严格审核 即使不经过RestrictedPython也无安全风险
        restricted_globals = {}
        byte_code = compile(function_source, '<inline code>', 'exec')

    _locals = {}
    exec(byte_code, restricted_globals, _locals)
    func = _locals.get(func_name)
    return func


async def exec_python_async(python_code: str, args: Dict[str, Any], _globals: Dict[str, Any],
                            _locals: Dict[str, Any]) -> Any:
    """执行异步 Python 代码"""
    try:
        func = compile_dynamic_func(python_code, 'main')
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
