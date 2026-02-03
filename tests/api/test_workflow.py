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
from server.workflow.component.tools.knowledge_retrieval import KnowledgeRetrievalComponent
from server.workflow.utils.inputs import *
from server.workflow.utils.outputs import *

root_path = Path(__file__).parent.parent.parent
sys.path.append(str(root_path))


@pytest.mark.asyncio
async def test_workflow():
    from server.chat.workflow_chat import do_workflow_chat

    # 评分案例+评分过程
    flow = {"nodes": [{"node": {"id": "chat_input-5vKzBR", "name": "chat_input", "display_name": "聊天输入", "description": "获取聊天输入", "tag": "输入", "icon": None, "inputs": [{"id": "query-4Vwqnv", "name": "query", "display_name": "查询内容", "required": True, "enable_expr": True, "info": "输入的问题内容", "options": [], "field_type": "str", "value": "", "type": "TextInput"}, {"id": "history_len-Zk3tiv", "name": "history_len", "display_name": "历史对话轮次", "required": False, "enable_expr": True, "info": "传递给LLM的历史消息的最大数量", "options": [], "field_type": "int", "value": -1, "type": "IntegerInput"}, {"id": "conversation_id-bfqUtM", "name": "conversation_id", "display_name": "会话ID", "required": False, "enable_expr": True, "info": "聊天的会话ID，如果为空将自动生成", "options": [], "field_type": "str", "value": None, "type": "TextInput"}, {"id": "knowledge_id-JpUhAp", "name": "knowledge_id", "display_name": "知识ID", "required": False, "enable_expr": True, "info": "附件上传后返回的ID", "options": [], "field_type": "str", "value": None, "type": "TextInput"}, {"id": "store_message-wtzxma", "name": "store_message", "display_name": "是否存储对话", "required": False, "enable_expr": True, "info": "是否将对话存储到数据库中", "options": [], "field_type": "bool", "value": True, "type": "BooleanInput"}, {"id": "extra-3ngNA9", "name": "extra", "display_name": "额外信息", "required": False, "enable_expr": True, "info": "传递给聊天的额外输入", "options": [], "field_type": "dict", "value": {}, "type": "DictInput"}], "outputs": [], "type": "ChatInputComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "knowledge_retrieval-4792j7", "name": "knowledge_retrieval", "display_name": "知识检索", "description": "使用嵌入模型从向量存储中检索知识", "tag": "工具", "icon": None, "inputs": [{"id": "query-tw2p9U", "name": "query", "display_name": "查询内容", "required": True, "enable_expr": True, "info": "输入的问题内容", "options": [], "field_type": "str", "value": "{{ chat_input-5vKzBR.inputs.extra.background }}", "type": "TextInput"}, {"id": "knowledge_base_names-g9hoKD", "name": "knowledge_base_names", "display_name": "知识库名称", "required": False, "enable_expr": True, "info": "可用于LLM的知识库名称", "options": [], "field_type": "list", "value": ["dispatch_evaluate"], "type": "ListInput"}, {"id": "top_k-37QLuR", "name": "top_k", "display_name": "Top K", "required": False, "enable_expr": True, "info": "知识库文档匹配的最大数量", "options": [], "field_type": "int", "value": 3, "type": "IntegerInput"}, {"id": "score_threshold-3LSDnR", "name": "score_threshold", "display_name": "相似度阈值", "required": False, "enable_expr": True, "info": "知识库匹配相关性阈值，值范围在0到1之间，较小的分数表示更高的相关性", "options": [], "field_type": "float", "value": 1.0, "type": "FloatInput"}, {"id": "only_content-3NyNH5", "name": "only_content", "display_name": "Only Content", "required": False, "enable_expr": True, "info": "Only content will concat all page content into one piece for similarity search", "options": [], "field_type": "bool", "value": True, "type": "BooleanInput"}], "outputs": [{"id": "document-v8Ezoc", "name": "document", "display_name": "文档", "info": None, "enable_expr": False, "field_type": "list", "value": None, "type": "ListOutput"}], "type": "KnowledgeRetrievalComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "local_llm-3WB2UN", "name": "local_llm", "display_name": "本地LLM", "description": "使用本地LLM生成文本", "tag": "模型", "icon": None, "inputs": [{"id": "query-Uvoc8F", "name": "query", "display_name": "Text", "required": True, "enable_expr": True, "info": "Message to be passed as input.", "options": [], "field_type": "str", "value": "", "type": "TextInput"}, {"id": "assistant_code-QBGpih", "name": "assistant_code", "display_name": "助手编码", "required": False, "enable_expr": True, "info": "助手的唯一编码", "options": [], "field_type": "str", "value": "BSS-BASE-QM", "type": "TextInput"}, {"id": "temperature-GoGEud", "name": "temperature", "display_name": "Temperature", "required": False, "enable_expr": True, "info": None, "options": [], "field_type": "float", "value": 0.1, "type": "FloatInput"}, {"id": "prompt-8HRAPU", "name": "prompt", "display_name": "Prompt", "required": False, "enable_expr": True, "info": "Prompt for chat.", "options": [], "field_type": "str", "value": "你是一个资深的系统运维专家，通过以下给定的告警调度单信息，对客服的回复内容进行评估打分并给出修改建议。\n                    <调度单信息>\n                    {{ chat_input-5vKzBR.inputs.extra.background }}\n                    </调度单信息>\n                    <客服的回复内容>\n                    {{ chat_input-5vKzBR.inputs.query }}\n                    </客服的回复内容>\n                    你可以参考以下历史评分案例，但是不要直接使用里面的评分数据：\n                    <历史评分案例>\n                    {{ knowledge_retrieval-4792j7.outputs.document }}\n                    </历史评分案例>\n                    不要直接使用历史评分案例里面的评分数据！不要直接使用历史评分案例里面的评分数据！不要直接使用历史评分案例里面的评分数据！\n                    现在请深吸一口气，让我们一步一步来思考，请根据以下规则进行评分：\n                    1. 分数范围： 最低分0分，最高分100分\n                    2. 以下是四个维度的评分规则：\n                        ## 一、调度单填写合规性（满分15分）\n                        * 直接给固定分数{{ chat_input-5vKzBR.inputs.extra.compliance_score }}分\n                        ## 二、原因分析质量（满分35分）\n                        注：原因分析为空或纯数字字母时此维度只能得0分，例如：“无”“/”“123”“abc”。\n                        ### 原因分析的信息完备性（满分25分）\n                        * 16-25分：在问题定位方面，能够明确定位问题现象，明确具体系统处理环节、系统组件、业务规则或数据字段，例如：“VoLTE 话单中 access - domain 字段未填写区号”“错单原因是计费号码到访地区号是字母，如 1027027”。同时，在原因分析上，包含具体的实例数据，支撑充分，例如：明确 “错单号码 18905320258”“具体 IMSI 号段 46011052776”“发生于 4 日凌晨”“F600 错误码”“涉及 12 个空文件”。\n                        * 6-15分：仅描述问题表面现象，未指出源头。例如：“话单解析为空”“错单描述为空”“数据异常”。并且原因分析仅有非常模糊的描述，缺乏关键信息，例如：“参数更新”没有说明具体的参数信息、“个别错单”未量化、“出库异常”缺少异常的详细说明。\n                        * 0-5分：问题定位模糊或缺失，例如：“核实正常”“核查无问题”“分析中”。同时，原因分析几乎无任何具体细节，例如：“上海核查正常”“资料异常”“网元问题”。\n                        ### 错误分类与原因分析匹配度（满分10分）\n                        * 7-10分：选择的`错误原因分类`（如业务平台、其他原因等）与填写`原因分析`描述的内容高度匹配。\n                        * 3-6分：大致匹配，但略有偏差。\n                        * 0-2分：完全不符合或相互矛盾，例如：分类选“其他原因”，但分析内容是“业务平台参数配置错误”；或分类选“业务平台”，但分析写“集团未下发”。\n                        ## 三、解决措施质量（满分35分）\n                        注：解决措施为空或纯数字字母时此维度只能得0分，例如：“无”“/”“123”“abc”。\n                        ### 解决措施的信息完备性（满分25分）\n                        * 16-25分：在解决措施明确性方面，包含具体措施，明确牵头方，并协调相关上下游解决处理，措施明确可执行。同时，在解决措施的信息完备性上，措施包含具体的操作步骤、方法、技术方案或参数调整项。例如1：“运维部牵头协调网元侧与计费系统，具体步骤为导出异常用户清单、执行 SQL 脚本更新数据库字段、重新触发同步任务以完成用户资料同步”。例如2：“技术部负责调整拣重配置规则中的时间窗口参数，明确将原 30 分钟窗口调整为 60 分钟，并同步至上下游系统”。\n                        * 6-15分：解决措施明确性表现为措施较模糊，无法判断具体的优化操作。例如：“已处理”“进一步分析”“持续跟踪”。解决措施的信息完备性仅有非常初步的想法或计划。例如：“待测试”“待处理”。\n                        * 0-5分：解决措施明确性上未提出任何实质性措施，或措施完全不可行，例如：“标记不涉及”“请集团谅解”。同时，解决措施的信息完整性无任何实施细节。\n                        ### 原因分析与采取措施匹配度（满分10分）\n                        * 7-10分：所述“采取措施”与“原因分析”指出的问题一一对应，形成闭环，分析出的原因在措施中得到直接解决。\n                        * 3-6分：大致匹配，措施与原因部分相关。\n                        * 0-2分：措施与原因分析完全无关，或者未提出任何具体措施。\n                        ## 四、调度单回复及时性（满分15分）\n                        * 直接给固定分数{{ chat_input-5vKzBR.inputs.extra.timeliness_score }}分\n                    3. 每一个子项的得分是一个区间范围，请先确定评分区间范围，然后每个不足之处在区间范围内酌情扣分\n                    4. 计算过程，请严格按照实际数值进行科学严谨的数学计算：每个维度的得分等于每个维度下的子项得分之和\n                    5. 最终分数必须在分数范围内\n                    请按照以下json格式（必须用双引号包裹key和value）直接输出，不允许包含其他字符：{\"short_reason\":{\"r1\":\"一句话说明调度单填写合规性评分过程和得分情况\",\"r2\":{\"r2.1\":\"一句话说明原因分析的信息完备性的评分过程和得分情况\",\"r2.2\":\"一句话说明错误分类与原因分析匹配度的评分过程和得分情况\"},\"r3\":{\"r3.1\":\"一句话说明解决措施的信息完备性的评分过程和得分情况\",\"r3.2\":\"一句话说明原因分析与采取措施匹配度的评分过程和得分情况\"},\"r4\":\"一句话说明调度单回复及时性评分过程和得分情况\"}, \"scores\":{\"r1\":\"调度单填写合规性得分\",\"r2\":{\"r2.1\":\"原因分析的信息完备性得分\",\"r2.2\":\"错误分类与原因分析匹配度得分\"},\"r3\":{\"r3.1\":\"解决措施的信息完备性得分\",\"r3.2\":\"原因分析与采取措施匹配度得分\"},\"r4\":\"调度单回复及时性得分\"}, \"suggest\":\"仅针对没有得满分的项，对原因分析和采取措施的内容提出改进建议，判断是否需要修改原因分类，无需改进时请给出友好的回复，纯文本输出\"}", "type": "TextInput"}, {"id": "model_name-4RbEUs", "name": "model_name", "display_name": "Model Name", "required": True, "enable_expr": True, "info": "The name of LLM.", "options": ["qwen-api"], "field_type": "str", "value": "qwen-api", "type": "TextInput"}], "outputs": [{"id": "answer-AQeseq", "name": "answer", "display_name": "答案", "info": None, "enable_expr": False, "field_type": "str", "value": None, "type": "TextOutput"}, {"id": "docs-4HxeTe", "name": "docs", "display_name": "文档", "info": None, "enable_expr": False, "field_type": "list", "value": None, "type": "ListOutput"}, {"id": "thought-ZfhrML", "name": "thought", "display_name": "思考过程", "info": None, "enable_expr": False, "field_type": "str", "value": None, "type": "TextOutput"}], "type": "LocalLLMComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "python_repl-HM5eAn", "name": "python_repl", "display_name": "Python执行", "description": "执行Python代码", "tag": "工具", "icon": None, "inputs": [{"id": "args-dxYKvQ", "name": "args", "display_name": "Args", "required": False, "enable_expr": True, "info": "The args for python function.", "options": [], "field_type": "dict", "value": {"arg1": "{{ local_llm-3WB2UN.outputs.answer }}"}, "type": "DictInput"}, {"id": "python_code-3iL2A4", "name": "python_code", "display_name": "Python", "required": True, "enable_expr": True, "info": "python code.", "options": [], "field_type": "str", "value": "def main(arg1: str) -> str:\n                import json\n                import re\n                if \"```\" in arg1:\n                    match = re.search(r'```(json)?(.*?)```', arg1, re.DOTALL)\n                    if match:\n                        arg1 = match.group(2)\n                a = json.loads(arg1)\n                scores = a.get('scores',{})\n                total_score = int(scores.get('r1',0)) + int(scores.get('r2',{}).get('r2.1',0)) + int(scores.get('r2',{}).get('r2.2',0)) + int(scores.get('r3',{}).get('r3.1',0)) + int(scores.get('r3',{}).get('r3.2',0)) + int(scores.get('r4',0))\n                return json.dumps({\"score\": total_score, \"suggest\": f\"评估得分：{total_score}分；\\n改进建议：{a.get('suggest')}\"},ensure_ascii=False)\n            ", "type": "TextInput"}], "outputs": [{"id": "result-K44xrj", "name": "result", "display_name": "结果", "info": None, "enable_expr": False, "field_type": "dict", "value": {}, "type": "DictOutput"}], "type": "PythonREPLComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "chat_output-3WG5KZ", "name": "chat_output", "display_name": "聊天输出", "description": "获取聊天输出", "tag": "输出", "icon": None, "inputs": [], "outputs": [{"id": "answer-48DyCZ", "name": "answer", "display_name": "Answer", "info": None, "enable_expr": True, "field_type": "str", "value": "{{ python_repl-HM5eAn.outputs.result }}", "type": "TextOutput"}], "type": "ChatOutputComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}], "edges": [{"source": "chat_input-5vKzBR", "target": "knowledge_retrieval-4792j7"}, {"source": "knowledge_retrieval-4792j7", "target": "local_llm-3WB2UN"}, {"source": "local_llm-3WB2UN", "target": "python_repl-HM5eAn"}, {"source": "python_repl-HM5eAn", "target": "chat_output-3WG5KZ"}]}

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
采取措施：暂无
原因分析：1、7月非周期套餐用户出账，出账金额较高。2、全省集中催欠，待列转收多，导致用户数和收入都有增长，经核查，出账无误
完成状态：已完成
完成时间：2025-08-01 00:00:00
        """, assistant_id=-1,
        extra={
            "compliance_score": 15,
            "timeliness_score": 15,
            "background": """
            错单描述：202507账期云南省红河(个旧)分公司(873)上传出账数据异常，其中：上期出账用户数:1893071,本期出账用户数1917783,出账用户数环比为:1.31%,波动超1%。
202507账期云南省昭通分公司(870)上传出账数据异常，其中：上期出账金额:52046635.61元,本期出账金额:59229917.85元,出账金额环比为:13.80%,波动超3%。
202507账期云南省怒江(六库)分公司(886)上传出账数据异常，其中：上期出账用户数:435287,本期出账用户数:440106,出账用户数环比为:1.11%,波动超1%。上期出账金额:14974417.45元,本期出账金额:14184464.83元,出账金额环比为:-5.28%,波动超3%。
202507账期云南省玉溪分公司(877)上传出账数据异常，其中：上期出账用户数:1624485,本期出账用户数:1641674,出账用户数环比为:1.06%,波动超1%。上期出账金额:48851904.06元,本期出账金额:46736338.41元,出账金额环比为:-4.33%,波动超3%。
202507账期云南省昆明市(871)上传出账数据异常，其中：上期出账金额:297073383.74元,本期出账金额:270863982.38元,出账金额环比为:-8.82%,波动超3%。
202507账期云南省楚雄分公司(878)上传出账数据异常，其中：上期出账用户数:1976121,本期出账用户数:2013934,出账用户数环比为:1.91%,波动超1%。上期出账金额:65769876.32元,本期出账金额:57864340.50元,出账金额环比为:-12.02%,波动超3%。
202507账期云南省丽江分公司(888)上传出账数据异常，其中：上期出账金额:25227996.28元,本期出账金额:23604660.57元,出账金额环比为:-6.43%,波动超3%。
202507账期云南省德宏(潞西)分公司(692)上传出账数据异常，其中：上期出账用户数:994402,本期出账用户数:1006926,出账用户数环比为:1.26%,波动超1%。上期出账金额:29547981.26元,本期出账金额:31952921.44元,出账金额环比为:8.14%,波动超3%。
202507账期云南省曲靖分公司(874)上传出账数据异常，其中：上期出账金额:98316991.14元,本期出账金额:95241038.43元,出账金额环比为:-3.13%,波动超3%。
202507账期云南省思茅分公司(879)上传出账数据异常，其中：上期出账用户数:1925067,本期出账用户数:1945232,出账用户数环比为:1.05%,波动超1%。上期出账金额:59945676.00元,本期出账金额:63231953.72元,出账金额环比为:5.48%,波动超3%。
202507账期云南省保山分公司(875)上传出账数据异常，其中：上期出账用户数:1730076,本期出账用户数:1753500,出账用户数环比为:1.35%,波动超1%。上期出账金额:53900561.83元,本期出账金额:51599501.55元,出账金额环比为:-4.27%,波动超3%。
202507账期云南省大理分公司(872)上传出账数据异常，其中：上期出账金额:68346028.61元,本期出账金额:62895619.83元,出账金额环比为:-7.97%,波动超3%。
202507账期云南省文山分公司(876)上传出账数据异常，其中：上期出账用户数:1830751,本期出账用户数1856337,出账用户数环比为:1.40%,波动超1%。
202507账期云南省迪庆(中甸)分公司(887)上传出账数据异常，其中：上期出账用户数:276619,本期出账用户数:283075,出账用户数环比为:2.33%,波动超1%。上期出账金额:15054225.29元,本期出账金额:12841464.37元,出账金额环比为:-14.70%,波动超3%。
202507账期云南省版纳(景洪)分公司(691)上传出账数据异常，其中：上期出账用户数:1433488,本期出账用户数1455410,出账用户数环比为:1.53%,波动超1%。
202507账期云南省临沧分公司(883)上传出账数据异常，其中：上期出账用户数:1426545,本期出账用户数:1441475,出账用户数环比为:1.05%,波动超1%。上期出账金额:49807635.11元,本期出账金额:55203237.60元,出账金额环比为:10.83%,波动超3%。
            """,
        }, workflow_config=flow, stream=True, store_message=False)

    # flow = {"nodes": [{"node": {"id": "chat_input-4AMoyb", "name": "chat_input", "display_name": "聊天输入", "description": "获取聊天输入", "tag": "输入", "icon": None, "inputs": [{"id": "query-44RYJX", "name": "query", "display_name": "查询内容", "required": True, "enable_expr": True, "info": "输入的问题内容", "options": [], "field_type": "str", "value": "", "type": "TextInput"}, {"id": "history_len-3yWnTh", "name": "history_len", "display_name": "历史对话轮次", "required": False, "enable_expr": True, "info": "传递给LLM的历史消息的最大数量", "options": [], "field_type": "int", "value": -1, "type": "IntegerInput"}, {"id": "conversation_id-DQU3RR", "name": "conversation_id", "display_name": "会话ID", "required": False, "enable_expr": True, "info": "聊天的会话ID，如果为空将自动生成", "options": [], "field_type": "str", "value": None, "type": "TextInput"}, {"id": "knowledge_id-3HxYL6", "name": "knowledge_id", "display_name": "知识ID", "required": False, "enable_expr": True, "info": "附件上传后返回的ID", "options": [], "field_type": "str", "value": None, "type": "TextInput"}, {"id": "store_message-StURc9", "name": "store_message", "display_name": "是否存储对话", "required": False, "enable_expr": True, "info": "是否将对话存储到数据库中", "options": [], "field_type": "bool", "value": True, "type": "BooleanInput"}, {"id": "extra-woAbVe", "name": "extra", "display_name": "额外信息", "required": False, "enable_expr": True, "info": "传递给聊天的额外输入", "options": [], "field_type": "dict", "value": {}, "type": "DictInput"}], "outputs": [], "type": "ChatInputComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "local_llm-3FF8pi", "name": "local_llm", "display_name": "本地LLM", "description": "使用本地LLM生成文本", "tag": "模型", "icon": None, "inputs": [{"id": "query-3AGc2m", "name": "query", "display_name": "Text", "required": True, "enable_expr": True, "info": "Message to be passed as input.", "options": [], "field_type": "str", "value": "", "type": "TextInput"}, {"id": "temperature-fgeYex", "name": "temperature", "display_name": "Temperature", "required": False, "enable_expr": True, "info": None, "options": [], "field_type": "float", "value": 0.1, "type": "FloatInput"}, {"id": "prompt-4BazPb", "name": "prompt", "display_name": "Prompt", "required": False, "enable_expr": True, "info": "Prompt for chat.", "options": [], "field_type": "str", "value": "你是一名专业的系统运维分析师，请严格根据以下提供的告警工单信息和省份回复内容进行分析{{ input }}：\n                <告警工单信息>\n                {{ chat_input-4AMoyb.inputs.query }}\n                </告警工单信息>\n                <省份回复内容>\n                {{ chat_input-4AMoyb.inputs.extra.background }}\n                </省份回复内容>\n                请严格按照以下要求一步一步输出纯文本，不得使用任何括号，删除所有括号内的内容：\n                1. 第一段内容：此次告警涉及xxx等省份（包括省份回复里面的所有省份），通过省份回复分析得出xxx等省份核查正常，xxx等省份核查异常（正常和异常的省份加起来为所有省份，但是同一个省份只能出现一次）\n                2. 第二段内容：原因分类主要为：1、原因分类名称：罗列涉及的省份名称；2、依此类推...(对所有省份的原因分类进行分组合并，原因分类名称是固定值，不可以从原因分析里面提取，找不到原因分类的名称，则不输出该原因分类名称)\n                3. 第三段内容：原因措施包含：1、省份名称：xxx，原因分析：xxx，采取措施：xxx，完成状态：xxx；2、依此类推...（按照上面核查异常的省份一一列举并总结概括省份的原因分析和处理措施，必须保留省份的信息和序号）\n                4. 第四段内容：建议：(从异常省份的问题处理情况的后续跟进方向考虑，用于领导汇报)\n                ", "type": "TextInput"}, {"id": "model_name-3VUxRq", "name": "model_name", "display_name": "Model Name", "required": True, "enable_expr": True, "info": "The name of LLM.", "options": ["qiming-api"], "field_type": "str", "value": "qwen-api", "type": "TextInput"}], "outputs": [{"id": "answer-LvrU3T", "name": "answer", "display_name": "答案", "info": None, "enable_expr": False, "field_type": "str", "value": None, "type": "TextOutput"}, {"id": "docs-3c6Npr", "name": "docs", "display_name": "文档", "info": None, "enable_expr": False, "field_type": "list", "value": None, "type": "ListOutput"}, {"id": "thought-4hZN7F", "name": "thought", "display_name": "思考过程", "info": None, "enable_expr": False, "field_type": "str", "value": None, "type": "TextOutput"}], "type": "LocalLLMComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "chat_output-3eAmzE", "name": "chat_output", "display_name": "聊天输出", "description": "获取聊天输出", "tag": "输出", "icon": None, "inputs": [], "outputs": [{"id": "answer-3yTdcc", "name": "answer", "display_name": "Answer", "info": None, "enable_expr": True, "field_type": "str", "value": "{{ local_llm-3FF8pi.outputs.answer }}", "type": "TextOutput"}], "type": "ChatOutputComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}], "edges": [{"source": "chat_input-4AMoyb", "target": "local_llm-3FF8pi"}, {"source": "local_llm-3FF8pi", "target": "chat_output-3eAmzE"}]}
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
    knowledge_retrieval = KnowledgeRetrievalComponent(inputs=[
        TextInput(
            name='query',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_QUERY}",
            required=True,
            info="${WORKFLOW_INPUT_INFO_QUERY}",
            value=f'{{{{ {background_var} }}}}'
        ),
        ListInput(
            name='knowledge_base_names',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_KNOWLEDGE_BASE_NAMES}",
            info="${WORKFLOW_INPUT_INFO_KNOWLEDGE_BASE_NAMES}",
            value=['dispatch_evaluate']
        ),
        IntegerInput(
            name='top_k',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_TOP_K}",
            info="${WORKFLOW_INPUT_INFO_TOP_K}",
            value=3
        ),
        FloatInput(
            name='score_threshold',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_SCORE_THRESHOLD}",
            info="${WORKFLOW_INPUT_INFO_SCORE_THRESHOLD}",
            value=1
        ),
        BooleanInput(
            name="only_content",
            display_name="Only Content",
            info="Only content will concat all page content into one piece for similarity search",
            value=True
        ),
    ])
    score_case_var = knowledge_retrieval.id + ".outputs.document"
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
            value=0.1
        ),
        TextInput(
            name='prompt',
            display_name='Prompt',
            info='Prompt for chat.',
            value=f"""你是一个资深的系统运维专家，通过以下给定的告警调度单信息，对客服的回复内容进行评估打分并给出修改建议。
                    <调度单信息>
                    {{{{ {background_var} }}}}
                    </调度单信息>
                    <客服的回复内容>
                    {{{{ {query_var} }}}}
                    </客服的回复内容>
                    你可以参考以下历史评分案例，但是不要直接使用里面的评分数据：
                    <历史评分案例>
                    {{{{ {score_case_var} }}}}
                    </历史评分案例>
                    不要直接使用历史评分案例里面的评分数据！不要直接使用历史评分案例里面的评分数据！不要直接使用历史评分案例里面的评分数据！
                    现在请深吸一口气，让我们一步一步来思考，请根据以下规则进行评分：
                    1. 分数范围： 最低分0分，最高分100分
                    2. 以下是四个维度的评分规则：
                        ## 一、调度单填写合规性（满分15分）
                        * 直接给固定分数{{{{ {compliance_score_var} }}}}分
                        ## 二、原因分析质量（满分35分）
                        注：原因分析为空或纯数字字母时此维度只能得0分，例如：“无”“/”“123”“abc”。
                        ### 原因分析的信息完备性（满分25分）
                        * 16-25分：在问题定位方面，能够明确定位问题现象，明确具体系统处理环节、系统组件、业务规则或数据字段，例如：“VoLTE 话单中 access - domain 字段未填写区号”“错单原因是计费号码到访地区号是字母，如 1027027”。同时，在原因分析上，包含具体的实例数据，支撑充分，例如：明确 “错单号码 18905320258”“具体 IMSI 号段 46011052776”“发生于 4 日凌晨”“F600 错误码”“涉及 12 个空文件”。
                        * 6-15分：仅描述问题表面现象，未指出源头。例如：“话单解析为空”“错单描述为空”“数据异常”。并且原因分析仅有非常模糊的描述，缺乏关键信息，例如：“参数更新”没有说明具体的参数信息、“个别错单”未量化、“出库异常”缺少异常的详细说明。
                        * 0-5分：问题定位模糊或缺失，例如：“核实正常”“核查无问题”“分析中”。同时，原因分析几乎无任何具体细节，例如：“上海核查正常”“资料异常”“网元问题”。
                        ### 错误分类与原因分析匹配度（满分10分）
                        * 7-10分：选择的`错误原因分类`（如业务平台、其他原因等）与填写`原因分析`描述的内容高度匹配。
                        * 3-6分：大致匹配，但略有偏差。
                        * 0-2分：完全不符合或相互矛盾，例如：分类选“其他原因”，但分析内容是“业务平台参数配置错误”；或分类选“业务平台”，但分析写“集团未下发”。
                        ## 三、解决措施质量（满分35分）
                        注：解决措施为空或纯数字字母时此维度只能得0分，例如：“无”“/”“123”“abc”。
                        ### 解决措施的信息完备性（满分25分）
                        * 16-25分：在解决措施明确性方面，包含具体措施，明确牵头方，并协调相关上下游解决处理，措施明确可执行。同时，在解决措施的信息完备性上，措施包含具体的操作步骤、方法、技术方案或参数调整项。例如1：“运维部牵头协调网元侧与计费系统，具体步骤为导出异常用户清单、执行 SQL 脚本更新数据库字段、重新触发同步任务以完成用户资料同步”。例如2：“技术部负责调整拣重配置规则中的时间窗口参数，明确将原 30 分钟窗口调整为 60 分钟，并同步至上下游系统”。
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
                    请按照以下json格式（必须用双引号包裹key和value）直接输出，不允许包含其他字符：""" + "{\"short_reason\":{\"r1\":\"一句话说明调度单填写合规性评分过程和得分情况\",\"r2\":{\"r2.1\":\"一句话说明原因分析的信息完备性的评分过程和得分情况\",\"r2.2\":\"一句话说明错误分类与原因分析匹配度的评分过程和得分情况\"},\"r3\":{\"r3.1\":\"一句话说明解决措施的信息完备性的评分过程和得分情况\",\"r3.2\":\"一句话说明原因分析与采取措施匹配度的评分过程和得分情况\"},\"r4\":\"一句话说明调度单回复及时性评分过程和得分情况\"}, \"scores\":{\"r1\":\"调度单填写合规性得分\",\"r2\":{\"r2.1\":\"原因分析的信息完备性得分\",\"r2.2\":\"错误分类与原因分析匹配度得分\"},\"r3\":{\"r3.1\":\"解决措施的信息完备性得分\",\"r3.2\":\"原因分析与采取措施匹配度得分\"},\"r4\":\"调度单回复及时性得分\"}, \"suggest\":\"仅针对没有得满分的项，对原因分析和采取措施的内容提出改进建议，判断是否需要修改原因分类，无需改进时请给出友好的回复，纯文本输出\"}"
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
                total_score = int(scores.get('r1',0)) + int(scores.get('r2',{}).get('r2.1',0)) + int(scores.get('r2',{}).get('r2.2',0)) + int(scores.get('r3',{}).get('r3.1',0)) + int(scores.get('r3',{}).get('r3.2',0)) + int(scores.get('r4',0))
                return json.dumps({"score": total_score, "suggest": f"评估得分：{total_score}分；\\n改进建议：{a.get('suggest')}"},ensure_ascii=False)
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
                     {"node": knowledge_retrieval, "position": position},
                     {"node": model, "position": position},
                     {"node": python_repl, "position": position},
                     {"node": chat_output, "position": position},
                     ]
    flow['edges'] = [{
        "source": chat_input.id,
        "target": knowledge_retrieval.id,
    }, {
        "source": knowledge_retrieval.id,
        "target": model.id
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
