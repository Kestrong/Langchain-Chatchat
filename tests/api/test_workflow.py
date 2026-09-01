import inspect
import json
import sys
import textwrap

import pytest
from fastapi.encoders import jsonable_encoder
from pathlib import Path
from sse_starlette import EventSourceResponse
from starlette.responses import Response

from configs import LLM_MODELS
from server.workflow.component.inputs.chat_input import ChatInputComponent
from server.workflow.component.models.local_llm import LocalLLMComponent
from server.workflow.component.outputs.chat_output import ChatOutputComponent
from server.workflow.component.tools.python_repl import PythonREPLComponent
from server.workflow.utils.inputs import *
from server.workflow.utils.outputs import *

root_path = Path(__file__).parent.parent.parent
sys.path.append(str(root_path))


@pytest.mark.asyncio
async def test_workflow():
    from server.chat.workflow_chat import do_workflow_chat

    flow = {"nodes": [{"node": {"id": "chat_input-rGyQLn", "name": "chat_input", "display_name": "聊天输入", "description": "获取聊天输入", "tag": "输入", "icon": None, "inputs": [{"id": "query-3anptw", "name": "query", "display_name": "查询内容", "required": True, "enable_expr": True, "info": "输入的问题内容", "options": [], "field_type": "str", "value": "", "type": "TextInput"}, {"id": "history_len-wYKmrb", "name": "history_len", "display_name": "历史对话轮次", "required": False, "enable_expr": True, "info": "传递给LLM的历史消息的最大数量", "options": [], "field_type": "int", "value": -1, "type": "IntegerInput"}, {"id": "conversation_id-3eAFTm", "name": "conversation_id", "display_name": "会话ID", "required": False, "enable_expr": True, "info": "聊天的会话ID，如果为空将自动生成", "options": [], "field_type": "str", "value": None, "type": "TextInput"}, {"id": "knowledge_id-ffnPuS", "name": "knowledge_id", "display_name": "知识ID", "required": False, "enable_expr": True, "info": "附件上传后返回的ID", "options": [], "field_type": "str", "value": None, "type": "TextInput"}, {"id": "store_message-3U3Gqp", "name": "store_message", "display_name": "是否存储对话", "required": False, "enable_expr": True, "info": "是否将对话存储到数据库中", "options": [], "field_type": "bool", "value": True, "type": "BooleanInput"}, {"id": "extra-34NzY4", "name": "extra", "display_name": "额外信息", "required": False, "enable_expr": True, "info": "传递给聊天的额外输入", "options": [], "field_type": "dict", "value": {}, "type": "DictInput"}], "outputs": [], "type": "ChatInputComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "local_llm-saH4BA", "name": "local_llm", "display_name": "本地LLM", "description": "使用本地LLM生成文本", "tag": "模型", "icon": None, "inputs": [{"id": "query-3rfbXL", "name": "query", "display_name": "Text", "required": True, "enable_expr": True, "info": "Message to be passed as input.", "options": [], "field_type": "str", "value": "", "type": "TextInput"}, {"id": "temperature-hfZA6J", "name": "temperature", "display_name": "Temperature", "required": False, "enable_expr": True, "info": None, "options": [], "field_type": "float", "value": 0.1, "type": "FloatInput"}, {"id": "prompt-3E5KwJ", "name": "prompt", "display_name": "Prompt", "required": False, "enable_expr": True, "info": "Prompt for chat.", "options": [], "field_type": "str", "value": "你是一名专业的系统运维分析师，请严格根据以下提供的告警工单信息和省份回复内容进行分析：\n                    <告警工单信息>\n                    {{ chat_input-rGyQLn.inputs.query }}\n                    </告警工单信息>\n                    <省份回复内容>\n                    {{ chat_input-rGyQLn.inputs.extra.background }}\n                    </省份回复内容>\n                    请严格按照以下要求一步一步输出纯文本，不得使用任何括号，删除所有括号内的内容：\n                    1. 第一段内容：此次告警涉及xxx等省份（包括省份回复里面的所有省份），通过省份回复分析得出xxx等省份核查正常，xxx等省份核查异常（正常和异常的省份加起来为所有省份，但是同一个省份只能出现一次）\n                    2. 第二段内容：原因分类主要为：1、原因分类名称：罗列涉及的省份名称；2、依此类推...(对所有省份的原因分类进行分组合并，原因分类名称是固定值，不可以从原因分析里面提取，找不到原因分类的名称，则不输出该原因分类名称)\n                    3. 第三段内容：原因措施包含：1、省份名称：xxx，原因分析：xxx，采取措施：xxx，完成状态：xxx；2、依此类推...（按照上面核查异常的省份一一列举并总结概括省份的原因分析和处理措施，必须保留省份的信息和序号）\n                    4. 第四段内容：建议：(从异常省份的问题处理情况的后续跟进方向考虑，用于领导汇报)\n                    ", "type": "TextInput"}, {"id": "model_name-3z6HcY", "name": "model_name", "display_name": "Model Name", "required": True, "enable_expr": True, "info": "The name of LLM.", "options": ["qwen-api"], "field_type": "str", "value": "qwen-api", "type": "TextInput"}], "outputs": [{"id": "answer-pECtQu", "name": "answer", "display_name": "答案", "info": None, "enable_expr": False, "field_type": "str", "value": None, "type": "TextOutput"}, {"id": "docs-nzJhGp", "name": "docs", "display_name": "文档", "info": None, "enable_expr": False, "field_type": "list", "value": None, "type": "ListOutput"}, {"id": "thought-rjp8Hb", "name": "thought", "display_name": "思考过程", "info": None, "enable_expr": False, "field_type": "str", "value": None, "type": "TextOutput"}], "type": "LocalLLMComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "chat_output-3ohyMU", "name": "chat_output", "display_name": "聊天输出", "description": "获取聊天输出", "tag": "输出", "icon": None, "inputs": [], "outputs": [{"id": "answer-4994RK", "name": "answer", "display_name": "Answer", "info": None, "enable_expr": True, "field_type": "str", "value": "{{ local_llm-saH4BA.outputs.answer }}", "type": "TextOutput"}], "type": "ChatOutputComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}], "edges": [{"source": "chat_input-rGyQLn", "target": "local_llm-saH4BA"}, {"source": "local_llm-saH4BA", "target": "chat_output-3ohyMU"}]}

    chat_response = await do_workflow_chat(
        query="海南、辽宁省内变更了套餐未几世同步集团导致，已联系省份尽快补传处理。其他省份处理暂无异常。",
        assistant_id=-1, extra={
            "background": """
            reason: 上海: 原因分析：核实后补传
            辽宁: 原因分析：省内更换套餐
            江苏: 原因分析：正常
            四川: 原因分析：省内用户优惠
            吉林: 原因分析：经查该错单用户已经销户，目前省内已经处理，以后不再上传集团。
            广东: 原因分析：主要是账目项对应问题，已经安排做兜底优化了，目前验证还需要调整，后续优化上线解决
            海南: 原因分析：经核查，17340654591用户停机导致的，按照业务规则停机次月就不收套餐费，收取停保费5元。所以省内应收费用传了5元，导致应收费用小于主套餐费用。省内数据上传正常。
             measure: 上海: 核实后补传 完成状态：已完成
            辽宁: 省内更换套餐 完成状态：已完成
            江苏: 无 完成状态：已完成
            四川: 省内用户优惠 完成状态：已完成
            吉林: 经查该错单用户已经销户，目前省内已经处理，以后不再上传集团。完成状态：已完成
            广东: 主要是账目项对应问题，已经安排做兜底优化了，目前验证还需要调整，后续优化上线解决 完成状态：处理中
            海南: 经核查，17340654591用户停机导致的，按照业务规则停机次月就不收套餐费，收取停保费5元。所以省内应收费用传了5元，导致应收费用小于主套餐费用。省内数据上传正常。完成状态：已完成
            """
        }, workflow_config=flow, stream=True, store_message=False)
    print("\n")
    if isinstance(chat_response, EventSourceResponse):
        async for chunk in chat_response.body_iterator:
            print(chunk)
    elif isinstance(chat_response, Response):
        print(chat_response.body.decode('utf-8'))
    else:
        print(chat_response)


@pytest.mark.asyncio
async def test_alarm_reason_generate_workflow_config():
    flow = {}
    chat_input = ChatInputComponent()
    query_var = chat_input.id + ".inputs.query"
    background_var = chat_input.id + ".inputs.extra.background"
    model = LocalLLMComponent(inputs=[
        TextInput(
            name='query',
            display_name='Text',
            required=True,
            info='Message to be passed as input.',
            value=''
        ),
        FloatInput(
            name='temperature',
            display_name='Temperature',
            value=0.1
        ),
        TextInput(
            name='prompt',
            display_name='Prompt',
            info='Prompt for chat.',
            value=f"""你是一名专业的系统运维分析师，请严格根据以下提供的告警工单信息和省份回复内容进行分析：
                    <告警工单信息>
                    {{{{ {query_var} }}}}
                    </告警工单信息>
                    <省份回复内容>
                    {{{{ {background_var} }}}}
                    </省份回复内容>
                    请严格按照以下要求一步一步输出纯文本，不得使用任何括号，删除所有括号内的内容：
                    1. 第一段内容：此次告警涉及xxx等省份（包括省份回复里面的所有省份），通过省份回复分析得出xxx等省份核查正常，xxx等省份核查异常（正常和异常的省份加起来为所有省份，但是同一个省份只能出现一次）
                    2. 第二段内容：原因分类主要为：1、原因分类名称：罗列涉及的省份名称；2、依此类推...(对所有省份的原因分类进行分组合并，原因分类名称是固定值，不可以从原因分析里面提取，找不到原因分类的名称，则不输出该原因分类名称)
                    3. 第三段内容：原因措施包含：1、省份名称：xxx，原因分析：xxx，采取措施：xxx，完成状态：xxx；2、依此类推...（按照上面核查异常的省份一一列举并总结概括省份的原因分析和处理措施，必须保留省份的信息和序号）
                    4. 第四段内容：建议：(从异常省份的问题处理情况的后续跟进方向考虑，用于领导汇报)
                    """
        ),
        TextInput(
            name='model_name',
            display_name='Model Name',
            required=True,
            info=f'The name of LLM.',
            options=[LLM_MODELS[0]],
            value=LLM_MODELS[0]
        ), ])
    chat_output = ChatOutputComponent(outputs=[
        TextOutput(
            display_name="Answer",
            name="answer",
            value="{{ " + model.id + ".outputs.answer }}",
            enable_expr=True,
        )
    ])
    position = {"width": 10, "height": 10, "x": -1, "y": -1}
    flow['nodes'] = [{"node": chat_input, "position": position},
                     {"node": model, "position": position},
                     {"node": chat_output, "position": position},
                     ]
    flow['edges'] = [{
        "source": chat_input.id,
        "target": model.id,
    }, {
        "source": model.id,
        "target": chat_output.id
    }, ]
    print("\n")
    print("json:" + json.dumps(jsonable_encoder(flow), ensure_ascii=False))
    print("python:" + json.dumps(jsonable_encoder(flow), ensure_ascii=False).replace('true', 'True')
          .replace('false', 'False').replace('null', 'None') + " \n")


