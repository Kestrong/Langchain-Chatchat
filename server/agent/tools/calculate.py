import numexpr
from langchain.chains import LLMMathChain
from langchain.chains.llm_math.prompt import PROMPT
from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field

from server.agent import get_model_container
from server.agent.tools_select import register_tool
from server.memory.message_i18n import Message_I18N
from server.memory.token_info_memory import is_english

_PROMPT_TEMPLATE = """
将数学问题翻译成可以使用Python的numexpr库执行的表达式。使用运行此代码的输出来回答问题。
问题: ${{包含数学问题的问题。}}
```text
${{解决问题的单行数学表达式}}
```
...numexpr.evaluate(query)...
```output
${{运行代码的输出}}
```
答案: ${{答案}}

这是两个例子：

问题: 37593 * 67是多少？
```text
37593 * 67
```
...numexpr.evaluate("37593 * 67")...
```output
2518731
```
答案: 2518731

问题: 37593的五次方根是多少？
```text
37593**(1/5)
```
...numexpr.evaluate("37593**(1/5)")...
```output
8.222831614237718
```
答案: 8.222831614237718


问题: 2的平方是多少？
```text
2 ** 2
```
...numexpr.evaluate("2 ** 2")...
```output
4
```
答案: 4


现在，这是我的问题：
问题: {question}
"""

PROMPT_CN = PromptTemplate(
    input_variables=["question"],
    template=_PROMPT_TEMPLATE,
)


class CalculatorInput(BaseModel):
    query: str = Field()


@register_tool(title='数学计算器',
               description="Useful for when you need to answer questions about simple calculations or math problems",
               args_schema=CalculatorInput)
def calculate(query: str):
    model_container = get_model_container()
    model = model_container.MODEL
    try:
        llm_math = LLMMathChain.from_llm(model, verbose=True, prompt=PROMPT if is_english() else PROMPT_CN)
        ans = llm_math.run(query)
        return ans
    except Exception:
        try:
            return str(numexpr.evaluate(query))
        except Exception:
            return Message_I18N.TOOL_CALCULATE_ERROR.value.format(query=query)


if __name__ == "__main__":
    result = calculate("2的三次方")
    print("答案:", result)
