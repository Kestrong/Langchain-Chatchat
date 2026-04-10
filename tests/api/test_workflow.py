import json
import sys

import pytest
from fastapi.encoders import jsonable_encoder
from pathlib import Path
from sse_starlette import EventSourceResponse
from starlette.responses import Response

from configs import LLM_MODELS
from server.workflow.component.inputs.chat_input import ChatInputComponent
from server.workflow.component.models.local_llm import LocalLLMComponent
from server.workflow.component.outputs.chat_output import ChatOutputComponent
from server.workflow.component.tools.code import PythonREPLComponent
from server.workflow.utils.inputs import *
from server.workflow.utils.outputs import *

root_path = Path(__file__).parent.parent.parent
sys.path.append(str(root_path))


@pytest.mark.asyncio
async def test_workflow():
    from server.chat.workflow_chat import do_workflow_chat

    # 评分案例+评分过程
    flow = {"nodes": [{"node": {"id": "chat_input-4PnQdf", "name": "chat_input", "display_name": "聊天输入", "description": "获取聊天输入", "tag": "输入", "icon": None, "inputs": [{"id": "query-3Yb9UD", "name": "query", "display_name": "查询内容", "required": True, "enable_expr": True, "info": "输入的问题内容", "options": [], "field_type": "str", "value": "", "type": "TextInput"}, {"id": "history_len-39fxEE", "name": "history_len", "display_name": "历史对话轮次", "required": False, "enable_expr": True, "info": "传递给LLM的历史消息的最大数量", "options": [], "field_type": "int", "value": -1, "type": "IntegerInput"}, {"id": "conversation_id-3BzgYi", "name": "conversation_id", "display_name": "会话ID", "required": False, "enable_expr": True, "info": "聊天的会话ID，如果为空将自动生成", "options": [], "field_type": "str", "value": None, "type": "TextInput"}, {"id": "knowledge_id-3gQEB6", "name": "knowledge_id", "display_name": "知识ID", "required": False, "enable_expr": True, "info": "附件上传后返回的ID", "options": [], "field_type": "str", "value": None, "type": "TextInput"}, {"id": "store_message-4TNz2z", "name": "store_message", "display_name": "是否存储对话", "required": False, "enable_expr": True, "info": "是否将对话存储到数据库中", "options": [], "field_type": "bool", "value": True, "type": "BooleanInput"}, {"id": "extra-4Crn3T", "name": "extra", "display_name": "额外信息", "required": False, "enable_expr": True, "info": "传递给聊天的额外输入", "options": [], "field_type": "dict", "value": {}, "type": "DictInput"}], "outputs": [], "type": "ChatInputComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "local_llm-SdGjBR", "name": "local_llm", "display_name": "本地LLM", "description": "使用本地LLM生成文本", "tag": "模型", "icon": None, "inputs": [{"id": "query-3fuSCj", "name": "query", "display_name": "Text", "required": True, "enable_expr": True, "info": "Message to be passed as input.", "options": [], "field_type": "str", "value": "", "type": "TextInput"}, {"id": "assistant_code-3nCrvC", "name": "assistant_code", "display_name": "助手编码", "required": False, "enable_expr": True, "info": "助手的唯一编码", "options": [], "field_type": "str", "value": "BSS-BASE-QM", "type": "TextInput"}, {"id": "temperature-3kV28d", "name": "temperature", "display_name": "Temperature", "required": False, "enable_expr": True, "info": None, "options": [], "field_type": "float", "value": 0.0, "type": "FloatInput"}, {"id": "prompt-33eVCK", "name": "prompt", "display_name": "Prompt", "required": False, "enable_expr": True, "info": "Prompt for chat.", "options": [], "field_type": "str", "value": "你是一个客观的自动化稽核打分程序。你的唯一任务是通过以下给定的告警调度单信息，对客服的回复内容进行严格的评估打分，并出具纯事实陈述的稽核判决报告。\n                    【全局最高红线】（极其重要）：\n                    由于系统业务规范的严格限制，你在接下来的任何输出中，【绝对禁止】扮演老师或专家的角色去指导用户！\n                    1. 严禁出现“建议补充”、“需要明确”、“请提供”、“应该”等任何带有主观建议或要求性质的话术。\n                    2. 你的职责仅仅是“法官宣判事实”，只陈述因为缺少了什么而扣分，绝不能指导客服怎么去补救。\n                    <错误原因分类两级标准>\n                        系统异常：网络问题、基础设施问题、应用软件问题、软件升级(计划外升级)\n                        配置异常：业务参数配置问题、业务规则问题、系统配置问题\n                        数据源本身问题：业务平台数据源问题、集团下发数据源问题、其他外围系统数据源问题\n                        业务异常：用户行为引起的业务波动、其他业务异常\n                    </错误原因分类两级标准>\n                    <调度单信息>\n                    {{ chat_input-4PnQdf.inputs.extra.background }}\n                    </调度单信息>\n                    <客服的回复内容>\n                    {{ chat_input-4PnQdf.inputs.query }}\n                    </客服的回复内容>\n                    现在请根据以下规则进行评分：\n                    1. 分数范围： 最低分0分，最高分100分\n                    2. 以下是四个维度的评分规则：\n                        ## 一、调度单填写合规性（满分15分）\n                        * 直接给固定分数{{ chat_input-4PnQdf.inputs.extra.compliance_score }}分\n                        ## 二、原因分析质量（满分35分）\n                        注：原因分析为空或纯数字字母时此维度只能得0分，例如：“无”“/”“123”“abc”。\n                        ### 原因分析的信息完备性（满分25分）\n                        * 16-25分：能够明确定位问题的核心根源，描述详细、逻辑清晰。包含明确的实例数据支撑（如具体的错误号码、时间等）或具体的业务场景归因。\n                        * 6-15分：仅描述问题表面现象，未深入指出导致该现象的具体业务源头。例如：“数据异常”“分析中”，且缺乏明确的实例数据支撑。\n                        * 0-5分：问题定位极其模糊或缺失，仅为过程性表述。例如：“核查中”“已知晓”。\n                        ### 错误分类与原因分析匹配度（满分10分）\n                        * 7-10分：选择的`错误原因分类`与填写`原因分析`描述的内容高度匹配。\n                        * 3-6分：大致匹配，但略有偏差。\n                        * 0-2分：完全不符合或相互矛盾，例如：分类选“网络问题”，但分析内容是“业务平台参数配置错误”。\n                        ## 三、解决措施质量（满分35分）\n                        注：解决措施为空或纯数字字母时此维度只能得0分，例如：“无”“/”“123”“abc”。\n                        ### 解决措施的信息完备性（满分25分）\n                        * 16-25分：包含针对根因的实质性处理动作（如补传数据、重跑批次、修改配置等），措施具备直接解决该问题的可执行性，能够推动问题闭环。\n                        * 6-15分：措施较为笼统，仅表达了沟通或核对的意向，未明确后续实质性的系统修复或补救动作。例如：“将进一步分析”“持续跟踪协调”。\n                        * 0-5分：未提出任何实质性措施，或仅为推诿。例如：“不涉及”“待处理”。\n                        ### 原因分析与采取措施匹配度（满分10分）\n                        * 7-10分：所述“采取措施”与“原因分析”指出的问题一一对应，形成闭环，分析出的原因在措施中得到直接解决。\n                        * 3-6分：大致匹配，措施与原因部分相关。\n                        * 0-2分：措施与原因分析完全无关，或者未提出任何具体措施。\n                        ## 四、调度单回复及时性（满分15分）\n                        * 直接给固定分数{{ chat_input-4PnQdf.inputs.extra.timeliness_score }}分\n                    3. 每一个子项的得分是一个区间范围，请先确定评分区间范围，然后每个不足之处在区间范围内酌情扣分\n                    4. 计算过程，请严格按照实际数值进行科学严谨的数学计算：每个维度的得分等于每个维度下的子项得分之和\n                    5. 最终分数必须在分数范围内\n                    请按照以下json格式（必须用双引号包裹key和value）直接输出，不允许包含其他字符：\n                    {\n                      \"short_reason\": {\n                        \"r1\": \"一句话说明调度单填写合规性评分过程\",\n                        \"r2\": {\n                          \"r2.1\": {\n                            \"grade\": \"原因分析的信息完备性的评级（例如：较差(0-5分)、一般(6-15分)、优秀(16-25分)）\",\n                            \"explanation\": \"说明客观事实。若低分：指明当前文本为何被定性为低分。【绝对红线】：文本中严禁出现“系统组件”、“数据字段”、“业务规则”等词汇。若需解释扣分原因，请结合单据上下文，用务实的语言指出其深度的不足（如：虽指出了资源压力，但未下钻到具体的瓶颈点；或：仅说明了状态，未能剖析背后的诱因）。切勿每次使用完全相同的句式。\"\n                          },\n                          \"r2.2\": {\n                            \"grade\": \"错误分类与原因分析匹配度的评级（例如：不匹配(0-2分)、大致匹配(3-6分)、匹配(7-10分)、无法评估(0分)）\",\n                            \"explanation\": \"一句话说明错误分类与原因分析匹配度评分过程\"\n                          }\n                        },\n                        \"r3\": {\n                          \"r3.1\": {\n                            \"grade\": \"解决措施的信息完备性的评级（例如：较差(0-5分)、一般(6-15分)、优秀(16-25分)）\",\n                            \"explanation\": \"说明客观事实。若低分：指明当前文本为何被定性为低分。【绝对红线】：文本中严禁出现“操作步骤”、“牵头方”、“责任人”等词汇。若需解释扣分原因，请结合当前提及的动作，指出其在可执行性上的欠缺（如：虽提出了核对意向，但具体的落地机制不够清晰；或：补传方案在实际执行层面稍显单薄）。切勿每次使用完全相同的句式。\"\n                          },\n                          \"r3.2\": {\n                            \"grade\": \"原因分析与采取措施匹配度的评级（例如：不匹配(0-2分)、大致匹配(3-6分)、匹配(7-10分)、无法评估(0分)）\",\n                            \"explanation\": \"客观陈述原因与措施的闭环情况。若原因与措施均不具体，请直接输出“由于原因与措施均不具体，无法判断是否形成闭环”。\"\n                          }\n                        },\n                        \"r4\": \"一句话说明调度单回复及时性评分过程\"\n                      },\n                      \"scores\": {\n                        \"r1\": \"调度单填写合规性得分\",\n                        \"r2\": {\n                          \"r2.1\": \"原因分析的信息完备性得分\",\n                          \"r2.2\": \"错误分类与原因匹配度得分\"\n                        },\n                        \"r3\": {\n                          \"r3.1\": \"解决措施的信息完备性得分\",\n                          \"r3.2\": \"原因与措施匹配度得分\"\n                        },\n                        \"r4\": \"调度单回复及时性得分\"\n                      },\n                      \"summary\": \"一句话综合总结本次单据的整体回复质量和扣分核心原因。客观陈述事实，严禁使用“建议”、“必须”等说教性词汇。\"\n                    }\n                    ", "type": "TextInput"}, {"id": "model_name-4PpBkg", "name": "model_name", "display_name": "Model Name", "required": True, "enable_expr": True, "info": "The name of LLM.", "options": ["qwen-api"], "field_type": "str", "value": "qwen-api", "type": "TextInput"}], "outputs": [{"id": "answer-3kodUZ", "name": "answer", "display_name": "答案", "info": None, "enable_expr": False, "field_type": "str", "value": None, "type": "TextOutput"}, {"id": "docs-4SM8TY", "name": "docs", "display_name": "文档", "info": None, "enable_expr": False, "field_type": "list", "value": None, "type": "ListOutput"}, {"id": "thought-4GCCeR", "name": "thought", "display_name": "思考过程", "info": None, "enable_expr": False, "field_type": "str", "value": None, "type": "TextOutput"}], "type": "LocalLLMComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "python_repl-Hv5cQw", "name": "python_repl", "display_name": "Python执行", "description": "执行Python代码", "tag": "工具", "icon": None, "inputs": [{"id": "args-B4HZF4", "name": "args", "display_name": "Args", "required": False, "enable_expr": True, "info": "The args for python function.", "options": [], "field_type": "dict", "value": {"arg1": "{{ local_llm-SdGjBR.outputs.answer }}"}, "type": "DictInput"}, {"id": "python_code-4249gd", "name": "python_code", "display_name": "Python", "required": True, "enable_expr": True, "info": "python code.", "options": [], "field_type": "str", "value": "def main(arg1: str) -> str:\n                import json\n                import re\n                if \"```\" in arg1:\n                    match = re.search(r'```(json)?(.*?)```', arg1, re.DOTALL)\n                    if match:\n                        arg1 = match.group(2)\n                a = json.loads(arg1)\n                scores = a.get('scores',{})\n                r1_score = int(scores.get('r1',0))\n                r21_score = int(scores.get('r2',{}).get('r2.1',0))\n                r22_score = int(scores.get('r2',{}).get('r2.2',0))\n                r31_score = int(scores.get('r3',{}).get('r3.1',0))\n                r32_score = int(scores.get('r3',{}).get('r3.2',0))\n                r4_score = int(scores.get('r4',0))\n                total_score = r1_score + r21_score + r22_score + r31_score + r32_score + r4_score\n                short_reason = a.get('short_reason',{})\n                evaluate_report = f\"\"\"\n                【调度单填写合规性】\n                得分：{r1_score}分\n                评分依据：{short_reason.get('r1')}\n                【原因分析的信息完备性】\n                评级：{short_reason.get('r2', {}).get('r2.1', {}).get('grade')}\n                得分：{r21_score}分\n                评分依据：{short_reason.get('r2', {}).get('r2.1', {}).get('explanation')}\n                【错误分类与原因分析匹配度】\n                评级：{short_reason.get('r2', {}).get('r2.2', {}).get('grade')}\n                得分：{r22_score}分\n                评分依据：{short_reason.get('r2', {}).get('r2.2', {}).get('explanation')}\n                【解决措施的信息完备性】\n                评级：{short_reason.get('r3', {}).get('r3.1', {}).get('grade')}\n                得分：{r31_score}分\n                评分依据：{short_reason.get('r3', {}).get('r3.1', {}).get('explanation')}\n                【原因分析与采取措施匹配度】\n                评级：{short_reason.get('r3', {}).get('r3.2', {}).get('grade')}\n                得分：{r32_score}分\n                评分依据：{short_reason.get('r3', {}).get('r3.2', {}).get('explanation')}\n                【调度单回复及时性】\n                得分：{r4_score}分\n                评分依据：{short_reason.get('r4')}\n                总结：最终得分为{total_score}分，{a.get('summary')}\n                \"\"\"\n                return json.dumps({\"score\": total_score, \"suggest\": evaluate_report}, ensure_ascii=False)\n            ", "type": "TextInput"}], "outputs": [{"id": "result-3o6Sbb", "name": "result", "display_name": "结果", "info": None, "enable_expr": False, "field_type": "dict", "value": {}, "type": "DictOutput"}], "type": "PythonREPLComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "chat_output-3ot5hQ", "name": "chat_output", "display_name": "聊天输出", "description": "获取聊天输出", "tag": "输出", "icon": None, "inputs": [], "outputs": [{"id": "answer-UQLWGp", "name": "answer", "display_name": "Answer", "info": None, "enable_expr": True, "field_type": "str", "value": "{{ python_repl-Hv5cQw.outputs.result }}", "type": "TextOutput"}], "type": "ChatOutputComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}], "edges": [{"source": "chat_input-4PnQdf", "target": "local_llm-SdGjBR"}, {"source": "local_llm-SdGjBR", "target": "python_repl-Hv5cQw"}, {"source": "python_repl-Hv5cQw", "target": "chat_output-3ot5hQ"}]}

    chat_response = await do_workflow_chat(
        query="""
省份联系人：毛建邦
省份联系电话：15368221036
涉及系统：出账
发生部门：企业数字化运营中心
影响范围：小
影响开始时间：2025-08-01 00:00:00.0
是否省份异常：否
错误原因分类："用户行为引起的业务波动"
采取措施：单个文件问题，在进一步分析处理中
原因分析：单个文件问题，在进一步分析处理中
完成状态：已完成
完成时间：2025-08-01 00:00:00
        """, assistant_id=-1,
        extra={
            "compliance_score": 15,
            "timeliness_score": 15,
            "background": """
            错单描述：2025-08-31 00:00:00,湖南LTE国际漫游来访数据业务产生拒收，错误条数:1条,拒收条数为：F2000""",
        }, workflow_config=flow, stream=True, store_message=False)

    # flow = {"nodes": [{"node": {"id": "chat_input-rGyQLn", "name": "chat_input", "display_name": "聊天输入", "description": "获取聊天输入", "tag": "输入", "icon": None, "inputs": [{"id": "query-3anptw", "name": "query", "display_name": "查询内容", "required": True, "enable_expr": True, "info": "输入的问题内容", "options": [], "field_type": "str", "value": "", "type": "TextInput"}, {"id": "history_len-wYKmrb", "name": "history_len", "display_name": "历史对话轮次", "required": False, "enable_expr": True, "info": "传递给LLM的历史消息的最大数量", "options": [], "field_type": "int", "value": -1, "type": "IntegerInput"}, {"id": "conversation_id-3eAFTm", "name": "conversation_id", "display_name": "会话ID", "required": False, "enable_expr": True, "info": "聊天的会话ID，如果为空将自动生成", "options": [], "field_type": "str", "value": None, "type": "TextInput"}, {"id": "knowledge_id-ffnPuS", "name": "knowledge_id", "display_name": "知识ID", "required": False, "enable_expr": True, "info": "附件上传后返回的ID", "options": [], "field_type": "str", "value": None, "type": "TextInput"}, {"id": "store_message-3U3Gqp", "name": "store_message", "display_name": "是否存储对话", "required": False, "enable_expr": True, "info": "是否将对话存储到数据库中", "options": [], "field_type": "bool", "value": True, "type": "BooleanInput"}, {"id": "extra-34NzY4", "name": "extra", "display_name": "额外信息", "required": False, "enable_expr": True, "info": "传递给聊天的额外输入", "options": [], "field_type": "dict", "value": {}, "type": "DictInput"}], "outputs": [], "type": "ChatInputComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "local_llm-saH4BA", "name": "local_llm", "display_name": "本地LLM", "description": "使用本地LLM生成文本", "tag": "模型", "icon": None, "inputs": [{"id": "query-3rfbXL", "name": "query", "display_name": "Text", "required": True, "enable_expr": True, "info": "Message to be passed as input.", "options": [], "field_type": "str", "value": "", "type": "TextInput"}, {"id": "temperature-hfZA6J", "name": "temperature", "display_name": "Temperature", "required": False, "enable_expr": True, "info": None, "options": [], "field_type": "float", "value": 0.1, "type": "FloatInput"}, {"id": "prompt-3E5KwJ", "name": "prompt", "display_name": "Prompt", "required": False, "enable_expr": True, "info": "Prompt for chat.", "options": [], "field_type": "str", "value": "你是一名专业的系统运维分析师，请严格根据以下提供的告警工单信息和省份回复内容进行分析：\n                    <告警工单信息>\n                    {{ chat_input-rGyQLn.inputs.query }}\n                    </告警工单信息>\n                    <省份回复内容>\n                    {{ chat_input-rGyQLn.inputs.extra.background }}\n                    </省份回复内容>\n                    请严格按照以下要求一步一步输出纯文本，不得使用任何括号，删除所有括号内的内容：\n                    1. 第一段内容：此次告警涉及xxx等省份（包括省份回复里面的所有省份），通过省份回复分析得出xxx等省份核查正常，xxx等省份核查异常（正常和异常的省份加起来为所有省份，但是同一个省份只能出现一次）\n                    2. 第二段内容：原因分类主要为：1、原因分类名称：罗列涉及的省份名称；2、依此类推...(对所有省份的原因分类进行分组合并，原因分类名称是固定值，不可以从原因分析里面提取，找不到原因分类的名称，则不输出该原因分类名称)\n                    3. 第三段内容：原因措施包含：1、省份名称：xxx，原因分析：xxx，采取措施：xxx，完成状态：xxx；2、依此类推...（按照上面核查异常的省份一一列举并总结概括省份的原因分析和处理措施，必须保留省份的信息和序号）\n                    4. 第四段内容：建议：(从异常省份的问题处理情况的后续跟进方向考虑，用于领导汇报)\n                    ", "type": "TextInput"}, {"id": "model_name-3z6HcY", "name": "model_name", "display_name": "Model Name", "required": True, "enable_expr": True, "info": "The name of LLM.", "options": ["qwen-api"], "field_type": "str", "value": "qwen-api", "type": "TextInput"}], "outputs": [{"id": "answer-pECtQu", "name": "answer", "display_name": "答案", "info": None, "enable_expr": False, "field_type": "str", "value": None, "type": "TextOutput"}, {"id": "docs-nzJhGp", "name": "docs", "display_name": "文档", "info": None, "enable_expr": False, "field_type": "list", "value": None, "type": "ListOutput"}, {"id": "thought-rjp8Hb", "name": "thought", "display_name": "思考过程", "info": None, "enable_expr": False, "field_type": "str", "value": None, "type": "TextOutput"}], "type": "LocalLLMComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "chat_output-3ohyMU", "name": "chat_output", "display_name": "聊天输出", "description": "获取聊天输出", "tag": "输出", "icon": None, "inputs": [], "outputs": [{"id": "answer-4994RK", "name": "answer", "display_name": "Answer", "info": None, "enable_expr": True, "field_type": "str", "value": "{{ local_llm-saH4BA.outputs.answer }}", "type": "TextOutput"}], "type": "ChatOutputComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}], "edges": [{"source": "chat_input-rGyQLn", "target": "local_llm-saH4BA"}, {"source": "local_llm-saH4BA", "target": "chat_output-3ohyMU"}]}
    #
    # chat_response = await do_workflow_chat(
    #     query="海南、辽宁省内变更了套餐未几世同步集团导致，已联系省份尽快补传处理。其他省份处理暂无异常。",
    #     assistant_id=-1, extra={
    #         "background": """
    #         reason: 上海: 原因分析：核实后补传
    #         辽宁: 原因分析：省内更换套餐
    #         江苏: 原因分析：正常
    #         四川: 原因分析：省内用户优惠
    #         吉林: 原因分析：经查该错单用户已经销户，目前省内已经处理，以后不再上传集团。
    #         广东: 原因分析：主要是账目项对应问题，已经安排做兜底优化了，目前验证还需要调整，后续优化上线解决
    #         海南: 原因分析：经核查，17340654591用户停机导致的，按照业务规则停机次月就不收套餐费，收取停保费5元。所以省内应收费用传了5元，导致应收费用小于主套餐费用。省内数据上传正常。
    #          measure: 上海: 核实后补传 完成状态：已完成
    #         辽宁: 省内更换套餐 完成状态：已完成
    #         江苏: 无 完成状态：已完成
    #         四川: 省内用户优惠 完成状态：已完成
    #         吉林: 经查该错单用户已经销户，目前省内已经处理，以后不再上传集团。完成状态：已完成
    #         广东: 主要是账目项对应问题，已经安排做兜底优化了，目前验证还需要调整，后续优化上线解决 完成状态：处理中
    #         海南: 经核查，17340654591用户停机导致的，按照业务规则停机次月就不收套餐费，收取停保费5元。所以省内应收费用传了5元，导致应收费用小于主套餐费用。省内数据上传正常。完成状态：已完成
    #         """
    #     }, workflow_config=flow, stream=True, store_message=False)
    print("\n")
    if isinstance(chat_response, EventSourceResponse):
        async for chunk in chat_response.body_iterator:
            print(chunk)
    elif isinstance(chat_response, Response):
        print(chat_response.body.decode('utf-8'))
    else:
        print(chat_response)


@pytest.mark.asyncio
async def test_dispatch_evaluate_workflow_config():
    flow = {}
    chat_input = ChatInputComponent()
    query_var = chat_input.id + ".inputs.query"
    background_var = chat_input.id + ".inputs.extra.background"
    compliance_score_var = chat_input.id + ".inputs.extra.compliance_score"
    timeliness_score_var = chat_input.id + ".inputs.extra.timeliness_score"

    suggestion_prompt = """
        仅针对得分区间没有达到最高档的项对原因分析和采取措施的内容按照以下规则进行建议：
        1. 采用渐进式的建议，不要一步到位，分解后先引导用户往最简单的方向改进；
        2. 严禁要求补充具体系统处理环节、系统组件、业务规则、用户信息、敏感信息或数据字段等细节；
        3. 调度单信息和客服回复内容里面已经提供的问题描述、错误信息、背景、完成时间等不要再要求重复提供；
        4. 语气专业、客观、具有引导性，避免绝对化；不要进行举例；
        5. 无需改进时，请给出友好的回复；
        输出格式：请对原因分析和采取措施的内容先分别用一句话简要概括目前的主要问题，然后提供方向性、框架性的改进建议，纯文本输出。
    """

    model = LocalLLMComponent(inputs=[TextInput(
        name='query',
        display_name='Text',
        required=True,
        info='Message to be passed as input.',
        value=''
    ),
        TextInput(
            name='assistant_code',
            display_name="助手编码",
            info="助手的唯一编码",
            value='BSS-BASE-QM'
        ),
        FloatInput(
            name='temperature',
            display_name='Temperature',
            value=0
        ),
        TextInput(
            name='prompt',
            display_name='Prompt',
            info='Prompt for chat.',
            value=f"""你是一个资深的系统运维专家，通过以下给定的告警调度单信息，对客服的回复内容进行评估打分并给出修改建议。
                    <错误原因分类两级标准>
                        系统异常：网络问题、基础设施问题、应用软件问题、软件升级(计划外升级)
                        配置异常：业务参数配置问题、业务规则问题、系统配置问题
                        数据源本身问题：业务平台数据源问题、集团下发数据源问题、其他外围系统数据源问题
                        业务异常：用户行为引起的业务波动、其他业务异常
                    </错误原因分类两级标准>
                    <调度单信息>
                    {{{{ {background_var} }}}}
                    </调度单信息>
                    <客服的回复内容>
                    {{{{ {query_var} }}}}
                    </客服的回复内容>
                    现在请根据以下规则进行评分：
                    1. 分数范围： 最低分0分，最高分100分
                    2. 以下是四个维度的评分规则：
                        ## 一、调度单填写合规性（满分15分）
                        * 直接给固定分数{{{{ {compliance_score_var} }}}}分
                        ## 二、原因分析质量（满分35分）
                        注：原因分析为空或纯数字字母时此维度只能得0分，例如：“无”“/”“123”“abc”。
                        ### 原因分析的信息完备性（满分25分）
                        * 16-25分：在问题定位方面，能够明确定位问题的根源，描述详细、逻辑清晰、关键信息完整。同时，在原因分析上，包含具体的实例数据（具体情况具体分析有些场景不需要实例数据），支撑充分。
                        * 6-15分：仅描述问题表面现象，未指出源头。例如：“话单解析为空”“错单描述为空”“数据异常”。并且原因分析仅有非常模糊的描述，缺乏关键信息，例如：“参数更新”没有说明具体的参数信息、“个别错单”未量化、“出库异常”缺少异常的详细说明。
                        * 0-5分：问题定位模糊或缺失，例如：“核实正常”“核查无问题”“分析中”。同时，原因分析几乎无任何具体细节，例如：“上海核查正常”“资料异常”“网元问题”。
                        ### 错误分类与原因分析匹配度（满分10分）
                        * 7-10分：选择的`错误原因分类`与填写`原因分析`描述的内容高度匹配。
                        * 3-6分：大致匹配，但略有偏差。
                        * 0-2分：完全不符合或相互矛盾，例如：分类选“网络问题”，但分析内容是“业务平台参数配置错误”。
                        ## 三、解决措施质量（满分35分）
                        注：解决措施为空或纯数字字母时此维度只能得0分，例如：“无”“/”“123”“abc”。
                        ### 解决措施的信息完备性（满分25分）
                        * 16-25分：在解决措施明确性方面，包含具体措施，明确牵头方，并协调相关上下游解决处理，措施明确可执行。同时，在解决措施的信息完备性上，措施包含具体的操作步骤、方法、技术方案或参数调整项（视情况有些简单的场景只需要明确具体动作或计划）。例如1：“运维部牵头协调网元侧与计费系统，具体步骤为导出异常用户清单、执行 SQL 脚本更新数据库字段、重新触发同步任务以完成用户资料同步”。例如2：“技术部负责调整拣重配置规则中的时间窗口参数，明确将原 30 分钟窗口调整为 60 分钟，并同步至上下游系统”。
                        * 6-15分：解决措施明确性表现为措施较模糊，无法判断具体的优化操作。例如：“已处理”“进一步分析”“持续跟踪”。解决措施的信息完备性仅有非常初步的想法或计划。例如：“待测试”“待处理”。
                        * 0-5分：解决措施明确性上未提出任何实质性措施，或措施完全不可行，例如：“标记不涉及”“请集团谅解”。同时，解决措施的信息完整性无任何实施细节。
                        ### 原因分析与采取措施匹配度（满分10分）
                        * 7-10分：所述“采取措施”与“原因分析”指出的问题一一对应，形成闭环，分析出的原因在措施中得到直接解决。
                        * 3-6分：大致匹配，措施与原因部分相关。
                        * 0-2分：措施与原因分析完全无关，或者未提出任何具体措施。
                        ## 四、调度单回复及时性（满分15分）
                        * 直接给固定分数{{{{ {timeliness_score_var} }}}}分
                    3. 每一个子项的得分是一个区间范围，请先确定评分区间范围，然后每个不足之处在区间范围内酌情扣分
                    4. 计算过程，请严格按照实际数值进行科学严谨的数学计算：每个维度的得分等于每个维度下的子项得分之和
                    5. 最终分数必须在分数范围内
                    请按照以下json格式（必须用双引号包裹key和value）直接输出，不允许包含其他字符："""
                  + """
                  {
                      "short_reason": {
                        "r1": "一句话说明调度单填写合规性评分过程",
                        "r2": {
                          "r2.1": {
                            "grade": "原因分析的信息完备性的评级（例如：较差(0-5分)、一般(6-15分)、优秀(16-25分)）",
                            "explanation": "一句话说明原因分析的信息完备性的评分过程"
                          },
                          "r2.2": {
                            "grade": "错误分类与原因分析匹配度的评级（例如：不匹配(0-2分)、大致匹配(3-6分)、匹配(7-10分)、无法评估(0分)）",
                            "explanation": "一句话说明错误分类与原因分析匹配度评分过程"
                          }
                        },
                        "r3": {
                          "r3.1": {
                            "grade": "解决措施的信息完备性的评级（例如：较差(0-5分)、一般(6-15分)、优秀(16-25分)）",
                            "explanation": "一句话说明解决措施的信息完备性的评分过程"
                          },
                          "r3.2": {
                            "grade": "原因分析与采取措施匹配度的评级（例如：不匹配(0-2分)、大致匹配(3-6分)、匹配(7-10分)、无法评估(0分)）",
                            "explanation": "一句话说明原因与措施匹配度的评分过程"
                          }
                        },
                        "r4": "一句话说明调度单回复及时性评分过程"
                      },
                      "scores": {
                        "r1": "调度单填写合规性得分",
                        "r2": {
                          "r2.1": "原因分析的信息完备性得分",
                          "r2.2": "错误分类与原因匹配度得分"
                        },
                        "r3": {
                          "r3.1": "解决措施的信息完备性得分",
                          "r3.2": "原因与措施匹配度得分"
                        },
                        "r4": "调度单回复及时性得分"
                      },
                      "suggest": """+suggestion_prompt+""" 
                  }
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

    main = """def main(arg1: str) -> str:
                    import json
                    import re
                    if "```" in arg1:
                        match = re.search(r'```(json)?(.*?)```', arg1, re.DOTALL)
                        if match:
                            arg1 = match.group(2)
                    a = json.loads(arg1)
                    scores = a.get('scores',{})
                    r1_score = int(scores.get('r1',0))
                    r21_score = int(scores.get('r2',{}).get('r2.1',0))
                    r22_score = int(scores.get('r2',{}).get('r2.2',0))
                    r31_score = int(scores.get('r3',{}).get('r3.1',0))
                    r32_score = int(scores.get('r3',{}).get('r3.2',0))
                    r4_score = int(scores.get('r4',0))
                    total_score = r1_score + r21_score + r22_score + r31_score + r32_score + r4_score
                    short_reason = a.get('short_reason',{})
                    evaluate_report = f\"\"\"
                    【调度单填写合规性】
                    得分：{r1_score}分
                    评分依据：{short_reason.get('r1')}
                    【原因分析的信息完备性】
                    评级：{short_reason.get('r2', {}).get('r2.1', {}).get('grade')}
                    得分：{r21_score}分
                    评分依据：{short_reason.get('r2', {}).get('r2.1', {}).get('explanation')}
                    【错误分类与原因分析匹配度】
                    评级：{short_reason.get('r2', {}).get('r2.2', {}).get('grade')}
                    得分：{r22_score}分
                    评分依据：{short_reason.get('r2', {}).get('r2.2', {}).get('explanation')}
                    【解决措施的信息完备性】
                    评级：{short_reason.get('r3', {}).get('r3.1', {}).get('grade')}
                    得分：{r31_score}分
                    评分依据：{short_reason.get('r3', {}).get('r3.1', {}).get('explanation')}
                    【原因分析与采取措施匹配度】
                    评级：{short_reason.get('r3', {}).get('r3.2', {}).get('grade')}
                    得分：{r32_score}分
                    评分依据：{short_reason.get('r3', {}).get('r3.2', {}).get('explanation')}
                    【调度单回复及时性】
                    得分：{r4_score}分
                    评分依据：{short_reason.get('r4')}
                    \"\"\"
                    return json.dumps({"score": total_score, "suggest": f"评估得分：{total_score}分，改进建议：{a.get('suggest')}", "evaluate_report": evaluate_report}, ensure_ascii=False)
                """

    python_repl = PythonREPLComponent(inputs=[DictInput(
        name='args',
        display_name='Args',
        info='The args for python function.',
        value={"arg1": "{{ " + model.id + ".outputs.answer }}"}
    ),
        TextInput(
            name='python_code',
            display_name='Python',
            required=True,
            info='python code.',
            value=main
        )])
    chat_output = ChatOutputComponent(outputs=[
        TextOutput(
            display_name="Answer",
            name="answer",
            value="{{ " + python_repl.id + ".outputs.result }}",
            enable_expr=True,
        )
    ])
    position = {"width": 10, "height": 10, "x": -1, "y": -1}
    flow['nodes'] = [{"node": chat_input, "position": position},
                     {"node": model, "position": position},
                     {"node": python_repl, "position": position},
                     {"node": chat_output, "position": position},
                     ]
    flow['edges'] = [{
        "source": chat_input.id,
        "target": model.id,
    }, {
        "source": model.id,
        "target": python_repl.id
    }, {
        "source": python_repl.id,
        "target": chat_output.id
    }]
    print("\n")
    print("json:" + json.dumps(jsonable_encoder(flow), ensure_ascii=False))
    print("python:" + json.dumps(jsonable_encoder(flow), ensure_ascii=False).replace('true', 'True')
          .replace('false', 'False').replace('null', 'None') + " \n")


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


@pytest.mark.asyncio
async def test_excel_import_workflow_config():
    import pandas as pd
    df = pd.read_excel(r'D:\文档\开发文件\大模型\BSS稽核\调度单质量_改进建议抽样_20260330.xlsx')

    from server.chat.workflow_chat import do_workflow_chat

    # 评分案例+评分过程
    flow = {"nodes": [{"node": {"id": "chat_input-4PnQdf", "name": "chat_input", "display_name": "聊天输入", "description": "获取聊天输入", "tag": "输入", "icon": None, "inputs": [{"id": "query-3Yb9UD", "name": "query", "display_name": "查询内容", "required": True, "enable_expr": True, "info": "输入的问题内容", "options": [], "field_type": "str", "value": "", "type": "TextInput"}, {"id": "history_len-39fxEE", "name": "history_len", "display_name": "历史对话轮次", "required": False, "enable_expr": True, "info": "传递给LLM的历史消息的最大数量", "options": [], "field_type": "int", "value": -1, "type": "IntegerInput"}, {"id": "conversation_id-3BzgYi", "name": "conversation_id", "display_name": "会话ID", "required": False, "enable_expr": True, "info": "聊天的会话ID，如果为空将自动生成", "options": [], "field_type": "str", "value": None, "type": "TextInput"}, {"id": "knowledge_id-3gQEB6", "name": "knowledge_id", "display_name": "知识ID", "required": False, "enable_expr": True, "info": "附件上传后返回的ID", "options": [], "field_type": "str", "value": None, "type": "TextInput"}, {"id": "store_message-4TNz2z", "name": "store_message", "display_name": "是否存储对话", "required": False, "enable_expr": True, "info": "是否将对话存储到数据库中", "options": [], "field_type": "bool", "value": True, "type": "BooleanInput"}, {"id": "extra-4Crn3T", "name": "extra", "display_name": "额外信息", "required": False, "enable_expr": True, "info": "传递给聊天的额外输入", "options": [], "field_type": "dict", "value": {}, "type": "DictInput"}], "outputs": [], "type": "ChatInputComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "local_llm-SdGjBR", "name": "local_llm", "display_name": "本地LLM", "description": "使用本地LLM生成文本", "tag": "模型", "icon": None, "inputs": [{"id": "query-3fuSCj", "name": "query", "display_name": "Text", "required": True, "enable_expr": True, "info": "Message to be passed as input.", "options": [], "field_type": "str", "value": "", "type": "TextInput"}, {"id": "assistant_code-3nCrvC", "name": "assistant_code", "display_name": "助手编码", "required": False, "enable_expr": True, "info": "助手的唯一编码", "options": [], "field_type": "str", "value": "BSS-BASE-QM", "type": "TextInput"}, {"id": "temperature-3kV28d", "name": "temperature", "display_name": "Temperature", "required": False, "enable_expr": True, "info": None, "options": [], "field_type": "float", "value": 0.0, "type": "FloatInput"}, {"id": "prompt-33eVCK", "name": "prompt", "display_name": "Prompt", "required": False, "enable_expr": True, "info": "Prompt for chat.", "options": [], "field_type": "str", "value": "你是一个客观的自动化稽核打分程序。你的唯一任务是通过以下给定的告警调度单信息，对客服的回复内容进行严格的评估打分，并出具纯事实陈述的稽核判决报告。\n                    【全局最高红线】（极其重要）：\n                    由于系统业务规范的严格限制，你在接下来的任何输出中，【绝对禁止】扮演老师或专家的角色去指导用户！\n                    1. 严禁出现“建议补充”、“需要明确”、“请提供”、“应该”等任何带有主观建议或要求性质的话术。\n                    2. 你的职责仅仅是“法官宣判事实”，只陈述因为缺少了什么而扣分，绝不能指导客服怎么去补救。\n                    <错误原因分类两级标准>\n                        系统异常：网络问题、基础设施问题、应用软件问题、软件升级(计划外升级)\n                        配置异常：业务参数配置问题、业务规则问题、系统配置问题\n                        数据源本身问题：业务平台数据源问题、集团下发数据源问题、其他外围系统数据源问题\n                        业务异常：用户行为引起的业务波动、其他业务异常\n                    </错误原因分类两级标准>\n                    <调度单信息>\n                    {{ chat_input-4PnQdf.inputs.extra.background }}\n                    </调度单信息>\n                    <客服的回复内容>\n                    {{ chat_input-4PnQdf.inputs.query }}\n                    </客服的回复内容>\n                    现在请根据以下规则进行评分：\n                    1. 分数范围： 最低分0分，最高分100分\n                    2. 以下是四个维度的评分规则：\n                        ## 一、调度单填写合规性（满分15分）\n                        * 直接给固定分数{{ chat_input-4PnQdf.inputs.extra.compliance_score }}分\n                        ## 二、原因分析质量（满分35分）\n                        注：原因分析为空或纯数字字母时此维度只能得0分，例如：“无”“/”“123”“abc”。\n                        ### 原因分析的信息完备性（满分25分）\n                        * 16-25分：能够明确定位问题的核心根源，描述详细、逻辑清晰。包含明确的实例数据支撑（如具体的错误号码、时间等）或具体的业务场景归因。\n                        * 6-15分：仅描述问题表面现象，未深入指出导致该现象的具体业务源头。例如：“数据异常”“分析中”，且缺乏明确的实例数据支撑。\n                        * 0-5分：问题定位极其模糊或缺失，仅为过程性表述。例如：“核查中”“已知晓”。\n                        ### 错误分类与原因分析匹配度（满分10分）\n                        * 7-10分：选择的`错误原因分类`与填写`原因分析`描述的内容高度匹配。\n                        * 3-6分：大致匹配，但略有偏差。\n                        * 0-2分：完全不符合或相互矛盾，例如：分类选“网络问题”，但分析内容是“业务平台参数配置错误”。\n                        ## 三、解决措施质量（满分35分）\n                        注：解决措施为空或纯数字字母时此维度只能得0分，例如：“无”“/”“123”“abc”。\n                        ### 解决措施的信息完备性（满分25分）\n                        * 16-25分：包含针对根因的实质性处理动作（如补传数据、重跑批次、修改配置等），措施具备直接解决该问题的可执行性，能够推动问题闭环。\n                        * 6-15分：措施较为笼统，仅表达了沟通或核对的意向，未明确后续实质性的系统修复或补救动作。例如：“将进一步分析”“持续跟踪协调”。\n                        * 0-5分：未提出任何实质性措施，或仅为推诿。例如：“不涉及”“待处理”。\n                        ### 原因分析与采取措施匹配度（满分10分）\n                        * 7-10分：所述“采取措施”与“原因分析”指出的问题一一对应，形成闭环，分析出的原因在措施中得到直接解决。\n                        * 3-6分：大致匹配，措施与原因部分相关。\n                        * 0-2分：措施与原因分析完全无关，或者未提出任何具体措施。\n                        ## 四、调度单回复及时性（满分15分）\n                        * 直接给固定分数{{ chat_input-4PnQdf.inputs.extra.timeliness_score }}分\n                    3. 每一个子项的得分是一个区间范围，请先确定评分区间范围，然后每个不足之处在区间范围内酌情扣分\n                    4. 计算过程，请严格按照实际数值进行科学严谨的数学计算：每个维度的得分等于每个维度下的子项得分之和\n                    5. 最终分数必须在分数范围内\n                    请按照以下json格式（必须用双引号包裹key和value）直接输出，不允许包含其他字符：\n                    {\n                      \"short_reason\": {\n                        \"r1\": \"一句话说明调度单填写合规性评分过程\",\n                        \"r2\": {\n                          \"r2.1\": {\n                            \"grade\": \"原因分析的信息完备性的评级（例如：较差(0-5分)、一般(6-15分)、优秀(16-25分)）\",\n                            \"explanation\": \"说明客观事实。若低分：指明当前文本为何被定性为低分。【绝对红线】：文本中严禁出现“系统组件”、“数据字段”、“业务规则”等词汇。若需解释扣分原因，请结合单据上下文，用务实的语言指出其深度的不足（如：虽指出了资源压力，但未下钻到具体的瓶颈点；或：仅说明了状态，未能剖析背后的诱因）。切勿每次使用完全相同的句式。\"\n                          },\n                          \"r2.2\": {\n                            \"grade\": \"错误分类与原因分析匹配度的评级（例如：不匹配(0-2分)、大致匹配(3-6分)、匹配(7-10分)、无法评估(0分)）\",\n                            \"explanation\": \"一句话说明错误分类与原因分析匹配度评分过程\"\n                          }\n                        },\n                        \"r3\": {\n                          \"r3.1\": {\n                            \"grade\": \"解决措施的信息完备性的评级（例如：较差(0-5分)、一般(6-15分)、优秀(16-25分)）\",\n                            \"explanation\": \"说明客观事实。若低分：指明当前文本为何被定性为低分。【绝对红线】：文本中严禁出现“操作步骤”、“牵头方”、“责任人”等词汇。若需解释扣分原因，请结合当前提及的动作，指出其在可执行性上的欠缺（如：虽提出了核对意向，但具体的落地机制不够清晰；或：补传方案在实际执行层面稍显单薄）。切勿每次使用完全相同的句式。\"\n                          },\n                          \"r3.2\": {\n                            \"grade\": \"原因分析与采取措施匹配度的评级（例如：不匹配(0-2分)、大致匹配(3-6分)、匹配(7-10分)、无法评估(0分)）\",\n                            \"explanation\": \"客观陈述原因与措施的闭环情况。若原因与措施均不具体，请直接输出“由于原因与措施均不具体，无法判断是否形成闭环”。\"\n                          }\n                        },\n                        \"r4\": \"一句话说明调度单回复及时性评分过程\"\n                      },\n                      \"scores\": {\n                        \"r1\": \"调度单填写合规性得分\",\n                        \"r2\": {\n                          \"r2.1\": \"原因分析的信息完备性得分\",\n                          \"r2.2\": \"错误分类与原因匹配度得分\"\n                        },\n                        \"r3\": {\n                          \"r3.1\": \"解决措施的信息完备性得分\",\n                          \"r3.2\": \"原因与措施匹配度得分\"\n                        },\n                        \"r4\": \"调度单回复及时性得分\"\n                      },\n                      \"summary\": \"一句话综合总结本次单据的整体回复质量和扣分核心原因。客观陈述事实，严禁使用“建议”、“必须”等说教性词汇。\"\n                    }\n                    ", "type": "TextInput"}, {"id": "model_name-4PpBkg", "name": "model_name", "display_name": "Model Name", "required": True, "enable_expr": True, "info": "The name of LLM.", "options": ["qwen-api"], "field_type": "str", "value": "qwen-api", "type": "TextInput"}], "outputs": [{"id": "answer-3kodUZ", "name": "answer", "display_name": "答案", "info": None, "enable_expr": False, "field_type": "str", "value": None, "type": "TextOutput"}, {"id": "docs-4SM8TY", "name": "docs", "display_name": "文档", "info": None, "enable_expr": False, "field_type": "list", "value": None, "type": "ListOutput"}, {"id": "thought-4GCCeR", "name": "thought", "display_name": "思考过程", "info": None, "enable_expr": False, "field_type": "str", "value": None, "type": "TextOutput"}], "type": "LocalLLMComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "python_repl-Hv5cQw", "name": "python_repl", "display_name": "Python执行", "description": "执行Python代码", "tag": "工具", "icon": None, "inputs": [{"id": "args-B4HZF4", "name": "args", "display_name": "Args", "required": False, "enable_expr": True, "info": "The args for python function.", "options": [], "field_type": "dict", "value": {"arg1": "{{ local_llm-SdGjBR.outputs.answer }}"}, "type": "DictInput"}, {"id": "python_code-4249gd", "name": "python_code", "display_name": "Python", "required": True, "enable_expr": True, "info": "python code.", "options": [], "field_type": "str", "value": "def main(arg1: str) -> str:\n                import json\n                import re\n                if \"```\" in arg1:\n                    match = re.search(r'```(json)?(.*?)```', arg1, re.DOTALL)\n                    if match:\n                        arg1 = match.group(2)\n                a = json.loads(arg1)\n                scores = a.get('scores',{})\n                r1_score = int(scores.get('r1',0))\n                r21_score = int(scores.get('r2',{}).get('r2.1',0))\n                r22_score = int(scores.get('r2',{}).get('r2.2',0))\n                r31_score = int(scores.get('r3',{}).get('r3.1',0))\n                r32_score = int(scores.get('r3',{}).get('r3.2',0))\n                r4_score = int(scores.get('r4',0))\n                total_score = r1_score + r21_score + r22_score + r31_score + r32_score + r4_score\n                short_reason = a.get('short_reason',{})\n                evaluate_report = f\"\"\"\n                【调度单填写合规性】\n                得分：{r1_score}分\n                评分依据：{short_reason.get('r1')}\n                【原因分析的信息完备性】\n                评级：{short_reason.get('r2', {}).get('r2.1', {}).get('grade')}\n                得分：{r21_score}分\n                评分依据：{short_reason.get('r2', {}).get('r2.1', {}).get('explanation')}\n                【错误分类与原因分析匹配度】\n                评级：{short_reason.get('r2', {}).get('r2.2', {}).get('grade')}\n                得分：{r22_score}分\n                评分依据：{short_reason.get('r2', {}).get('r2.2', {}).get('explanation')}\n                【解决措施的信息完备性】\n                评级：{short_reason.get('r3', {}).get('r3.1', {}).get('grade')}\n                得分：{r31_score}分\n                评分依据：{short_reason.get('r3', {}).get('r3.1', {}).get('explanation')}\n                【原因分析与采取措施匹配度】\n                评级：{short_reason.get('r3', {}).get('r3.2', {}).get('grade')}\n                得分：{r32_score}分\n                评分依据：{short_reason.get('r3', {}).get('r3.2', {}).get('explanation')}\n                【调度单回复及时性】\n                得分：{r4_score}分\n                评分依据：{short_reason.get('r4')}\n                总结：最终得分为{total_score}分，{a.get('summary')}\n                \"\"\"\n                return json.dumps({\"score\": total_score, \"suggest\": evaluate_report}, ensure_ascii=False)\n            ", "type": "TextInput"}], "outputs": [{"id": "result-3o6Sbb", "name": "result", "display_name": "结果", "info": None, "enable_expr": False, "field_type": "dict", "value": {}, "type": "DictOutput"}], "type": "PythonREPLComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "chat_output-3ot5hQ", "name": "chat_output", "display_name": "聊天输出", "description": "获取聊天输出", "tag": "输出", "icon": None, "inputs": [], "outputs": [{"id": "answer-UQLWGp", "name": "answer", "display_name": "Answer", "info": None, "enable_expr": True, "field_type": "str", "value": "{{ python_repl-Hv5cQw.outputs.result }}", "type": "TextOutput"}], "type": "ChatOutputComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}], "edges": [{"source": "chat_input-4PnQdf", "target": "local_llm-SdGjBR"}, {"source": "local_llm-SdGjBR", "target": "python_repl-Hv5cQw"}, {"source": "python_repl-Hv5cQw", "target": "chat_output-3ot5hQ"}]}

    data_list = ['新版总结']
    score_list = ['新版得分']
    evaluate_report = ["新版评分报告"]

    # 遍历每一行
    for index, row in df.iterrows():
        if index == 0:
            continue
        try:
            # row 是一个 Series 对象，可以通过列名访问值
            chat_response = await do_workflow_chat(
                query=f"""
            省份联系人：{row['region_linker']}
            省份联系电话：{row['region_telephone']}
            涉及系统：{row['involves_system']}
            发生部门：{row['happen_dept']}
            影响范围：{row['incidence']}
            影响开始时间：2025-08-01 00:00:00.0
            是否省份异常：否
            错误原因分类：{row['error_reason_class']}
            采取措施：{row['measure']}
            原因分析：{row['reason_analysis']}
            完成状态：已完成
            完成时间：2025-08-01 00:00:00
                    """, assistant_id=-1,
                extra={
                    "compliance_score": 15,
                    "timeliness_score": 15,
                    "background": f"""
                        错单描述：{row['error_description']}
                        """,
                }, workflow_config=flow, stream=False, store_message=False)
            if isinstance(chat_response, EventSourceResponse):
                async for chunk in chat_response.body_iterator:
                    result = json.loads(json.loads(chunk)['answer'][-1]['outputs']['answer'])
                    score_list.append(result['score'])
                    data_list.append(result['suggest'])
                    evaluate_report.append(result['evaluate_report'])
        except BaseException as e:
            data_list.append("执行报错")
            score_list.append(-1)
            evaluate_report.append("执行报错")
    while len(data_list) < len(df):
        data_list.append("数据缺失")
        score_list.append(None)
        evaluate_report.append("数据缺失")
    df['new_score'] = score_list
    df['new_score_description'] = data_list
    df['new_score_report'] = evaluate_report
    df.to_excel('D:\文档\开发文件\大模型\BSS稽核\调度单质量_改进建议抽样_20260330结果文件.xlsx', index=False)