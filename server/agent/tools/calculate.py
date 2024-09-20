import numexpr
from pydantic import BaseModel, Field

from server.agent.tools_select import register_tool
from server.memory.message_i18n import Message_I18N


class CalculatorInput(BaseModel):
    expression: str = Field(description="a math expression")


@register_tool(title='数学计算器',
               description="Useful to answer questions about simple calculations. translate user question to a math expression that can be evaluated by numexpr.",
               args_schema=CalculatorInput)
def calculate(expression: str):
    try:
        return str(numexpr.evaluate(expression))
    except Exception:
        return Message_I18N.TOOL_CALCULATE_ERROR.value.format(query=expression)


if __name__ == "__main__":
    result = calculate("2**3")
    print("答案:", result)
