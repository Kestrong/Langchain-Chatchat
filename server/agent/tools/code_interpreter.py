import contextlib
from io import StringIO

from pydantic import Field, BaseModel

from server.agent.tools_select import register_tool


class CodeInput(BaseModel):
    code: str = Field(description="Python3 code to be interpreted.")


@register_tool(title='代码执行器',
               description="Interprets Python3 code strings with a final print statement. ALWAYS create a variable called `result` as the output of the code and print(result)",
               args_schema=CodeInput)
def code_interpreter(code: str):
    f = StringIO()
    try:
        exec_locals = {}
        exec_globals = {}
        with contextlib.redirect_stdout(f):
            exec(code, exec_globals, exec_locals)
        return f.getvalue() or exec_locals.get('result',
                                               "No result variable found, you must create a variable called `result` as the output of the code and print(result).")
    except Exception as e:
        return f"An error occurred: {str(e)}"
    finally:
        f.close()
