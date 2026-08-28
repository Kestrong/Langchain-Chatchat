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

    flow = {"nodes": [{"node": {"id": "chat_input-PBYTfP", "name": "chat_input", "display_name": "聊天输入", "description": "获取聊天输入", "tag": "输入", "icon": None, "inputs": [{"id": "query-z3dHNE", "name": "query", "display_name": "查询内容", "required": True, "enable_expr": True, "info": "输入的问题内容", "options": [], "field_type": "str", "value": "", "type": "TextInput"}, {"id": "history_len-3KciqM", "name": "history_len", "display_name": "历史对话轮次", "required": False, "enable_expr": True, "info": "传递给LLM的历史消息的最大数量", "options": [], "field_type": "int", "value": -1, "type": "IntegerInput"}, {"id": "conversation_id-SenBQU", "name": "conversation_id", "display_name": "会话ID", "required": False, "enable_expr": True, "info": "聊天的会话ID，如果为空将自动生成", "options": [], "field_type": "str", "value": None, "type": "TextInput"}, {"id": "knowledge_id-43VK8G", "name": "knowledge_id", "display_name": "知识ID", "required": False, "enable_expr": True, "info": "附件上传后返回的ID", "options": [], "field_type": "str", "value": None, "type": "TextInput"}, {"id": "store_message-4PiDcG", "name": "store_message", "display_name": "是否存储对话", "required": False, "enable_expr": True, "info": "是否将对话存储到数据库中", "options": [], "field_type": "bool", "value": True, "type": "BooleanInput"}, {"id": "extra-3Su9V5", "name": "extra", "display_name": "额外信息", "required": False, "enable_expr": True, "info": "传递给聊天的额外输入", "options": [], "field_type": "dict", "value": {}, "type": "DictInput"}], "outputs": [], "type": "ChatInputComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "python_repl-3rPiNu", "name": "python_repl", "display_name": "Python执行", "description": "执行Python代码", "tag": "工具", "icon": None, "inputs": [{"id": "args-TLg63f", "name": "args", "display_name": "Args", "required": False, "enable_expr": True, "info": "The args for python function.", "options": [], "field_type": "dict", "value": {"error_class_name": "{{ chat_input-PBYTfP.inputs.extra.error_class_name  }}", "query": "{{ chat_input-PBYTfP.inputs.query  }}", "background": "{{ chat_input-PBYTfP.inputs.extra.background  }}", "compliance_score": "{{ chat_input-PBYTfP.inputs.extra.compliance_score  }}", "timeliness_score": "{{ chat_input-PBYTfP.inputs.extra.timeliness_score  }}"}, "type": "DictInput"}, {"id": "python_code-3CnrBi", "name": "python_code", "display_name": "Python", "required": True, "enable_expr": True, "info": "python code.", "options": [], "field_type": "str", "value": "async def main(error_class_name: str, query: str, background: str, compliance_score: str,\n               timeliness_score: str):\n    import json\n    import re\n    import random\n\n    from configs import LLM_MODELS\n    from server.workflow.component.models.local_llm import LocalLLMComponent\n    from server.workflow.utils.inputs import TextInput, FloatInput\n    ISSUE_CATEGORIES = {\n        \"流程催办类\": [\n            \"调研\",\n            \"出账信息填报\"\n        ],\n        \"核查确认类\": [\n            \"环比波动异常\",\n            \"国内数据高额高频下发\",\n            \"出账环比波动\",\n            \"基站数据求取不到\"\n        ],\n        \"问题处理类\": [\n            \"省份文件缺失\",\n            \"省上传文件数不平衡\",\n            \"省上传文件数不完整\",\n            \"话单上传及时率低于阈值异常\",\n            \"其他\",\n            \"通信链路异常\",\n            \"省上传错单\",\n            \"省上传拒收\",\n            \"省份消息接收失败\",\n            \"集团下发错单\",\n            \"集团下发拒收\",\n            \"省文件序列号缺漏\",\n            \"省上传跳号\",\n            \"基础信息缺漏\",\n            \"出账上传质量\",\n            \"政企稽核情况调度\",\n            \"自动拨测\",\n            \"省上传空文件\",\n            \"省上传延迟话单\",\n            \"省未及时上传文件\"\n        ]\n    }\n    error_type_to_issue_category = {\n        error: category\n        for category, errors in ISSUE_CATEGORIES.items()\n        for error in errors\n    }\n    error_class_name = error_class_name.strip()\n    score_rule_map = {\n        \"问题处理类\": {\n            \"rule\": f\"\"\"\n            请按照以下规则进行评分：\n            1. 分数范围： 最低分0分，最高分100分\n            2. 以下是四个维度的评分规则：\n                # 前提条件：\n                1. 调度单信息和回复内容作为一个整体进行评分，不是单独针对某个字段，其他字段已给出的信息均可以作为补充内容进行评分。\n                2. 如果为上下游外部原因导致，非己方问题，可以无需采取措施，仅须通知并协调责任方处理。\n                3. 每个维度之间需要关联打分，需考虑维度之间的关联性。\n                ** 请牢记此前提，所有规则都在要在此前提下进行！！！**\n                ## 一、调度单填写合规性（满分15分）\n                * 直接给固定分数{compliance_score}分\n                ## 二、原因分析质量（满分35分）\n                注：原因分析为空或纯数字字母时此维度只能得0分，例如：“无”“/”“123”“abc”。\n                ### 原因分析的信息完备性（满分25分）\n                * 0-3分：完全没有针对问题的原因分析，或回复内容属于无效的客套话、流程性回复，不包含任何实质性信息。例如：“已通知相关人员处理”“已安排补传”“请集团知晓”“分析中”“持续关注”等。\n                * 4-9分：问题描述过于笼统、模糊，缺乏具体的场景或细节，导致难以判断具体发生了什么问题。\n                * 10-17分：能够准确描述问题的表面现象或报错信息，但未进一步指出问题源头，或缺乏定位问题所需的关键细节（如具体字段、组件等）。\n                * 18-25分：能够深入定位问题根源，不仅明确问题现象，还能精准提供系统处理环节、系统组件、业务规则、上下游原因（集团、下级、外部系统）或具体数据字段等关键定位信息中的至少一项，例如：“VoLTE 话单中 access - domain 字段未填写区号”“错单原因是计费号码到访地区号是字母，如 1027027”。\n                ### 错误分类与原因分析匹配度（满分10分）\n                * 0-4分：完全不符合或相互矛盾，例如：分类选“网络问题”，但分析内容是“业务平台参数配置错误”。\n                * 5-7分：大致匹配，但略有偏差。\n                * 8-10分：选择的`错误原因分类`与填写`原因分析`描述的内容高度匹配。\n                ## 三、解决措施质量（满分35分）\n                注：采取措施为空或纯数字字母时此维度只能得0分，例如：“无”“/”“123”“abc”。\n                ### 解决措施的信息完备性（满分25分）\n                * 0-3分：未提出任何实质性措施，或措施完全不可行、属于推诿性回复；无任何实施细节，属于无效沟通。\n                * 4-9分：仅提出了极其宽泛的方向或原则性建议，未落实到具体动作，难以直接指导执行；基本无实施细节，或细节与实际解决问题关联度极低。\n                * 10-17分：虽然提及了处理方向，但措施表述较为模糊，无法准确判断具体的优化操作；或仅有非常初步的想法、计划及待办状态，缺乏实质性内容。\n                * 18-25分：在解决措施明确性方面，包含具体措施，明确牵头方，并协调相关上下游解决处理，措施明确可执行。同时，在解决措施的信息完备性上，措施包含具体的操作步骤、方法。\n                ### 原因分析与采取措施匹配度（满分10分）\n                * 0-4分：措施与原因分析完全无关，或者未提出任何具体措施。\n                * 5-7分：大致匹配，措施与原因部分相关。\n                * 8-10分：所述“采取措施”与“原因分析”指出的问题一一对应，形成闭环，分析出的原因在措施中得到直接解决。\n                ## 四、调度单回复及时性（满分15分）\n                    * 直接给固定分数{timeliness_score}分\n            3. 每一个子项的得分是一个区间范围，请先确定评分区间范围，然后酌情给分\n            4. 最终分数必须在分数范围内\n            \"\"\",\n            \"output\": {\n                \"evaluate_report\": {\n                    \"r1\": {\n                        \"explanation\": \"固定得分\",\n                        \"score\": \"调度单填写合规性得分\"\n                    },\n                    \"r2\": {\n                        \"r2.1\": {\n                            \"explanation\": \"先深度思考，然后输出原因分析的信息完备性的详细评分过程\",\n                            \"grade\": \"原因分析的信息完备性的评级（例如：优秀(18-25分)、一般(10-17分)、较差(4-9分)、无效(0-3分)）\",\n                            \"score\": \"原因分析的信息完备性得分\"\n                        },\n                        \"r2.2\": {\n                            \"explanation\": \"先深度思考，然后输出错误分类与原因分析匹配度的详细评分过程\",\n                            \"grade\": \"错误分类与原因分析匹配度的评级（例如：匹配(8-10分)、大致匹配(5-7分)、不匹配(0-4分)）\",\n                            \"score\": \"错误分类与原因匹配度得分\"\n                        }\n                    },\n                    \"r3\": {\n                        \"r3.1\": {\n                            \"explanation\": \"先深度思考，然后输出解决措施的信息完备性的详细评分过程\",\n                            \"grade\": \"解决措施的信息完备性的评级（例如：优秀(18-25分)、一般(10-17分)、较差(4-9分)、无效(0-3分)）\",\n                            \"score\": \"解决措施的信息完备性得分\"\n                        },\n                        \"r3.2\": {\n                            \"explanation\": \"先深度思考，然后输出原因与措施匹配度的详细评分过程\",\n                            \"grade\": \"原因分析与采取措施匹配度的评级（例如：匹配(8-10分)、大致匹配(5-7分)、不匹配(0-4分)）\",\n                            \"score\": \"原因与措施匹配度得分\"\n                        }\n                    },\n                    \"r4\": {\n                        \"explanation\": \"固定得分\",\n                        \"score\": \"调度单回复及时性得分\"\n                    }\n                }\n            }\n        },\n        \"核查确认类\": {\n            \"rule\": f\"\"\"\n            请按照以下规则进行评分：\n            1. 分数范围： 最低分0分，最高分100分\n            2. 以下是四个维度的评分规则：\n                ## 一、调度单填写合规性（满分15分）\n                * 直接给固定分数{compliance_score}分\n                ## 二、原因分析质量（满分35分）\n                ### 原因分析的信息完备性（满分35分）\n                * 0-9分：原因分析与调度单完全无关。\n                * 10-24分：明确给出了“正常”或“异常”的结论，或者明确说明了当前的处理状态（如“核查中”），但未对情况进行说明。示例：“省内核查中” → 属于“说明了状态”。“用户正常使用”、“上传正常”、“经核实，用户余额状态和限速状态正常，请集团知悉” → 属于“给出了结论”。\n                * 25-35分：已明确给出核查的最终结果，并说明情况，例如：“核查正常，套内流量”或“经核查发现波动异常，因上游数据下发异常导致”。\n                ## 三、解决措施质量（满分35分）\n                ### 解决措施的信息完备性（满分35分）\n                注：请先独立判断目前是属于正常场景还是异常场景（不受错误分类影响），然后只看对应的标准。\n                * 0-9分：未在措施中给出任何状态确认或有效结论，与调度单完全无关。\n                * 10-24分：正常场景：只给出了核查结果，但未补充说明情况，或者只给出了倾向性判断、确认/签收的动作。异常场景：解决措施较模糊，或者仅说明当前的处理状态。\n                * 25-35分：正常场景：给出核查结果并说明情况（无需任何处理动作），例如：“核查正常，套内流量”。异常场景：针对异常或问题给出处理动作或处理方法。\n                ## 四、调度单回复及时性（满分15分）\n                * 直接给固定分数{timeliness_score}分\n            3. 每一个子项的得分是一个区间范围，请先确定评分区间范围，然后酌情给分\n            4. 最终分数必须在分数范围内\n            \"\"\",\n            \"output\": {\n                \"evaluate_report\": {\n                    \"r1\": {\n                        \"explanation\": \"固定得分\",\n                        \"score\": \"调度单填写合规性得分\"\n                    },\n                    \"r2\": {\n                        \"r2.1\": {\n                            \"explanation\": \"先深度思考，然后输出原因分析的信息完备性的详细评分过程\",\n                            \"grade\": \"原因分析的信息完备性的评级（例如：优秀(25-35分)、一般(10-24分)、较差(0-9分)）\",\n                            \"score\": \"原因分析的信息完备性得分\"\n                        }\n                    },\n                    \"r3\": {\n                        \"r3.1\": {\n                            \"explanation\": \"先深度思考，然后输出解决措施的信息完备性的详细评分过程\",\n                            \"grade\": \"解决措施的信息完备性的评级（例如：优秀(25-35分)、一般(10-24分)、较差(0-9分)）\",\n                            \"score\": \"解决措施的信息完备性得分\"\n                        }\n                    },\n                    \"r4\": {\n                        \"explanation\": \"固定得分\",\n                        \"score\": \"调度单回复及时性得分\"\n                    }\n                }\n            }\n        },\n        \"流程催办类\": {\n            \"rule\": f\"\"\"\n            请按照以下规则进行评分：\n            1. 分数范围： 最低分0分，最高分100分\n            2. 以下是四个维度的评分规则：\n                ## 一、调度单填写合规性（满分15分）\n                * 直接给固定分数{compliance_score}分\n                ## 二、原因分析质量（满分35分）\n                ### 原因分析的信息完备性（满分35分）\n                * 0-9分： 从原因分析内容仅能推出针对调度单通知的催办内容未开展任何动作，仅仅处于签收状态。例如：“已收到”、“已确认”、“已知晓”、“已知悉”、“遵办”等等。或者原因分析与调度单催办通知内容完全无关。\n                * 10-24分：从原因分析内容仅能推出目前针对调度单通知的催办内容处于进行中或者未完成状态。涵盖情况：“已通知相关人员填报”、“转负责同事处理”、“将按时填写”、“由于某某原因暂未填写/处理”、“正在填写”等等。\n                * 25-35分：从原因分析内容可以推理出目前针对调度单通知的催办内容已办结、已提交、已处理或者处于已完成状态（即可得25分基础分），例如：“已填报”、“已填写”、“已完成/已处理”、“已上报”等等。增加清晰、详细的描述可酌情加分，例如：“省内已填报，烦请集团核实”，“按照集团要求执行，吉林已上报”（可以给25分-35分）。\n                ## 三、解决措施质量（满分35分）\n                ### 解决措施的信息完备性（满分35分）\n                * 0-9分： 从采取措施内容仅能推出针对调度单通知的催办内容未开展任何动作，仅仅处于签收状态。例如：“已收到”、“已确认”、“已知晓”、“已知悉”等等。或者采取措施与调度单催办通知内容完全无关。\n                * 10-24分：从采取措施内容仅能推出目前针对调度单通知的催办内容处于进行中或者未完成状态。涵盖情况：“已通知相关人员填报”、“转负责同事处理”、“将按时填写”、“由于某某原因暂未填写/处理”、“正在填写”等等。\n                * 25-35分：从采取措施内容可以推理出目前针对调度单通知的催办内容已办结、已提交、已处理或者处于已完成状态（即可得25分基础分），例如：“已填报”、“已填写”、“已完成/已处理”、“已上报”等等。增加清晰、详细的描述可酌情加分，例如：“省内已填报，烦请集团核实”，“按照集团要求执行，吉林已上报”（可以给25分-35分）。\n                ## 四、调度单回复及时性（满分15分）\n                    * 直接给固定分数{timeliness_score}分\n            3. 每一个子项的得分是一个区间范围，请先确定评分区间范围，然后酌情给分\n            4. 最终分数必须在分数范围内\n            \"\"\",\n            \"output\": {\n                \"evaluate_report\": {\n                    \"r1\": {\n                        \"explanation\": \"固定得分\",\n                        \"score\": \"调度单填写合规性得分\"\n                    },\n                    \"r2\": {\n                        \"r2.1\": {\n                            \"explanation\": \"先深度思考，然后输出原因分析的信息完备性的详细评分过程\",\n                            \"grade\": \"原因分析的信息完备性的评级（例如：优秀(25-35分)、一般(10-24分)、较差(0-9分)）\",\n                            \"score\": \"原因分析的信息完备性得分\"\n                        }\n                    },\n                    \"r3\": {\n                        \"r3.1\": {\n                            \"explanation\": \"先深度思考，然后输出解决措施的信息完备性的详细评分过程\",\n                            \"grade\": \"解决措施的信息完备性的评级（例如：优秀(25-35分)、一般(10-24分)、较差(0-9分)）\",\n                            \"score\": \"解决措施的信息完备性得分\"\n                        }\n                    },\n                    \"r4\": {\n                        \"explanation\": \"固定得分\",\n                        \"score\": \"调度单回复及时性得分\"\n                    }\n                }\n            }\n        }\n    }\n\n    standard_responses = {\n        \"问题处理类\": {\n            \"r2.1\": {\n                \"无效\": [\n                    \"当前内容仅体现处理动作或沟通反馈，未进一步说明具体问题原因或异常环节，暂无法支撑问题定位与原因判断。\",\n                    \"现有描述未体现具体问题原因、影响对象或相关处理环节，暂不构成有效原因分析。\",\n                    \"当前原因分析信息不足，主要为状态反馈或处理说明，缺少对问题原因及异常链路的有效描述。\",\n                    \"当前内容未进一步说明问题原因、异常场景或影响环节，难以支撑后续问题判断与原因复盘。\"\n                ],\n                \"较差\": [\n                    \"原因分析较为简略，当前尚不足以支撑对问题的准确判断，未能明确说明具体问题原因或异常环节。\",\n                    \"当前描述偏概括，尚未体现具体问题原因或异常定位，缺少对异常表现、处理环节或上下游关系的有效说明。\",\n                    \"现有内容信息支撑不足，缺少与问题原因相关的关键说明，暂无法形成较完整的问题定位依据。\",\n                    \"当前原因分析支撑不足，尚未明确具体问题原因、涉及环节或异常链路，对问题定位帮助有限。\",\n                    \"现有描述较为笼统，未明确异常原因、对应处理环节或上下游影响关系，缺少有效定位信息。\",\n                    \"当前原因分析较为模糊，缺少能够支撑问题判断的关键原因说明或异常定位信息。\",\n                ],\n                \"一般\": [\n                    \"原因分析已有基本方向，但当前更多停留在异常现象描述层面，对具体问题原因、处理环节或异常链路说明还不够充分。\",\n                    \"当前已给出初步原因判断，但对具体问题点、触发原因或上下游关系的描述仍可进一步细化，以便更准确支撑结论。\",\n                    \"分析内容具备一定参考性，但关键问题定位仍不够明确，建议进一步补充异常原因、影响范围或相关处理环节说明。\",\n                    \"当前已说明相关异常现象，但对具体问题原因、涉及环节或异常触发场景的描述仍不够完整。\",\n                    \"分析方向基本明确，但对具体异常对象或原因关联关系的说明仍可进一步细化。\",\n                    \"当前内容已具备一定分析基础，若进一步补充问题原因、异常场景或相关影响环节，将更有助于支撑判断。\"\n                ],\n                \"优秀\": [\n                    \"定位较为明确，原因分析较完整。已说明具体处理环节、业务规则、上下游关系或相关数据字段，能够较好支撑问题判断与原因定位。\",\n                    \"原因说明较为清晰。能够从异常现象进一步定位到具体问题点，并对问题原因、影响对象或异常链路进行有效说明，整体逻辑较完整。\",\n                    \"分析较有针对性。已结合具体异常对象、错误描述、上下游关系或相关特征进行说明，对问题判断具有较好的参考价值。\",\n                    \"原因分析较为完整，已对问题定位、异常原因及相关依据作出说明，能够较好支撑原因判断与问题复盘。\"\n                ]\n            },\n            \"r2.2\": {\n                \"不匹配\": [\n                    \"错误分类与原因分析之间存在明显偏差，建议结合实际原因重新核对分类选择。\",\n                    \"当前分类与原因说明不够一致，建议根据主要原因调整为更贴合的分类。\",\n                    \"文字内容与所选分类对应关系较弱，建议统一分类与原因分析的表达口径。\",\n                    \"当前错误分类与原因分析描述存在偏差，建议重新核对分类是否准确。\",\n                    \"分析内容指向的问题类型与所选分类不完全吻合，请结合实际情况调整。\",\n                ],\n                \"大致匹配\": [\n                    \"分类选择与分析内容大体相符，建议再核对表述重点是否与所选分类完全对应。\",\n                    \"当前分类与分析方向基本一致，若分类名称与原因表述进一步统一会更好。\",\n                ],\n                \"匹配\": [\"错误分类与原因分析内容一致，分类选择较准确，整体逻辑清晰。\",\n                         \"分类与文字说明对应较好，能够反映实际分析方向。\",\n                         \"所选分类与原因分析相互印证，匹配度较高。\",\n                         \"错误分类与原因分析内容高度一致，逻辑清晰。\", ]\n            },\n            \"r3.1\": {\n                \"较差\": [\n                    \"当前措施内容较少，尚未体现明确的处理动作或落实方式，建议补充具体安排。\",\n                    \"现有措施表述偏笼统，暂时难以判断实际执行方式，建议进一步说明下一步处理动作。\",\n                    \"当前措施信息支撑不足，尚未体现明确的处理动作或落实方式，建议补充具体安排。\",\n                    \"当前措施尚未体现明确的处理动作或落实方式，建议补充具体安排。\",\n                    \"现有措施表述较为笼统，建议进一步细化为可执行的处理动作。\",\n                    \"措施描述缺少实质性处理内容，建议补充具体处理动作或相关安排。\"\n                ],\n                \"一般\": [\n                    \"已提出处理思路，但措施完整度仍可提升。当前对具体执行动作或落实细节说明还不够充分。\",\n                    \"措施方向基本明确，建议进一步补充处理步骤或实施要点。\",\n                    \"当前措施具备初步可行性，若能再细化到具体操作层面，会更便于后续跟踪。\",\n                    \"已提出初步处理计划，建议进一步明确具体动作和落实要点。\",\n                    \"措施方向基本正确，若补充一些实施细节会更清晰。\",\n                    \"当前措施较为基础，建议细化到可执行的行动步骤。\"\n                ],\n                \"优秀\": [\n                    \"解决措施较明确，包含了具体处理动作或推进方式，整体具备较好的可执行性。\",\n                    \"措施内容较为完整，能够对应问题处理需要，并体现一定的处理思路或落实方向。\",\n                    \"当前措施已体现较为明确的处理动作和落实方向，能够较好支撑后续执行。\",\n                    \"解决措施较为具体，已说明处理动作或推进方式，整体执行方向较清晰。\",\n                ]\n            },\n            \"r3.2\": {\n                \"不匹配\": [\n                    \"原因分析与解决措施之间的对应关系不够清晰，建议根据问题原因补充更有针对性的处理动作。\",\n                    \"当前措施未能充分回应原因分析中的关键问题，建议进一步梳理两者之间的对应关系。\",\n                    \"前后内容存在一定脱节，建议使措施更直接对应分析中提到的问题点。\",\n                    \"解决措施未能直接回应原因分析中提出的问题，建议重新梳理两者之间的逻辑关系。\",\n                    \"措施内容与原因分析脱节，建议根据实际情况补充更有针对性的措施。\"\n                ],\n                \"大致匹配\": [\n                    \"措施与原因分析有一定关联，建议进一步确保关键问题点均有对应处理动作。\",\n                    \"整体方向基本一致，若能将分析中的重点与措施逐一对应会更完整。\",\n                ],\n                \"匹配\": [\"原因分析与解决措施对应较好，前后逻辑较一致，能够形成较完整的处理闭环。\",\n                         \"措施能够回应原因分析中指出的问题，整体匹配度较高。\",\n                         \"前后内容衔接较顺畅，原因判断与处理动作之间具有较好的对应关系。\",\n                         \"解决措施与原因分析高度对应，形成了较完整的闭环。\", ]\n            }\n        },\n        \"核查确认类\": {\n            \"r2.1\": {\n                \"较差\": [\n                    \"当前回复信息较少，尚未充分体现核查结论或情况说明，建议补充具体结果。\",\n                    \"现有反馈未能清楚说明指标波动对应的核查判断，建议进一步明确结论及相关情况。\",\n                    \"核查说明仍不够完整，建议补充与预警现象相关的结果说明或判断依据。\",\n                    \"建议明确给出核查最终结论，并简要说明具体情况。\",\n                    \"当前描述更多停留在状态层面，建议补充核查结果依据。\",\n                    \"分析内容可进一步具体化，建议在结论后增加情况说明。\"\n                ],\n                \"一般\": [\n                    \"已给出结论或状态说明，但情况说明仍可适当补充，以增强判断依据。\",\n                    \"当前回复体现了初步核查结果，但对具体情况的说明还不够充分。\",\n                    \"结论方向基本明确，建议补充简要情况或依据，使回复更完整。\",\n                    \"当前已给出结论，建议补充简短情况说明以增强支撑性。\",\n                    \"结论较清晰，若能简述关键点会更完整。\",\n                    \"当前状态描述较准确，建议增加简要解释或佐证。\"\n                ],\n                \"优秀\": [\n                    \"核查结论明确，情况说明较完整，能够较好支撑当前判断。\",\n                    \"回复已给出清晰的业务定性，并对相关情况进行了基本说明，整体表达较清楚。\",\n                    \"当前反馈能够对应预警现象，核查结论较明确，并具备基本情况说明。\",\n                    \"核查结论明确且情况说明清晰，逻辑较顺畅。\",\n                ]\n            },\n            \"r2.2\": {\n                \"不匹配\": [\n                    \"错误分类与原因分析之间存在一定冲突，建议根据实际核查结果重新核对分类。\",\n                    \"当前文字说明与所选分类对应性较弱，建议调整为更贴近实际情况的分类。\",\n                    \"分类与原因分析的匹配关系不够清晰，建议统一分类口径与文字表述。\",\n                    \"当前分类与核查结论存在矛盾，请根据实际结果重新选择更准确的分类。\",\n                    \"分类选项未能反映核查的实际情况，建议仔细核对后调整。\",\n                ],\n                \"大致匹配\": [\n                    \"分类与原因分析大体相符，建议在措辞上进一步统一，以提升匹配度。\",\n                    \"当前分类与结论方向基本一致，但在表述颗粒度上仍可更精确。\",\n                    \"归类方向基本正确，若分类名称与原因表述进一步对齐会更好。\",\n                    \"分类与结论基本吻合，建议在措辞上统一以确保完全对应。\",\n                    \"整体方向正确，若能将关键词与分类定义更精准对齐会更好。\",\n                ],\n                \"匹配\": [\n                    \"错误分类与原因分析内容一致，整体定性较为准确。\",\n                    \"分类选择能够较好对应文字说明，逻辑关系清晰。\",\n                    \"所选分类与核查结论方向一致，匹配情况较好。\",\n                    \"错误分类与核查结论一致，逻辑自洽。\",\n                ]\n            },\n            \"r3.1\": {\n                \"较差\": [\n                    \"当前措施未体现有效的状态确认或处理信息，难以判断问题是否已完成核查或后续处置，整体闭环支撑不足。\",\n                    \"当前措施说明不足，未明确体现确认结果、处理动作或结单信息，难以支撑对处置状态的判断。\",\n                    \"现有措施未能有效说明当前处理状态或后续处置情况，信息支撑较弱，流程闭环不足。\",\n                    \"当前措施缺少有效的确认或处理内容，无法判断事项是否已完成核查、处理或反馈。\",\n                    \"措施内容较为空泛，未能体现明确的确认状态、处理动作或结果反馈，难以形成有效闭环。\",\n                ],\n                \"一般\": [\n                    \"当前已体现确认或处理动作，建议结合核查结果补充相关说明，以增强内容完整性。\",\n                    \"当前措施已有基本说明，若能结合核查结果进一步补充相关信息，会更为完整。\",\n                    \"当前内容已体现一定的确认或处理情况，建议补充必要说明，进一步提升信息完整性。\",\n                ],\n                \"优秀\": [\n                    \"当前措施已围绕核查结果或状态反馈作出说明，能够满足本场景的基本要求。\",\n                    \"当前内容已体现核查确认结果及处理状态，能够支撑对处置情况的基本判断。\",\n                    \"当前措施表达与核查确认类场景要求基本一致，已具备必要的信息支撑。\",\n                    \"当前措施已明确体现核查确认结果或状态反馈，能够满足本场景的基本闭环要求。\",\n                ]\n            },\n            \"r3.2\": {\n                \"不匹配\": [\n                    \"原因分析与采取措施之间的衔接不够充分，建议根据核查结论调整后续动作表述。\",\n                    \"当前措施对结论的支撑性偏弱，建议进一步统一原因分析与措施内容。\",\n                    \"前后内容存在一定不一致，建议结合实际核查情况完善闭环表达。\",\n                    \"采取措施与原因分析存在脱节，建议重新梳理。\",\n                    \"措施内容对原因分析结论的支撑不足，建议根据实际情况调整。\",\n                ],\n                \"大致匹配\": [\n                    \"整体闭环关系基本成立，建议进一步增强措施对结论的支撑说明。\",\n                    \"原因分析与措施之间存在一定关联，若能更明确呼应关键点会更完整。\",\n                    \"措施与原因分析有一定关联，建议进一步强化两者之间的对应关系。\",\n                    \"整体逻辑成立，若能在措施中更明确回应分析中的关键点会更好。\",\n                ],\n                \"匹配\": [\n                    \"采取措施与原因分析能够相互印证，整体逻辑较顺畅。\",\n                    \"结论与后续反馈基本吻合，能够支撑当前核查判断。\",\n                    \"措施内容对原因分析起到了较好的补充说明作用，前后逻辑较一致。\",\n                    \"采取的措施与原因分析能够相互印证，形成闭环。\",\n                ]\n            }\n        },\n        \"流程催办类\": {\n            \"r2.1\": {\n                \"较差\": [\n                    \"当前未提供有效分析内容，难以判断事项处理状态，建议补充相关说明。\",\n                    \"现有内容对任务进度说明不足，建议补充已开展的动作或处理状态。\",\n                    \"建议在回复中体现实质进展，而不仅是收到通知后的确认状态。\",\n                    \"分析内容需体现实质进展，建议补充当前处理状态而非仅确认收到。\",\n                ],\n                \"一般\": [\n                    \"已体现当前处理状态，但对进展的描述仍可进一步细化。\",\n                    \"分析内容反映了处理状态，建议补充目前的执行情况或阶段性结果。\",\n                    \"当前描述表明处于进行中，若能提供更具体的进度信息会更完整。\",\n                    \"已说明正在处理，建议补充当前具体进度或阶段性结果。\",\n                ],\n                \"优秀\": [\n                    \"当前已较清楚说明办理状态，能够支撑对任务进展的基本判断。\",\n                    \"当前已对办理情况作出说明，能够反映任务处理的基本状态。\",\n                    \"已结合当前进度进行了说明，能够反映任务处理的实际状态。\",\n                    \"对于当前处理情况已有说明，能够支撑对任务进展的基本判断。\",\n                ]\n            },\n            \"r2.2\": {\n                \"不匹配\": [\"本类调度单为催办通知，不涉及错误分类评估，该项按固定分值处理。\"],\n                \"大致匹配\": [\"本类调度单为催办通知，不涉及错误分类评估，该项按固定分值处理。\"],\n                \"匹配\": [\"本类调度单为催办通知，不涉及错误分类评估，该项按固定分值处理。\"]\n            },\n            \"r3.1\": {\n                \"较差\": [\n                    \"当前措施对具体办理动作说明不足，建议补充是否已提交、办结或正在推进。\",\n                    \"当前措施未明确体现具体办结动作或处理进度，难以判断事项办理状态。\",\n                    \"现有措施更多停留在确认层面，尚未体现实质办理动作，建议补充当前处理进展。\",\n                ],\n                \"一般\": [\n                    \"已说明处理方向，但对完成节点或具体进展的描述仍可进一步补充。\",\n                    \"建议对正在处理的事项补充当前进展或阶段性结果。\",\n                    \"措施方向基本正确，若能提供更具体的办理进度会更清晰。\",\n                    \"当前措施体现了处理状态，建议进一步补充执行进展。\",\n                ],\n                \"优秀\": [\n                    \"当前措施能够体现实质性办理动作或办结状态，能够反映事项处置情况。\",\n                    \"当前措施已对办理情况作出说明，能够体现处理进展或当前状态。\",\n                    \"措施内容能够体现当前办理结果或推进状态，整体表达较为明确。\",\n                ]\n            },\n            \"r3.2\": {\n                \"不匹配\": [\n                    \"原因分析与采取措施之间存在一定脱节，建议根据实际处理进度统一表述。\",\n                    \"当前措施未能充分对应原因分析中的状态说明，建议调整为更一致的表达。\",\n                    \"措施内容对原因分析的支撑不足，建议重新梳理并确保两者一致。\",\n                ],\n                \"大致匹配\": [\n                    \"原因分析与措施基本对应，建议进一步增强两者在进度描述上的一致性。\",\n                    \"措施与原因分析基本对应，若能更明确呼应关键进度点会更完整。\",\n                    \"整体逻辑较顺畅，建议在措施中更明确回应原因分析中的状态描述。\",\n                ],\n                \"匹配\": [\n                    \"原因分析与采取措施逻辑一致，能够体现从接收到办理推进的对应关系。\",\n                    \"措施与原因分析前后衔接较顺畅，整体对应较好。\",\n                ]\n            }\n        }\n    }\n    output_format = score_rule_map.get(error_type_to_issue_category.get(error_class_name, \"问题处理类\"),\n                                       score_rule_map.get(\"问题处理类\", {})).get(\"output\")\n    score_prompt = f\"\"\" # 角色\n                        你是一个专业的电信客服回复质量评估助手，结合领域的知识，通过以下给定的调度单信息，对客服的回复内容进行评估打分，并帮助他们改进回复的质量。\n                        # 输入\n                        <错误原因分类两级标准>\n                            系统异常：网络问题、基础设施问题、应用软件问题、软件升级(计划外升级)\n                            配置异常：业务参数配置问题、业务规则问题、系统配置问题\n                            数据源本身问题：业务平台数据源问题、集团下发数据源问题、其他外围系统数据源问题\n                            业务异常：用户行为引起的业务波动、其他业务异常\n                        </错误原因分类两级标准>\n                        <调度单信息>\n                        {background}\n                        </调度单信息>\n                        <客服的回复内容>\n                        {query}\n                        </客服的回复内容>\n                        # 任务\n                        {score_rule_map.get(error_type_to_issue_category.get(error_class_name, \"问题处理类\"), score_rule_map.get(\"问题处理类\", {})).get(\"rule\")}\n                        # 输出\n                        请直接按照以下评分报告的json模板输出，每个维度的每个子项都是一个对象，不要包含其他任何字符：\n                        ```json\n                        {json.dumps(output_format, ensure_ascii=False)}\n                        ```\n                    \"\"\"\n\n    def replace_specific_values(target_dict, replacement_map, prefix=None):\n        for key in target_dict:\n            if isinstance(target_dict[key], dict):\n                replace_specific_values(target_dict[key], replacement_map, key)\n            else:\n                if key in replacement_map:\n                    target_dict[key] = replacement_map[key]\n        if prefix in ['r2.1', 'r2.2', 'r3.1', 'r3.2']:\n            for key in replacement_map:\n                if key not in target_dict:\n                    target_dict[key] = replacement_map[key]\n        return target_dict\n\n    model = LocalLLMComponent(inputs=[\n        TextInput(name='query', display_name='Text', value=''),\n        TextInput(name='assistant_code', display_name=\"助手编码\", value='BSS-BASE-QM-32'),\n        FloatInput(name='temperature', display_name='Temperature', value=0.1),\n        TextInput(name='prompt', display_name='Prompt', value=score_prompt),\n        TextInput(name='model_name', display_name='Model name', value=LLM_MODELS[0]),\n    ])\n    model.set_context({})\n    total_tokens = None\n    try:\n        result = await model.run(state={\"query\": query})\n        total_tokens = result.get(\"total_tokens\", None)\n    except BaseException as e:\n        print(f\"大模型调用失败: {e}\")\n        error_obj = {\"explanation\": \"大模型调用失败\", \"score\": -1, \"grade\": \"无法评估\",\n                     \"suggestion\": \"大模型调用失败\"}\n        return {\"answer\": json.dumps({\"score\": -1, **replace_specific_values(output_format, error_obj)}),\n                \"total_tokens\": total_tokens}\n\n    final_response = {}\n    try:\n        answer = result.get(\"answer\", \"\")\n        if \"```\" in answer:\n            match = re.search(r'```(json)?(.*?)```', answer, re.DOTALL)\n            if match:\n                answer = match.group(2)\n        answer_obj = json.loads(answer)\n        evaluate_report = answer_obj.get('evaluate_report', {})\n        r1 = evaluate_report.get('r1', {})\n        r21 = evaluate_report.get('r2', {}).get('r2.1', {})\n        r22 = evaluate_report.get('r2', {}).get('r2.2', {})\n        r31 = evaluate_report.get('r3', {}).get('r3.1', {})\n        r32 = evaluate_report.get('r3', {}).get('r3.2', {})\n        r4 = evaluate_report.get('r4', {})\n        r1_score = int(r1.get('score', 0))\n        r21_score = int(r21.get('score', 0))\n        r22_score = int(r22.get('score', 0))\n        r31_score = int(r31.get('score', 0))\n        r32_score = int(r32.get('score', 0))\n        r4_score = int(r4.get('score', 0))\n        total_score = r1_score + r21_score + r22_score + r31_score + r32_score + r4_score\n\n        final_response[\"score\"] = total_score\n        final_response[\"evaluate_report\"] = evaluate_report\n\n        standard_response_dict = standard_responses.get(\n            error_type_to_issue_category.get(error_class_name, \"问题处理类\"), standard_responses[\"问题处理类\"])\n\n        def get_suggestion_by_grade(dimension: str, grade: str) -> [str, None]:\n            dimension_standard_response_dict = standard_response_dict.get(dimension, {})\n            for k in sorted(dimension_standard_response_dict.keys(), key=len, reverse=True):\n                if k in grade:\n                    return random.choice(dimension_standard_response_dict.get(k))\n            return random.choice(dimension_standard_response_dict.get('较差')) if '无效' in grade else None\n\n        for dimension, score_obj in [(\"r2.1\", r21), (\"r2.2\", r22), (\"r3.1\", r31), (\"r3.2\", r32)]:\n            if len(score_obj) == 0:\n                continue\n            suggestion = get_suggestion_by_grade(dimension, score_obj.get('grade', ''))\n            if suggestion:\n                score_obj['suggestion'] = suggestion\n        return {\"answer\": json.dumps(final_response, ensure_ascii=False), \"total_tokens\": total_tokens}\n    except BaseException as e:\n        print(f\"解析错误评估结果失败: {e}，原始数据：{result.get('answer')}\")\n        error_obj = {\"explanation\": \"大模型返回格式错误导致解析评分结果失败\", \"score\": -1, \"grade\": \"无法评估\",\n                     \"suggestion\": \"大模型返回格式错误导致解析评分结果失败\"}\n        return {\"answer\": json.dumps({\"score\": -1, **replace_specific_values(output_format, error_obj)}),\n                \"total_tokens\": total_tokens}\n", "type": "TextInput"}], "outputs": [{"id": "result-3GmcZj", "name": "result", "display_name": "结果", "info": None, "enable_expr": False, "field_type": "dict", "value": {}, "type": "DictOutput"}, {"id": "total_tokens-46izmH", "name": "total_tokens", "display_name": "总token数量", "info": None, "enable_expr": False, "field_type": "str", "value": None, "type": "TextOutput"}], "type": "PythonREPLComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "chat_output-43CTSP", "name": "chat_output", "display_name": "聊天输出", "description": "获取聊天输出", "tag": "输出", "icon": None, "inputs": [], "outputs": [{"id": "answer-4GgPTZ", "name": "answer", "display_name": "Answer", "info": None, "enable_expr": True, "field_type": "str", "value": "{{ python_repl-3rPiNu.outputs.result.answer }}", "type": "TextOutput"}], "type": "ChatOutputComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}], "edges": [{"source": "chat_input-PBYTfP", "target": "python_repl-3rPiNu"}, {"source": "python_repl-3rPiNu", "target": "chat_output-43CTSP"}]}

    chat_response = await do_workflow_chat(
        query="""
省份联系人：毛建邦
省份联系电话：15368221036
涉及系统：出账
发生部门：企业数字化运营中心
影响范围：小
影响开始时间：2025-08-01 00:00:00.0
是否省份异常：否
错误原因分类："集团下发数据源问题"
原因分析：集团下发的volte话单里面没有漫游地区号导致。
采取措施：反馈集团核查解决。
完成状态：已完成
完成时间：2025-08-01 00:00:00
        """, assistant_id=-1,
        extra={
            "compliance_score": 15,
            "timeliness_score": 15,
            "error_class_name": "省上传错单",
            "background": """
            调度类型：详单查询调度。
            错单类型：省上传错单。
            错单代码：F190
            字段名称：用户归属地区号
            错误描述：湖北移网语音详单上周错误条数为10。
            """,
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
    error_class_name_var = chat_input.id + ".inputs.extra.error_class_name"

    async def main(error_class_name: str, query: str, background: str, compliance_score: str,
                   timeliness_score: str):
        import json
        import re
        import random

        from configs import LLM_MODELS
        from server.workflow.component.models.local_llm import LocalLLMComponent
        from server.workflow.utils.inputs import TextInput, FloatInput
        ISSUE_CATEGORIES = {
            "流程催办类": [
                "调研",
                "出账信息填报"
            ],
            "核查确认类": [
                "环比波动异常",
                "国内数据高额高频下发",
                "出账环比波动",
                "基站数据求取不到"
            ],
            "问题处理类": [
                "省份文件缺失",
                "省上传文件数不平衡",
                "省上传文件数不完整",
                "话单上传及时率低于阈值异常",
                "其他",
                "通信链路异常",
                "省上传错单",
                "省上传拒收",
                "省份消息接收失败",
                "集团下发错单",
                "集团下发拒收",
                "省文件序列号缺漏",
                "省上传跳号",
                "基础信息缺漏",
                "出账上传质量",
                "政企稽核情况调度",
                "自动拨测",
                "省上传空文件",
                "省上传延迟话单",
                "省未及时上传文件"
            ]
        }
        error_type_to_issue_category = {
            error: category
            for category, errors in ISSUE_CATEGORIES.items()
            for error in errors
        }
        error_class_name = error_class_name.strip()
        score_rule_map = {
            "问题处理类": {
                "rule": f"""
                请按照以下规则进行评分：
                1. 分数范围： 最低分0分，最高分100分
                2. 以下是四个维度的评分规则：
                    # 前提条件：
                    1. 调度单信息和回复内容作为一个整体进行评分，不是单独针对某个字段，其他字段已给出的信息均可以作为补充内容进行评分。
                    2. 如果为上下游外部原因导致，非己方问题，可以无需采取措施，仅须通知并协调责任方处理。
                    3. 每个维度之间需要关联打分，需考虑维度之间的关联性。
                    ** 请牢记此前提，所有规则都在要在此前提下进行！！！**
                    ## 一、调度单填写合规性（满分15分）
                    * 直接给固定分数{compliance_score}分
                    ## 二、原因分析质量（满分35分）
                    注：原因分析为空或纯数字字母时此维度只能得0分，例如：“无”“/”“123”“abc”。
                    ### 原因分析的信息完备性（满分25分）
                    * 0-3分：完全没有针对问题的原因分析，或回复内容属于无效的客套话、流程性回复，不包含任何实质性信息。例如：“已通知相关人员处理”“已安排补传”“请集团知晓”“分析中”“持续关注”等。
                    * 4-9分：问题描述过于笼统、模糊，缺乏具体的场景或细节，导致难以判断具体发生了什么问题。
                    * 10-17分：能够准确描述问题的表面现象或报错信息，但未进一步指出问题源头，或缺乏定位问题所需的关键细节（如具体字段、组件等）。
                    * 18-25分：能够深入定位问题根源，不仅明确问题现象，还能精准提供系统处理环节、系统组件、业务规则、上下游原因（集团、下级、外部系统）或具体数据字段等关键定位信息中的至少一项，例如：“VoLTE 话单中 access - domain 字段未填写区号”“错单原因是计费号码到访地区号是字母，如 1027027”。
                    ### 错误分类与原因分析匹配度（满分10分）
                    * 0-4分：完全不符合或相互矛盾，例如：分类选“网络问题”，但分析内容是“业务平台参数配置错误”。
                    * 5-7分：大致匹配，但略有偏差。
                    * 8-10分：选择的`错误原因分类`与填写`原因分析`描述的内容高度匹配。
                    ## 三、解决措施质量（满分35分）
                    注：采取措施为空或纯数字字母时此维度只能得0分，例如：“无”“/”“123”“abc”。
                    ### 解决措施的信息完备性（满分25分）
                    * 0-3分：未提出任何实质性措施，或措施完全不可行、属于推诿性回复；无任何实施细节，属于无效沟通。
                    * 4-9分：仅提出了极其宽泛的方向或原则性建议，未落实到具体动作，难以直接指导执行；基本无实施细节，或细节与实际解决问题关联度极低。
                    * 10-17分：虽然提及了处理方向，但措施表述较为模糊，无法准确判断具体的优化操作；或仅有非常初步的想法、计划及待办状态，缺乏实质性内容。
                    * 18-25分：在解决措施明确性方面，包含具体措施，明确牵头方，并协调相关上下游解决处理，措施明确可执行。同时，在解决措施的信息完备性上，措施包含具体的操作步骤、方法。
                    ### 原因分析与采取措施匹配度（满分10分）
                    * 0-4分：措施与原因分析完全无关，或者未提出任何具体措施。
                    * 5-7分：大致匹配，措施与原因部分相关。
                    * 8-10分：所述“采取措施”与“原因分析”指出的问题一一对应，形成闭环，分析出的原因在措施中得到直接解决。
                    ## 四、调度单回复及时性（满分15分）
                        * 直接给固定分数{timeliness_score}分
                3. 每一个子项的得分是一个区间范围，请先确定评分区间范围，然后酌情给分
                4. 最终分数必须在分数范围内
                """,
                "output": {
                    "evaluate_report": {
                        "r1": {
                            "explanation": "固定得分",
                            "score": "调度单填写合规性得分"
                        },
                        "r2": {
                            "r2.1": {
                                "explanation": "先深度思考，然后输出原因分析的信息完备性的详细评分过程",
                                "grade": "原因分析的信息完备性的评级（例如：优秀(18-25分)、一般(10-17分)、较差(4-9分)、无效(0-3分)）",
                                "score": "原因分析的信息完备性得分"
                            },
                            "r2.2": {
                                "explanation": "先深度思考，然后输出错误分类与原因分析匹配度的详细评分过程",
                                "grade": "错误分类与原因分析匹配度的评级（例如：匹配(8-10分)、大致匹配(5-7分)、不匹配(0-4分)）",
                                "score": "错误分类与原因匹配度得分"
                            }
                        },
                        "r3": {
                            "r3.1": {
                                "explanation": "先深度思考，然后输出解决措施的信息完备性的详细评分过程",
                                "grade": "解决措施的信息完备性的评级（例如：优秀(18-25分)、一般(10-17分)、较差(4-9分)、无效(0-3分)）",
                                "score": "解决措施的信息完备性得分"
                            },
                            "r3.2": {
                                "explanation": "先深度思考，然后输出原因与措施匹配度的详细评分过程",
                                "grade": "原因分析与采取措施匹配度的评级（例如：匹配(8-10分)、大致匹配(5-7分)、不匹配(0-4分)）",
                                "score": "原因与措施匹配度得分"
                            }
                        },
                        "r4": {
                            "explanation": "固定得分",
                            "score": "调度单回复及时性得分"
                        }
                    }
                }
            },
            "核查确认类": {
                "rule": f"""
                请按照以下规则进行评分：
                1. 分数范围： 最低分0分，最高分100分
                2. 以下是四个维度的评分规则：
                    ## 一、调度单填写合规性（满分15分）
                    * 直接给固定分数{compliance_score}分
                    ## 二、原因分析质量（满分35分）
                    ### 原因分析的信息完备性（满分35分）
                    * 0-9分：原因分析与调度单完全无关。
                    * 10-24分：明确给出了“正常”或“异常”的结论，或者明确说明了当前的处理状态（如“核查中”），但未对情况进行说明。示例：“省内核查中” → 属于“说明了状态”。“用户正常使用”、“上传正常”、“经核实，用户余额状态和限速状态正常，请集团知悉” → 属于“给出了结论”。
                    * 25-35分：已明确给出核查的最终结果，并说明情况，例如：“核查正常，套内流量”或“经核查发现波动异常，因上游数据下发异常导致”。
                    ## 三、解决措施质量（满分35分）
                    ### 解决措施的信息完备性（满分35分）
                    注：请先独立判断目前是属于正常场景还是异常场景（不受错误分类影响），然后只看对应的标准。
                    * 0-9分：未在措施中给出任何状态确认或有效结论，与调度单完全无关。
                    * 10-24分：正常场景：只给出了核查结果，但未补充说明情况，或者只给出了倾向性判断、确认/签收的动作。异常场景：解决措施较模糊，或者仅说明当前的处理状态。
                    * 25-35分：正常场景：给出核查结果并说明情况（无需任何处理动作），例如：“核查正常，套内流量”。异常场景：针对异常或问题给出处理动作或处理方法。
                    ## 四、调度单回复及时性（满分15分）
                    * 直接给固定分数{timeliness_score}分
                3. 每一个子项的得分是一个区间范围，请先确定评分区间范围，然后酌情给分
                4. 最终分数必须在分数范围内
                """,
                "output": {
                    "evaluate_report": {
                        "r1": {
                            "explanation": "固定得分",
                            "score": "调度单填写合规性得分"
                        },
                        "r2": {
                            "r2.1": {
                                "explanation": "先深度思考，然后输出原因分析的信息完备性的详细评分过程",
                                "grade": "原因分析的信息完备性的评级（例如：优秀(25-35分)、一般(10-24分)、较差(0-9分)）",
                                "score": "原因分析的信息完备性得分"
                            }
                        },
                        "r3": {
                            "r3.1": {
                                "explanation": "先深度思考，然后输出解决措施的信息完备性的详细评分过程",
                                "grade": "解决措施的信息完备性的评级（例如：优秀(25-35分)、一般(10-24分)、较差(0-9分)）",
                                "score": "解决措施的信息完备性得分"
                            }
                        },
                        "r4": {
                            "explanation": "固定得分",
                            "score": "调度单回复及时性得分"
                        }
                    }
                }
            },
            "流程催办类": {
                "rule": f"""
                请按照以下规则进行评分：
                1. 分数范围： 最低分0分，最高分100分
                2. 以下是四个维度的评分规则：
                    ## 一、调度单填写合规性（满分15分）
                    * 直接给固定分数{compliance_score}分
                    ## 二、原因分析质量（满分35分）
                    ### 原因分析的信息完备性（满分35分）
                    * 0-9分： 从原因分析内容仅能推出针对调度单通知的催办内容未开展任何动作，仅仅处于签收状态。例如：“已收到”、“已确认”、“已知晓”、“已知悉”、“遵办”等等。或者原因分析与调度单催办通知内容完全无关。
                    * 10-24分：从原因分析内容仅能推出目前针对调度单通知的催办内容处于进行中或者未完成状态。涵盖情况：“已通知相关人员填报”、“转负责同事处理”、“将按时填写”、“由于某某原因暂未填写/处理”、“正在填写”等等。
                    * 25-35分：从原因分析内容可以推理出目前针对调度单通知的催办内容已办结、已提交、已处理或者处于已完成状态（即可得25分基础分），例如：“已填报”、“已填写”、“已完成/已处理”、“已上报”等等。增加清晰、详细的描述可酌情加分，例如：“省内已填报，烦请集团核实”，“按照集团要求执行，吉林已上报”（可以给25分-35分）。
                    ## 三、解决措施质量（满分35分）
                    ### 解决措施的信息完备性（满分35分）
                    * 0-9分： 从采取措施内容仅能推出针对调度单通知的催办内容未开展任何动作，仅仅处于签收状态。例如：“已收到”、“已确认”、“已知晓”、“已知悉”等等。或者采取措施与调度单催办通知内容完全无关。
                    * 10-24分：从采取措施内容仅能推出目前针对调度单通知的催办内容处于进行中或者未完成状态。涵盖情况：“已通知相关人员填报”、“转负责同事处理”、“将按时填写”、“由于某某原因暂未填写/处理”、“正在填写”等等。
                    * 25-35分：从采取措施内容可以推理出目前针对调度单通知的催办内容已办结、已提交、已处理或者处于已完成状态（即可得25分基础分），例如：“已填报”、“已填写”、“已完成/已处理”、“已上报”等等。增加清晰、详细的描述可酌情加分，例如：“省内已填报，烦请集团核实”，“按照集团要求执行，吉林已上报”（可以给25分-35分）。
                    ## 四、调度单回复及时性（满分15分）
                        * 直接给固定分数{timeliness_score}分
                3. 每一个子项的得分是一个区间范围，请先确定评分区间范围，然后酌情给分
                4. 最终分数必须在分数范围内
                """,
                "output": {
                    "evaluate_report": {
                        "r1": {
                            "explanation": "固定得分",
                            "score": "调度单填写合规性得分"
                        },
                        "r2": {
                            "r2.1": {
                                "explanation": "先深度思考，然后输出原因分析的信息完备性的详细评分过程",
                                "grade": "原因分析的信息完备性的评级（例如：优秀(25-35分)、一般(10-24分)、较差(0-9分)）",
                                "score": "原因分析的信息完备性得分"
                            }
                        },
                        "r3": {
                            "r3.1": {
                                "explanation": "先深度思考，然后输出解决措施的信息完备性的详细评分过程",
                                "grade": "解决措施的信息完备性的评级（例如：优秀(25-35分)、一般(10-24分)、较差(0-9分)）",
                                "score": "解决措施的信息完备性得分"
                            }
                        },
                        "r4": {
                            "explanation": "固定得分",
                            "score": "调度单回复及时性得分"
                        }
                    }
                }
            }
        }

        standard_responses = {
            "问题处理类": {
                "r2.1": {
                    "无效": [
                        "当前内容仅体现处理动作或沟通反馈，未进一步说明具体问题原因或异常环节，暂无法支撑问题定位与原因判断。",
                        "现有描述未体现具体问题原因、影响对象或相关处理环节，暂不构成有效原因分析。",
                        "当前原因分析信息不足，主要为状态反馈或处理说明，缺少对问题原因及异常链路的有效描述。",
                        "当前内容未进一步说明问题原因、异常场景或影响环节，难以支撑后续问题判断与原因复盘。"
                    ],
                    "较差": [
                        "原因分析较为简略，当前尚不足以支撑对问题的准确判断，未能明确说明具体问题原因或异常环节。",
                        "当前描述偏概括，尚未体现具体问题原因或异常定位，缺少对异常表现、处理环节或上下游关系的有效说明。",
                        "现有内容信息支撑不足，缺少与问题原因相关的关键说明，暂无法形成较完整的问题定位依据。",
                        "当前原因分析支撑不足，尚未明确具体问题原因、涉及环节或异常链路，对问题定位帮助有限。",
                        "现有描述较为笼统，未明确异常原因、对应处理环节或上下游影响关系，缺少有效定位信息。",
                        "当前原因分析较为模糊，缺少能够支撑问题判断的关键原因说明或异常定位信息。",
                    ],
                    "一般": [
                        "原因分析已有基本方向，但当前更多停留在异常现象描述层面，对具体问题原因、处理环节或异常链路说明还不够充分。",
                        "当前已给出初步原因判断，但对具体问题点、触发原因或上下游关系的描述仍可进一步细化，以便更准确支撑结论。",
                        "分析内容具备一定参考性，但关键问题定位仍不够明确，建议进一步补充异常原因、影响范围或相关处理环节说明。",
                        "当前已说明相关异常现象，但对具体问题原因、涉及环节或异常触发场景的描述仍不够完整。",
                        "分析方向基本明确，但对具体异常对象或原因关联关系的说明仍可进一步细化。",
                        "当前内容已具备一定分析基础，若进一步补充问题原因、异常场景或相关影响环节，将更有助于支撑判断。"
                    ],
                    "优秀": [
                        "定位较为明确，原因分析较完整。已说明具体处理环节、业务规则、上下游关系或相关数据字段，能够较好支撑问题判断与原因定位。",
                        "原因说明较为清晰。能够从异常现象进一步定位到具体问题点，并对问题原因、影响对象或异常链路进行有效说明，整体逻辑较完整。",
                        "分析较有针对性。已结合具体异常对象、错误描述、上下游关系或相关特征进行说明，对问题判断具有较好的参考价值。",
                        "原因分析较为完整，已对问题定位、异常原因及相关依据作出说明，能够较好支撑原因判断与问题复盘。"
                    ]
                },
                "r2.2": {
                    "不匹配": [
                        "错误分类与原因分析之间存在明显偏差，建议结合实际原因重新核对分类选择。",
                        "当前分类与原因说明不够一致，建议根据主要原因调整为更贴合的分类。",
                        "文字内容与所选分类对应关系较弱，建议统一分类与原因分析的表达口径。",
                        "当前错误分类与原因分析描述存在偏差，建议重新核对分类是否准确。",
                        "分析内容指向的问题类型与所选分类不完全吻合，请结合实际情况调整。",
                    ],
                    "大致匹配": [
                        "分类选择与分析内容大体相符，建议再核对表述重点是否与所选分类完全对应。",
                        "当前分类与分析方向基本一致，若分类名称与原因表述进一步统一会更好。",
                    ],
                    "匹配": ["错误分类与原因分析内容一致，分类选择较准确，整体逻辑清晰。",
                             "分类与文字说明对应较好，能够反映实际分析方向。",
                             "所选分类与原因分析相互印证，匹配度较高。",
                             "错误分类与原因分析内容高度一致，逻辑清晰。", ]
                },
                "r3.1": {
                    "较差": [
                        "当前措施内容较少，尚未体现明确的处理动作或落实方式，建议补充具体安排。",
                        "现有措施表述偏笼统，暂时难以判断实际执行方式，建议进一步说明下一步处理动作。",
                        "当前措施信息支撑不足，尚未体现明确的处理动作或落实方式，建议补充具体安排。",
                        "当前措施尚未体现明确的处理动作或落实方式，建议补充具体安排。",
                        "现有措施表述较为笼统，建议进一步细化为可执行的处理动作。",
                        "措施描述缺少实质性处理内容，建议补充具体处理动作或相关安排。"
                    ],
                    "一般": [
                        "已提出处理思路，但措施完整度仍可提升。当前对具体执行动作或落实细节说明还不够充分。",
                        "措施方向基本明确，建议进一步补充处理步骤或实施要点。",
                        "当前措施具备初步可行性，若能再细化到具体操作层面，会更便于后续跟踪。",
                        "已提出初步处理计划，建议进一步明确具体动作和落实要点。",
                        "措施方向基本正确，若补充一些实施细节会更清晰。",
                        "当前措施较为基础，建议细化到可执行的行动步骤。"
                    ],
                    "优秀": [
                        "解决措施较明确，包含了具体处理动作或推进方式，整体具备较好的可执行性。",
                        "措施内容较为完整，能够对应问题处理需要，并体现一定的处理思路或落实方向。",
                        "当前措施已体现较为明确的处理动作和落实方向，能够较好支撑后续执行。",
                        "解决措施较为具体，已说明处理动作或推进方式，整体执行方向较清晰。",
                    ]
                },
                "r3.2": {
                    "不匹配": [
                        "原因分析与解决措施之间的对应关系不够清晰，建议根据问题原因补充更有针对性的处理动作。",
                        "当前措施未能充分回应原因分析中的关键问题，建议进一步梳理两者之间的对应关系。",
                        "前后内容存在一定脱节，建议使措施更直接对应分析中提到的问题点。",
                        "解决措施未能直接回应原因分析中提出的问题，建议重新梳理两者之间的逻辑关系。",
                        "措施内容与原因分析脱节，建议根据实际情况补充更有针对性的措施。"
                    ],
                    "大致匹配": [
                        "措施与原因分析有一定关联，建议进一步确保关键问题点均有对应处理动作。",
                        "整体方向基本一致，若能将分析中的重点与措施逐一对应会更完整。",
                    ],
                    "匹配": ["原因分析与解决措施对应较好，前后逻辑较一致，能够形成较完整的处理闭环。",
                             "措施能够回应原因分析中指出的问题，整体匹配度较高。",
                             "前后内容衔接较顺畅，原因判断与处理动作之间具有较好的对应关系。",
                             "解决措施与原因分析高度对应，形成了较完整的闭环。", ]
                }
            },
            "核查确认类": {
                "r2.1": {
                    "较差": [
                        "当前回复信息较少，尚未充分体现核查结论或情况说明，建议补充具体结果。",
                        "现有反馈未能清楚说明指标波动对应的核查判断，建议进一步明确结论及相关情况。",
                        "核查说明仍不够完整，建议补充与预警现象相关的结果说明或判断依据。",
                        "建议明确给出核查最终结论，并简要说明具体情况。",
                        "当前描述更多停留在状态层面，建议补充核查结果依据。",
                        "分析内容可进一步具体化，建议在结论后增加情况说明。"
                    ],
                    "一般": [
                        "已给出结论或状态说明，但情况说明仍可适当补充，以增强判断依据。",
                        "当前回复体现了初步核查结果，但对具体情况的说明还不够充分。",
                        "结论方向基本明确，建议补充简要情况或依据，使回复更完整。",
                        "当前已给出结论，建议补充简短情况说明以增强支撑性。",
                        "结论较清晰，若能简述关键点会更完整。",
                        "当前状态描述较准确，建议增加简要解释或佐证。"
                    ],
                    "优秀": [
                        "核查结论明确，情况说明较完整，能够较好支撑当前判断。",
                        "回复已给出清晰的业务定性，并对相关情况进行了基本说明，整体表达较清楚。",
                        "当前反馈能够对应预警现象，核查结论较明确，并具备基本情况说明。",
                        "核查结论明确且情况说明清晰，逻辑较顺畅。",
                    ]
                },
                "r2.2": {
                    "不匹配": [
                        "错误分类与原因分析之间存在一定冲突，建议根据实际核查结果重新核对分类。",
                        "当前文字说明与所选分类对应性较弱，建议调整为更贴近实际情况的分类。",
                        "分类与原因分析的匹配关系不够清晰，建议统一分类口径与文字表述。",
                        "当前分类与核查结论存在矛盾，请根据实际结果重新选择更准确的分类。",
                        "分类选项未能反映核查的实际情况，建议仔细核对后调整。",
                    ],
                    "大致匹配": [
                        "分类与原因分析大体相符，建议在措辞上进一步统一，以提升匹配度。",
                        "当前分类与结论方向基本一致，但在表述颗粒度上仍可更精确。",
                        "归类方向基本正确，若分类名称与原因表述进一步对齐会更好。",
                        "分类与结论基本吻合，建议在措辞上统一以确保完全对应。",
                        "整体方向正确，若能将关键词与分类定义更精准对齐会更好。",
                    ],
                    "匹配": [
                        "错误分类与原因分析内容一致，整体定性较为准确。",
                        "分类选择能够较好对应文字说明，逻辑关系清晰。",
                        "所选分类与核查结论方向一致，匹配情况较好。",
                        "错误分类与核查结论一致，逻辑自洽。",
                    ]
                },
                "r3.1": {
                    "较差": [
                        "当前措施未体现有效的状态确认或处理信息，难以判断问题是否已完成核查或后续处置，整体闭环支撑不足。",
                        "当前措施说明不足，未明确体现确认结果、处理动作或结单信息，难以支撑对处置状态的判断。",
                        "现有措施未能有效说明当前处理状态或后续处置情况，信息支撑较弱，流程闭环不足。",
                        "当前措施缺少有效的确认或处理内容，无法判断事项是否已完成核查、处理或反馈。",
                        "措施内容较为空泛，未能体现明确的确认状态、处理动作或结果反馈，难以形成有效闭环。",
                    ],
                    "一般": [
                        "当前已体现确认或处理动作，建议结合核查结果补充相关说明，以增强内容完整性。",
                        "当前措施已有基本说明，若能结合核查结果进一步补充相关信息，会更为完整。",
                        "当前内容已体现一定的确认或处理情况，建议补充必要说明，进一步提升信息完整性。",
                    ],
                    "优秀": [
                        "当前措施已围绕核查结果或状态反馈作出说明，能够满足本场景的基本要求。",
                        "当前内容已体现核查确认结果及处理状态，能够支撑对处置情况的基本判断。",
                        "当前措施表达与核查确认类场景要求基本一致，已具备必要的信息支撑。",
                        "当前措施已明确体现核查确认结果或状态反馈，能够满足本场景的基本闭环要求。",
                    ]
                },
                "r3.2": {
                    "不匹配": [
                        "原因分析与采取措施之间的衔接不够充分，建议根据核查结论调整后续动作表述。",
                        "当前措施对结论的支撑性偏弱，建议进一步统一原因分析与措施内容。",
                        "前后内容存在一定不一致，建议结合实际核查情况完善闭环表达。",
                        "采取措施与原因分析存在脱节，建议重新梳理。",
                        "措施内容对原因分析结论的支撑不足，建议根据实际情况调整。",
                    ],
                    "大致匹配": [
                        "整体闭环关系基本成立，建议进一步增强措施对结论的支撑说明。",
                        "原因分析与措施之间存在一定关联，若能更明确呼应关键点会更完整。",
                        "措施与原因分析有一定关联，建议进一步强化两者之间的对应关系。",
                        "整体逻辑成立，若能在措施中更明确回应分析中的关键点会更好。",
                    ],
                    "匹配": [
                        "采取措施与原因分析能够相互印证，整体逻辑较顺畅。",
                        "结论与后续反馈基本吻合，能够支撑当前核查判断。",
                        "措施内容对原因分析起到了较好的补充说明作用，前后逻辑较一致。",
                        "采取的措施与原因分析能够相互印证，形成闭环。",
                    ]
                }
            },
            "流程催办类": {
                "r2.1": {
                    "较差": [
                        "当前未提供有效分析内容，难以判断事项处理状态，建议补充相关说明。",
                        "现有内容对任务进度说明不足，建议补充已开展的动作或处理状态。",
                        "建议在回复中体现实质进展，而不仅是收到通知后的确认状态。",
                        "分析内容需体现实质进展，建议补充当前处理状态而非仅确认收到。",
                    ],
                    "一般": [
                        "已体现当前处理状态，但对进展的描述仍可进一步细化。",
                        "分析内容反映了处理状态，建议补充目前的执行情况或阶段性结果。",
                        "当前描述表明处于进行中，若能提供更具体的进度信息会更完整。",
                        "已说明正在处理，建议补充当前具体进度或阶段性结果。",
                    ],
                    "优秀": [
                        "当前已较清楚说明办理状态，能够支撑对任务进展的基本判断。",
                        "当前已对办理情况作出说明，能够反映任务处理的基本状态。",
                        "已结合当前进度进行了说明，能够反映任务处理的实际状态。",
                        "对于当前处理情况已有说明，能够支撑对任务进展的基本判断。",
                    ]
                },
                "r2.2": {
                    "不匹配": ["本类调度单为催办通知，不涉及错误分类评估，该项按固定分值处理。"],
                    "大致匹配": ["本类调度单为催办通知，不涉及错误分类评估，该项按固定分值处理。"],
                    "匹配": ["本类调度单为催办通知，不涉及错误分类评估，该项按固定分值处理。"]
                },
                "r3.1": {
                    "较差": [
                        "当前措施对具体办理动作说明不足，建议补充是否已提交、办结或正在推进。",
                        "当前措施未明确体现具体办结动作或处理进度，难以判断事项办理状态。",
                        "现有措施更多停留在确认层面，尚未体现实质办理动作，建议补充当前处理进展。",
                    ],
                    "一般": [
                        "已说明处理方向，但对完成节点或具体进展的描述仍可进一步补充。",
                        "建议对正在处理的事项补充当前进展或阶段性结果。",
                        "措施方向基本正确，若能提供更具体的办理进度会更清晰。",
                        "当前措施体现了处理状态，建议进一步补充执行进展。",
                    ],
                    "优秀": [
                        "当前措施能够体现实质性办理动作或办结状态，能够反映事项处置情况。",
                        "当前措施已对办理情况作出说明，能够体现处理进展或当前状态。",
                        "措施内容能够体现当前办理结果或推进状态，整体表达较为明确。",
                    ]
                },
                "r3.2": {
                    "不匹配": [
                        "原因分析与采取措施之间存在一定脱节，建议根据实际处理进度统一表述。",
                        "当前措施未能充分对应原因分析中的状态说明，建议调整为更一致的表达。",
                        "措施内容对原因分析的支撑不足，建议重新梳理并确保两者一致。",
                    ],
                    "大致匹配": [
                        "原因分析与措施基本对应，建议进一步增强两者在进度描述上的一致性。",
                        "措施与原因分析基本对应，若能更明确呼应关键进度点会更完整。",
                        "整体逻辑较顺畅，建议在措施中更明确回应原因分析中的状态描述。",
                    ],
                    "匹配": [
                        "原因分析与采取措施逻辑一致，能够体现从接收到办理推进的对应关系。",
                        "措施与原因分析前后衔接较顺畅，整体对应较好。",
                    ]
                }
            }
        }
        output_format = score_rule_map.get(error_type_to_issue_category.get(error_class_name, "问题处理类"),
                                           score_rule_map.get("问题处理类", {})).get("output")
        score_prompt = f""" # 角色
                            你是一个专业的电信客服回复质量评估助手，结合领域的知识，通过以下给定的调度单信息，对客服的回复内容进行评估打分，并帮助他们改进回复的质量。
                            # 输入
                            <错误原因分类两级标准>
                                系统异常：网络问题、基础设施问题、应用软件问题、软件升级(计划外升级)
                                配置异常：业务参数配置问题、业务规则问题、系统配置问题
                                数据源本身问题：业务平台数据源问题、集团下发数据源问题、其他外围系统数据源问题
                                业务异常：用户行为引起的业务波动、其他业务异常
                            </错误原因分类两级标准>
                            <调度单信息>
                            {background}
                            </调度单信息>
                            <客服的回复内容>
                            {query}
                            </客服的回复内容>
                            # 任务
                            {score_rule_map.get(error_type_to_issue_category.get(error_class_name, "问题处理类"), score_rule_map.get("问题处理类", {})).get("rule")}
                            # 输出
                            请直接按照以下评分报告的json模板输出，每个维度的每个子项都是一个对象，不要包含其他任何字符：
                            ```json
                            {json.dumps(output_format, ensure_ascii=False)}
                            ```
                        """

        def replace_specific_values(target_dict, replacement_map, prefix=None):
            for key in target_dict:
                if isinstance(target_dict[key], dict):
                    replace_specific_values(target_dict[key], replacement_map, key)
                else:
                    if key in replacement_map:
                        target_dict[key] = replacement_map[key]
            if prefix in ['r2.1', 'r2.2', 'r3.1', 'r3.2']:
                for key in replacement_map:
                    if key not in target_dict:
                        target_dict[key] = replacement_map[key]
            return target_dict

        model = LocalLLMComponent(inputs=[
            TextInput(name='query', display_name='Text', value=''),
            TextInput(name='assistant_code', display_name="助手编码", value='BSS-BASE-QM-32'),
            FloatInput(name='temperature', display_name='Temperature', value=0.1),
            TextInput(name='prompt', display_name='Prompt', value=score_prompt),
            TextInput(name='model_name', display_name='Model name', value=LLM_MODELS[0]),
        ])
        model.set_context({})
        total_tokens = None
        try:
            result = await model.run(state={"query": query})
            total_tokens = result.get("total_tokens", None)
        except BaseException as e:
            print(f"大模型调用失败: {e.__class__.__name__}:{e}")
            error_obj = {"explanation": "大模型调用失败", "score": -1, "grade": "无法评估",
                         "suggestion": "大模型调用失败"}
            return {"answer": json.dumps({"score": -1, **replace_specific_values(output_format, error_obj)}),
                    "total_tokens": total_tokens}

        final_response = {}
        try:
            answer = result.get("answer", "")
            if "```" in answer:
                match = re.search(r'```(json)?(.*?)```', answer, re.DOTALL)
                if match:
                    answer = match.group(2)
            answer_obj = json.loads(answer)
            evaluate_report = answer_obj.get('evaluate_report', {})
            r1 = evaluate_report.get('r1', {})
            r21 = evaluate_report.get('r2', {}).get('r2.1', {})
            r22 = evaluate_report.get('r2', {}).get('r2.2', {})
            r31 = evaluate_report.get('r3', {}).get('r3.1', {})
            r32 = evaluate_report.get('r3', {}).get('r3.2', {})
            r4 = evaluate_report.get('r4', {})
            r1_score = int(r1.get('score', 0))
            r21_score = int(r21.get('score', 0))
            r22_score = int(r22.get('score', 0))
            r31_score = int(r31.get('score', 0))
            r32_score = int(r32.get('score', 0))
            r4_score = int(r4.get('score', 0))
            total_score = r1_score + r21_score + r22_score + r31_score + r32_score + r4_score

            final_response["score"] = total_score
            final_response["evaluate_report"] = evaluate_report

            standard_response_dict = standard_responses.get(
                error_type_to_issue_category.get(error_class_name, "问题处理类"), standard_responses["问题处理类"])

            def get_suggestion_by_grade(dimension: str, grade: str) -> [str, None]:
                dimension_standard_response_dict = standard_response_dict.get(dimension, {})
                for k in sorted(dimension_standard_response_dict.keys(), key=len, reverse=True):
                    if k in grade:
                        return random.choice(dimension_standard_response_dict.get(k))
                return random.choice(dimension_standard_response_dict.get('较差')) if '无效' in grade else None

            for dimension, score_obj in [("r2.1", r21), ("r2.2", r22), ("r3.1", r31), ("r3.2", r32)]:
                if len(score_obj) == 0:
                    continue
                suggestion = get_suggestion_by_grade(dimension, score_obj.get('grade', ''))
                if suggestion:
                    score_obj['suggestion'] = suggestion
            return {"answer": json.dumps(final_response, ensure_ascii=False), "total_tokens": total_tokens}
        except BaseException as e:
            print(f"解析错误评估结果失败: {e}，原始数据：{result.get('answer')}")
            error_obj = {"explanation": "大模型返回格式错误导致解析评分结果失败", "score": -1, "grade": "无法评估",
                         "suggestion": "大模型返回格式错误导致解析评分结果失败"}
            return {"answer": json.dumps({"score": -1, **replace_specific_values(output_format, error_obj)}),
                    "total_tokens": total_tokens}

    main = textwrap.dedent(inspect.getsource(main))

    python_repl = PythonREPLComponent(inputs=[DictInput(
        name='args',
        display_name='Args',
        info='The args for python function.',
        value={"error_class_name": f"{{{{ {error_class_name_var}  }}}}", "query": f"{{{{ {query_var}  }}}}",
               "background": f"{{{{ {background_var}  }}}}", "compliance_score": f"{{{{ {compliance_score_var}  }}}}",
               "timeliness_score": f"{{{{ {timeliness_score_var}  }}}}"}
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
            value="{{ " + python_repl.id + ".outputs.result.answer }}",
            enable_expr=True,
        )
    ])
    position = {"width": 10, "height": 10, "x": -1, "y": -1}
    flow['nodes'] = [{"node": chat_input, "position": position},
                     {"node": python_repl, "position": position},
                     {"node": chat_output, "position": position},
                     ]
    flow['edges'] = [{
        "source": chat_input.id,
        "target": python_repl.id,
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
    file_name = '调度单质量_改进建议抽样_20260330_核查催办'
    df = pd.read_excel(rf'D:\文档\开发文件\大模型\BSS稽核\{file_name}.xlsx')

    from server.chat.workflow_chat import do_workflow_chat

    flow = {"nodes": [{"node": {"id": "chat_input-PBYTfP", "name": "chat_input", "display_name": "聊天输入", "description": "获取聊天输入", "tag": "输入", "icon": None, "inputs": [{"id": "query-z3dHNE", "name": "query", "display_name": "查询内容", "required": True, "enable_expr": True, "info": "输入的问题内容", "options": [], "field_type": "str", "value": "", "type": "TextInput"}, {"id": "history_len-3KciqM", "name": "history_len", "display_name": "历史对话轮次", "required": False, "enable_expr": True, "info": "传递给LLM的历史消息的最大数量", "options": [], "field_type": "int", "value": -1, "type": "IntegerInput"}, {"id": "conversation_id-SenBQU", "name": "conversation_id", "display_name": "会话ID", "required": False, "enable_expr": True, "info": "聊天的会话ID，如果为空将自动生成", "options": [], "field_type": "str", "value": None, "type": "TextInput"}, {"id": "knowledge_id-43VK8G", "name": "knowledge_id", "display_name": "知识ID", "required": False, "enable_expr": True, "info": "附件上传后返回的ID", "options": [], "field_type": "str", "value": None, "type": "TextInput"}, {"id": "store_message-4PiDcG", "name": "store_message", "display_name": "是否存储对话", "required": False, "enable_expr": True, "info": "是否将对话存储到数据库中", "options": [], "field_type": "bool", "value": True, "type": "BooleanInput"}, {"id": "extra-3Su9V5", "name": "extra", "display_name": "额外信息", "required": False, "enable_expr": True, "info": "传递给聊天的额外输入", "options": [], "field_type": "dict", "value": {}, "type": "DictInput"}], "outputs": [], "type": "ChatInputComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "python_repl-3rPiNu", "name": "python_repl", "display_name": "Python执行", "description": "执行Python代码", "tag": "工具", "icon": None, "inputs": [{"id": "args-TLg63f", "name": "args", "display_name": "Args", "required": False, "enable_expr": True, "info": "The args for python function.", "options": [], "field_type": "dict", "value": {"error_class_name": "{{ chat_input-PBYTfP.inputs.extra.error_class_name  }}", "query": "{{ chat_input-PBYTfP.inputs.query  }}", "background": "{{ chat_input-PBYTfP.inputs.extra.background  }}", "compliance_score": "{{ chat_input-PBYTfP.inputs.extra.compliance_score  }}", "timeliness_score": "{{ chat_input-PBYTfP.inputs.extra.timeliness_score  }}"}, "type": "DictInput"}, {"id": "python_code-3CnrBi", "name": "python_code", "display_name": "Python", "required": True, "enable_expr": True, "info": "python code.", "options": [], "field_type": "str", "value": "async def main(error_class_name: str, query: str, background: str, compliance_score: str,\n               timeliness_score: str):\n    import json\n    import re\n    import random\n\n    from configs import LLM_MODELS\n    from server.workflow.component.models.local_llm import LocalLLMComponent\n    from server.workflow.utils.inputs import TextInput, FloatInput\n    ISSUE_CATEGORIES = {\n        \"流程催办类\": [\n            \"调研\",\n            \"出账信息填报\"\n        ],\n        \"核查确认类\": [\n            \"环比波动异常\",\n            \"国内数据高额高频下发\",\n            \"出账环比波动\",\n            \"基站数据求取不到\"\n        ],\n        \"问题处理类\": [\n            \"省份文件缺失\",\n            \"省上传文件数不平衡\",\n            \"省上传文件数不完整\",\n            \"话单上传及时率低于阈值异常\",\n            \"其他\",\n            \"通信链路异常\",\n            \"省上传错单\",\n            \"省上传拒收\",\n            \"省份消息接收失败\",\n            \"集团下发错单\",\n            \"集团下发拒收\",\n            \"省文件序列号缺漏\",\n            \"省上传跳号\",\n            \"基础信息缺漏\",\n            \"出账上传质量\",\n            \"政企稽核情况调度\",\n            \"自动拨测\",\n            \"省上传空文件\",\n            \"省上传延迟话单\",\n            \"省未及时上传文件\"\n        ]\n    }\n    error_type_to_issue_category = {\n        error: category\n        for category, errors in ISSUE_CATEGORIES.items()\n        for error in errors\n    }\n    error_class_name = error_class_name.strip()\n    score_rule_map = {\n        \"问题处理类\": {\n            \"rule\": f\"\"\"\n            请按照以下规则进行评分：\n            1. 分数范围： 最低分0分，最高分100分\n            2. 以下是四个维度的评分规则：\n                # 前提条件：\n                1. 调度单信息和回复内容作为一个整体进行评分，不是单独针对某个字段，其他字段已给出的信息均可以作为补充内容进行评分。\n                2. 如果为上下游外部原因导致，非己方问题，可以无需采取措施，仅须通知并协调责任方处理。\n                3. 每个维度之间需要关联打分，需考虑维度之间的关联性。\n                ** 请牢记此前提，所有规则都在要在此前提下进行！！！**\n                ## 一、调度单填写合规性（满分15分）\n                * 直接给固定分数{compliance_score}分\n                ## 二、原因分析质量（满分35分）\n                注：原因分析为空或纯数字字母时此维度只能得0分，例如：“无”“/”“123”“abc”。\n                ### 原因分析的信息完备性（满分25分）\n                * 0-3分：完全没有针对问题的原因分析，或回复内容属于无效的客套话、流程性回复，不包含任何实质性信息。例如：“已通知相关人员处理”“已安排补传”“请集团知晓”“分析中”“持续关注”等。\n                * 4-9分：问题描述过于笼统、模糊，缺乏具体的场景或细节，导致难以判断具体发生了什么问题。\n                * 10-17分：能够准确描述问题的表面现象或报错信息，但未进一步指出问题源头，或缺乏定位问题所需的关键细节（如具体字段、组件等）。\n                * 18-25分：能够深入定位问题根源，不仅明确问题现象，还能精准提供系统处理环节、系统组件、业务规则、上下游原因（集团、下级、外部系统）或具体数据字段等关键定位信息中的至少一项，例如：“VoLTE 话单中 access - domain 字段未填写区号”“错单原因是计费号码到访地区号是字母，如 1027027”。\n                ### 错误分类与原因分析匹配度（满分10分）\n                * 0-4分：完全不符合或相互矛盾，例如：分类选“网络问题”，但分析内容是“业务平台参数配置错误”。\n                * 5-7分：大致匹配，但略有偏差。\n                * 8-10分：选择的`错误原因分类`与填写`原因分析`描述的内容高度匹配。\n                ## 三、解决措施质量（满分35分）\n                注：采取措施为空或纯数字字母时此维度只能得0分，例如：“无”“/”“123”“abc”。\n                ### 解决措施的信息完备性（满分25分）\n                * 0-3分：未提出任何实质性措施，或措施完全不可行、属于推诿性回复；无任何实施细节，属于无效沟通。\n                * 4-9分：仅提出了极其宽泛的方向或原则性建议，未落实到具体动作，难以直接指导执行；基本无实施细节，或细节与实际解决问题关联度极低。\n                * 10-17分：虽然提及了处理方向，但措施表述较为模糊，无法准确判断具体的优化操作；或仅有非常初步的想法、计划及待办状态，缺乏实质性内容。\n                * 18-25分：在解决措施明确性方面，包含具体措施，明确牵头方，并协调相关上下游解决处理，措施明确可执行。同时，在解决措施的信息完备性上，措施包含具体的操作步骤、方法。\n                ### 原因分析与采取措施匹配度（满分10分）\n                * 0-4分：措施与原因分析完全无关，或者未提出任何具体措施。\n                * 5-7分：大致匹配，措施与原因部分相关。\n                * 8-10分：所述“采取措施”与“原因分析”指出的问题一一对应，形成闭环，分析出的原因在措施中得到直接解决。\n                ## 四、调度单回复及时性（满分15分）\n                    * 直接给固定分数{timeliness_score}分\n            3. 每一个子项的得分是一个区间范围，请先确定评分区间范围，然后酌情给分\n            4. 最终分数必须在分数范围内\n            \"\"\",\n            \"output\": {\n                \"evaluate_report\": {\n                    \"r1\": {\n                        \"explanation\": \"固定得分\",\n                        \"score\": \"调度单填写合规性得分\"\n                    },\n                    \"r2\": {\n                        \"r2.1\": {\n                            \"explanation\": \"先深度思考，然后输出原因分析的信息完备性的详细评分过程\",\n                            \"grade\": \"原因分析的信息完备性的评级（例如：优秀(18-25分)、一般(10-17分)、较差(4-9分)、无效(0-3分)）\",\n                            \"score\": \"原因分析的信息完备性得分\"\n                        },\n                        \"r2.2\": {\n                            \"explanation\": \"先深度思考，然后输出错误分类与原因分析匹配度的详细评分过程\",\n                            \"grade\": \"错误分类与原因分析匹配度的评级（例如：匹配(8-10分)、大致匹配(5-7分)、不匹配(0-4分)）\",\n                            \"score\": \"错误分类与原因匹配度得分\"\n                        }\n                    },\n                    \"r3\": {\n                        \"r3.1\": {\n                            \"explanation\": \"先深度思考，然后输出解决措施的信息完备性的详细评分过程\",\n                            \"grade\": \"解决措施的信息完备性的评级（例如：优秀(18-25分)、一般(10-17分)、较差(4-9分)、无效(0-3分)）\",\n                            \"score\": \"解决措施的信息完备性得分\"\n                        },\n                        \"r3.2\": {\n                            \"explanation\": \"先深度思考，然后输出原因与措施匹配度的详细评分过程\",\n                            \"grade\": \"原因分析与采取措施匹配度的评级（例如：匹配(8-10分)、大致匹配(5-7分)、不匹配(0-4分)）\",\n                            \"score\": \"原因与措施匹配度得分\"\n                        }\n                    },\n                    \"r4\": {\n                        \"explanation\": \"固定得分\",\n                        \"score\": \"调度单回复及时性得分\"\n                    }\n                }\n            }\n        },\n        \"核查确认类\": {\n            \"rule\": f\"\"\"\n            请按照以下规则进行评分：\n            1. 分数范围： 最低分0分，最高分100分\n            2. 以下是四个维度的评分规则：\n                ## 一、调度单填写合规性（满分15分）\n                * 直接给固定分数{compliance_score}分\n                ## 二、原因分析质量（满分35分）\n                ### 原因分析的信息完备性（满分35分）\n                * 0-9分：原因分析与调度单完全无关。\n                * 10-24分：明确给出了“正常”或“异常”的结论，或者明确说明了当前的处理状态（如“核查中”），但未对情况进行说明。示例：“省内核查中” → 属于“说明了状态”。“用户正常使用”、“上传正常”、“经核实，用户余额状态和限速状态正常，请集团知悉” → 属于“给出了结论”。\n                * 25-35分：已明确给出核查的最终结果，并说明情况，例如：“核查正常，套内流量”或“经核查发现波动异常，因上游数据下发异常导致”。\n                ## 三、解决措施质量（满分35分）\n                ### 解决措施的信息完备性（满分35分）\n                注：请先独立判断目前是属于正常场景还是异常场景（不受错误分类影响），然后只看对应的标准。\n                * 0-9分：未在措施中给出任何状态确认或有效结论，与调度单完全无关。\n                * 10-24分：正常场景：只给出了核查结果，但未补充说明情况，或者只给出了倾向性判断、确认/签收的动作。异常场景：解决措施较模糊，或者仅说明当前的处理状态。\n                * 25-35分：正常场景：给出核查结果并说明情况（无需任何处理动作），例如：“核查正常，套内流量”。异常场景：针对异常或问题给出处理动作或处理方法。\n                ## 四、调度单回复及时性（满分15分）\n                * 直接给固定分数{timeliness_score}分\n            3. 每一个子项的得分是一个区间范围，请先确定评分区间范围，然后酌情给分\n            4. 最终分数必须在分数范围内\n            \"\"\",\n            \"output\": {\n                \"evaluate_report\": {\n                    \"r1\": {\n                        \"explanation\": \"固定得分\",\n                        \"score\": \"调度单填写合规性得分\"\n                    },\n                    \"r2\": {\n                        \"r2.1\": {\n                            \"explanation\": \"先深度思考，然后输出原因分析的信息完备性的详细评分过程\",\n                            \"grade\": \"原因分析的信息完备性的评级（例如：优秀(25-35分)、一般(10-24分)、较差(0-9分)）\",\n                            \"score\": \"原因分析的信息完备性得分\"\n                        }\n                    },\n                    \"r3\": {\n                        \"r3.1\": {\n                            \"explanation\": \"先深度思考，然后输出解决措施的信息完备性的详细评分过程\",\n                            \"grade\": \"解决措施的信息完备性的评级（例如：优秀(25-35分)、一般(10-24分)、较差(0-9分)）\",\n                            \"score\": \"解决措施的信息完备性得分\"\n                        }\n                    },\n                    \"r4\": {\n                        \"explanation\": \"固定得分\",\n                        \"score\": \"调度单回复及时性得分\"\n                    }\n                }\n            }\n        },\n        \"流程催办类\": {\n            \"rule\": f\"\"\"\n            请按照以下规则进行评分：\n            1. 分数范围： 最低分0分，最高分100分\n            2. 以下是四个维度的评分规则：\n                ## 一、调度单填写合规性（满分15分）\n                * 直接给固定分数{compliance_score}分\n                ## 二、原因分析质量（满分35分）\n                ### 原因分析的信息完备性（满分35分）\n                * 0-9分： 从原因分析内容仅能推出针对调度单通知的催办内容未开展任何动作，仅仅处于签收状态。例如：“已收到”、“已确认”、“已知晓”、“已知悉”、“遵办”等等。或者原因分析与调度单催办通知内容完全无关。\n                * 10-24分：从原因分析内容仅能推出目前针对调度单通知的催办内容处于进行中或者未完成状态。涵盖情况：“已通知相关人员填报”、“转负责同事处理”、“将按时填写”、“由于某某原因暂未填写/处理”、“正在填写”等等。\n                * 25-35分：从原因分析内容可以推理出目前针对调度单通知的催办内容已办结、已提交、已处理或者处于已完成状态（即可得25分基础分），例如：“已填报”、“已填写”、“已完成/已处理”、“已上报”等等。增加清晰、详细的描述可酌情加分，例如：“省内已填报，烦请集团核实”，“按照集团要求执行，吉林已上报”（可以给25分-35分）。\n                ## 三、解决措施质量（满分35分）\n                ### 解决措施的信息完备性（满分35分）\n                * 0-9分： 从采取措施内容仅能推出针对调度单通知的催办内容未开展任何动作，仅仅处于签收状态。例如：“已收到”、“已确认”、“已知晓”、“已知悉”等等。或者采取措施与调度单催办通知内容完全无关。\n                * 10-24分：从采取措施内容仅能推出目前针对调度单通知的催办内容处于进行中或者未完成状态。涵盖情况：“已通知相关人员填报”、“转负责同事处理”、“将按时填写”、“由于某某原因暂未填写/处理”、“正在填写”等等。\n                * 25-35分：从采取措施内容可以推理出目前针对调度单通知的催办内容已办结、已提交、已处理或者处于已完成状态（即可得25分基础分），例如：“已填报”、“已填写”、“已完成/已处理”、“已上报”等等。增加清晰、详细的描述可酌情加分，例如：“省内已填报，烦请集团核实”，“按照集团要求执行，吉林已上报”（可以给25分-35分）。\n                ## 四、调度单回复及时性（满分15分）\n                    * 直接给固定分数{timeliness_score}分\n            3. 每一个子项的得分是一个区间范围，请先确定评分区间范围，然后酌情给分\n            4. 最终分数必须在分数范围内\n            \"\"\",\n            \"output\": {\n                \"evaluate_report\": {\n                    \"r1\": {\n                        \"explanation\": \"固定得分\",\n                        \"score\": \"调度单填写合规性得分\"\n                    },\n                    \"r2\": {\n                        \"r2.1\": {\n                            \"explanation\": \"先深度思考，然后输出原因分析的信息完备性的详细评分过程\",\n                            \"grade\": \"原因分析的信息完备性的评级（例如：优秀(25-35分)、一般(10-24分)、较差(0-9分)）\",\n                            \"score\": \"原因分析的信息完备性得分\"\n                        }\n                    },\n                    \"r3\": {\n                        \"r3.1\": {\n                            \"explanation\": \"先深度思考，然后输出解决措施的信息完备性的详细评分过程\",\n                            \"grade\": \"解决措施的信息完备性的评级（例如：优秀(25-35分)、一般(10-24分)、较差(0-9分)）\",\n                            \"score\": \"解决措施的信息完备性得分\"\n                        }\n                    },\n                    \"r4\": {\n                        \"explanation\": \"固定得分\",\n                        \"score\": \"调度单回复及时性得分\"\n                    }\n                }\n            }\n        }\n    }\n\n    standard_responses = {\n        \"问题处理类\": {\n            \"r2.1\": {\n                \"无效\": [\n                    \"当前内容仅体现处理动作或沟通反馈，未进一步说明具体问题原因或异常环节，暂无法支撑问题定位与原因判断。\",\n                    \"现有描述未体现具体问题原因、影响对象或相关处理环节，暂不构成有效原因分析。\",\n                    \"当前原因分析信息不足，主要为状态反馈或处理说明，缺少对问题原因及异常链路的有效描述。\",\n                    \"当前内容未进一步说明问题原因、异常场景或影响环节，难以支撑后续问题判断与原因复盘。\"\n                ],\n                \"较差\": [\n                    \"原因分析较为简略，当前尚不足以支撑对问题的准确判断，未能明确说明具体问题原因或异常环节。\",\n                    \"当前描述偏概括，尚未体现具体问题原因或异常定位，缺少对异常表现、处理环节或上下游关系的有效说明。\",\n                    \"现有内容信息支撑不足，缺少与问题原因相关的关键说明，暂无法形成较完整的问题定位依据。\",\n                    \"当前原因分析支撑不足，尚未明确具体问题原因、涉及环节或异常链路，对问题定位帮助有限。\",\n                    \"现有描述较为笼统，未明确异常原因、对应处理环节或上下游影响关系，缺少有效定位信息。\",\n                    \"当前原因分析较为模糊，缺少能够支撑问题判断的关键原因说明或异常定位信息。\",\n                ],\n                \"一般\": [\n                    \"原因分析已有基本方向，但当前更多停留在异常现象描述层面，对具体问题原因、处理环节或异常链路说明还不够充分。\",\n                    \"当前已给出初步原因判断，但对具体问题点、触发原因或上下游关系的描述仍可进一步细化，以便更准确支撑结论。\",\n                    \"分析内容具备一定参考性，但关键问题定位仍不够明确，建议进一步补充异常原因、影响范围或相关处理环节说明。\",\n                    \"当前已说明相关异常现象，但对具体问题原因、涉及环节或异常触发场景的描述仍不够完整。\",\n                    \"分析方向基本明确，但对具体异常对象或原因关联关系的说明仍可进一步细化。\",\n                    \"当前内容已具备一定分析基础，若进一步补充问题原因、异常场景或相关影响环节，将更有助于支撑判断。\"\n                ],\n                \"优秀\": [\n                    \"定位较为明确，原因分析较完整。已说明具体处理环节、业务规则、上下游关系或相关数据字段，能够较好支撑问题判断与原因定位。\",\n                    \"原因说明较为清晰。能够从异常现象进一步定位到具体问题点，并对问题原因、影响对象或异常链路进行有效说明，整体逻辑较完整。\",\n                    \"分析较有针对性。已结合具体异常对象、错误描述、上下游关系或相关特征进行说明，对问题判断具有较好的参考价值。\",\n                    \"原因分析较为完整，已对问题定位、异常原因及相关依据作出说明，能够较好支撑原因判断与问题复盘。\"\n                ]\n            },\n            \"r2.2\": {\n                \"不匹配\": [\n                    \"错误分类与原因分析之间存在明显偏差，建议结合实际原因重新核对分类选择。\",\n                    \"当前分类与原因说明不够一致，建议根据主要原因调整为更贴合的分类。\",\n                    \"文字内容与所选分类对应关系较弱，建议统一分类与原因分析的表达口径。\",\n                    \"当前错误分类与原因分析描述存在偏差，建议重新核对分类是否准确。\",\n                    \"分析内容指向的问题类型与所选分类不完全吻合，请结合实际情况调整。\",\n                ],\n                \"大致匹配\": [\n                    \"分类选择与分析内容大体相符，建议再核对表述重点是否与所选分类完全对应。\",\n                    \"当前分类与分析方向基本一致，若分类名称与原因表述进一步统一会更好。\",\n                ],\n                \"匹配\": [\"错误分类与原因分析内容一致，分类选择较准确，整体逻辑清晰。\",\n                         \"分类与文字说明对应较好，能够反映实际分析方向。\",\n                         \"所选分类与原因分析相互印证，匹配度较高。\",\n                         \"错误分类与原因分析内容高度一致，逻辑清晰。\", ]\n            },\n            \"r3.1\": {\n                \"较差\": [\n                    \"当前措施内容较少，尚未体现明确的处理动作或落实方式，建议补充具体安排。\",\n                    \"现有措施表述偏笼统，暂时难以判断实际执行方式，建议进一步说明下一步处理动作。\",\n                    \"当前措施信息支撑不足，尚未体现明确的处理动作或落实方式，建议补充具体安排。\",\n                    \"当前措施尚未体现明确的处理动作或落实方式，建议补充具体安排。\",\n                    \"现有措施表述较为笼统，建议进一步细化为可执行的处理动作。\",\n                    \"措施描述缺少实质性处理内容，建议补充具体处理动作或相关安排。\"\n                ],\n                \"一般\": [\n                    \"已提出处理思路，但措施完整度仍可提升。当前对具体执行动作或落实细节说明还不够充分。\",\n                    \"措施方向基本明确，建议进一步补充处理步骤或实施要点。\",\n                    \"当前措施具备初步可行性，若能再细化到具体操作层面，会更便于后续跟踪。\",\n                    \"已提出初步处理计划，建议进一步明确具体动作和落实要点。\",\n                    \"措施方向基本正确，若补充一些实施细节会更清晰。\",\n                    \"当前措施较为基础，建议细化到可执行的行动步骤。\"\n                ],\n                \"优秀\": [\n                    \"解决措施较明确，包含了具体处理动作或推进方式，整体具备较好的可执行性。\",\n                    \"措施内容较为完整，能够对应问题处理需要，并体现一定的处理思路或落实方向。\",\n                    \"当前措施已体现较为明确的处理动作和落实方向，能够较好支撑后续执行。\",\n                    \"解决措施较为具体，已说明处理动作或推进方式，整体执行方向较清晰。\",\n                ]\n            },\n            \"r3.2\": {\n                \"不匹配\": [\n                    \"原因分析与解决措施之间的对应关系不够清晰，建议根据问题原因补充更有针对性的处理动作。\",\n                    \"当前措施未能充分回应原因分析中的关键问题，建议进一步梳理两者之间的对应关系。\",\n                    \"前后内容存在一定脱节，建议使措施更直接对应分析中提到的问题点。\",\n                    \"解决措施未能直接回应原因分析中提出的问题，建议重新梳理两者之间的逻辑关系。\",\n                    \"措施内容与原因分析脱节，建议根据实际情况补充更有针对性的措施。\"\n                ],\n                \"大致匹配\": [\n                    \"措施与原因分析有一定关联，建议进一步确保关键问题点均有对应处理动作。\",\n                    \"整体方向基本一致，若能将分析中的重点与措施逐一对应会更完整。\",\n                ],\n                \"匹配\": [\"原因分析与解决措施对应较好，前后逻辑较一致，能够形成较完整的处理闭环。\",\n                         \"措施能够回应原因分析中指出的问题，整体匹配度较高。\",\n                         \"前后内容衔接较顺畅，原因判断与处理动作之间具有较好的对应关系。\",\n                         \"解决措施与原因分析高度对应，形成了较完整的闭环。\", ]\n            }\n        },\n        \"核查确认类\": {\n            \"r2.1\": {\n                \"较差\": [\n                    \"当前回复信息较少，尚未充分体现核查结论或情况说明，建议补充具体结果。\",\n                    \"现有反馈未能清楚说明指标波动对应的核查判断，建议进一步明确结论及相关情况。\",\n                    \"核查说明仍不够完整，建议补充与预警现象相关的结果说明或判断依据。\",\n                    \"建议明确给出核查最终结论，并简要说明具体情况。\",\n                    \"当前描述更多停留在状态层面，建议补充核查结果依据。\",\n                    \"分析内容可进一步具体化，建议在结论后增加情况说明。\"\n                ],\n                \"一般\": [\n                    \"已给出结论或状态说明，但情况说明仍可适当补充，以增强判断依据。\",\n                    \"当前回复体现了初步核查结果，但对具体情况的说明还不够充分。\",\n                    \"结论方向基本明确，建议补充简要情况或依据，使回复更完整。\",\n                    \"当前已给出结论，建议补充简短情况说明以增强支撑性。\",\n                    \"结论较清晰，若能简述关键点会更完整。\",\n                    \"当前状态描述较准确，建议增加简要解释或佐证。\"\n                ],\n                \"优秀\": [\n                    \"核查结论明确，情况说明较完整，能够较好支撑当前判断。\",\n                    \"回复已给出清晰的业务定性，并对相关情况进行了基本说明，整体表达较清楚。\",\n                    \"当前反馈能够对应预警现象，核查结论较明确，并具备基本情况说明。\",\n                    \"核查结论明确且情况说明清晰，逻辑较顺畅。\",\n                ]\n            },\n            \"r2.2\": {\n                \"不匹配\": [\n                    \"错误分类与原因分析之间存在一定冲突，建议根据实际核查结果重新核对分类。\",\n                    \"当前文字说明与所选分类对应性较弱，建议调整为更贴近实际情况的分类。\",\n                    \"分类与原因分析的匹配关系不够清晰，建议统一分类口径与文字表述。\",\n                    \"当前分类与核查结论存在矛盾，请根据实际结果重新选择更准确的分类。\",\n                    \"分类选项未能反映核查的实际情况，建议仔细核对后调整。\",\n                ],\n                \"大致匹配\": [\n                    \"分类与原因分析大体相符，建议在措辞上进一步统一，以提升匹配度。\",\n                    \"当前分类与结论方向基本一致，但在表述颗粒度上仍可更精确。\",\n                    \"归类方向基本正确，若分类名称与原因表述进一步对齐会更好。\",\n                    \"分类与结论基本吻合，建议在措辞上统一以确保完全对应。\",\n                    \"整体方向正确，若能将关键词与分类定义更精准对齐会更好。\",\n                ],\n                \"匹配\": [\n                    \"错误分类与原因分析内容一致，整体定性较为准确。\",\n                    \"分类选择能够较好对应文字说明，逻辑关系清晰。\",\n                    \"所选分类与核查结论方向一致，匹配情况较好。\",\n                    \"错误分类与核查结论一致，逻辑自洽。\",\n                ]\n            },\n            \"r3.1\": {\n                \"较差\": [\n                    \"当前措施未体现有效的状态确认或处理信息，难以判断问题是否已完成核查或后续处置，整体闭环支撑不足。\",\n                    \"当前措施说明不足，未明确体现确认结果、处理动作或结单信息，难以支撑对处置状态的判断。\",\n                    \"现有措施未能有效说明当前处理状态或后续处置情况，信息支撑较弱，流程闭环不足。\",\n                    \"当前措施缺少有效的确认或处理内容，无法判断事项是否已完成核查、处理或反馈。\",\n                    \"措施内容较为空泛，未能体现明确的确认状态、处理动作或结果反馈，难以形成有效闭环。\",\n                ],\n                \"一般\": [\n                    \"当前已体现确认或处理动作，建议结合核查结果补充相关说明，以增强内容完整性。\",\n                    \"当前措施已有基本说明，若能结合核查结果进一步补充相关信息，会更为完整。\",\n                    \"当前内容已体现一定的确认或处理情况，建议补充必要说明，进一步提升信息完整性。\",\n                ],\n                \"优秀\": [\n                    \"当前措施已围绕核查结果或状态反馈作出说明，能够满足本场景的基本要求。\",\n                    \"当前内容已体现核查确认结果及处理状态，能够支撑对处置情况的基本判断。\",\n                    \"当前措施表达与核查确认类场景要求基本一致，已具备必要的信息支撑。\",\n                    \"当前措施已明确体现核查确认结果或状态反馈，能够满足本场景的基本闭环要求。\",\n                ]\n            },\n            \"r3.2\": {\n                \"不匹配\": [\n                    \"原因分析与采取措施之间的衔接不够充分，建议根据核查结论调整后续动作表述。\",\n                    \"当前措施对结论的支撑性偏弱，建议进一步统一原因分析与措施内容。\",\n                    \"前后内容存在一定不一致，建议结合实际核查情况完善闭环表达。\",\n                    \"采取措施与原因分析存在脱节，建议重新梳理。\",\n                    \"措施内容对原因分析结论的支撑不足，建议根据实际情况调整。\",\n                ],\n                \"大致匹配\": [\n                    \"整体闭环关系基本成立，建议进一步增强措施对结论的支撑说明。\",\n                    \"原因分析与措施之间存在一定关联，若能更明确呼应关键点会更完整。\",\n                    \"措施与原因分析有一定关联，建议进一步强化两者之间的对应关系。\",\n                    \"整体逻辑成立，若能在措施中更明确回应分析中的关键点会更好。\",\n                ],\n                \"匹配\": [\n                    \"采取措施与原因分析能够相互印证，整体逻辑较顺畅。\",\n                    \"结论与后续反馈基本吻合，能够支撑当前核查判断。\",\n                    \"措施内容对原因分析起到了较好的补充说明作用，前后逻辑较一致。\",\n                    \"采取的措施与原因分析能够相互印证，形成闭环。\",\n                ]\n            }\n        },\n        \"流程催办类\": {\n            \"r2.1\": {\n                \"较差\": [\n                    \"当前未提供有效分析内容，难以判断事项处理状态，建议补充相关说明。\",\n                    \"现有内容对任务进度说明不足，建议补充已开展的动作或处理状态。\",\n                    \"建议在回复中体现实质进展，而不仅是收到通知后的确认状态。\",\n                    \"分析内容需体现实质进展，建议补充当前处理状态而非仅确认收到。\",\n                ],\n                \"一般\": [\n                    \"已体现当前处理状态，但对进展的描述仍可进一步细化。\",\n                    \"分析内容反映了处理状态，建议补充目前的执行情况或阶段性结果。\",\n                    \"当前描述表明处于进行中，若能提供更具体的进度信息会更完整。\",\n                    \"已说明正在处理，建议补充当前具体进度或阶段性结果。\",\n                ],\n                \"优秀\": [\n                    \"当前已较清楚说明办理状态，能够支撑对任务进展的基本判断。\",\n                    \"当前已对办理情况作出说明，能够反映任务处理的基本状态。\",\n                    \"已结合当前进度进行了说明，能够反映任务处理的实际状态。\",\n                    \"对于当前处理情况已有说明，能够支撑对任务进展的基本判断。\",\n                ]\n            },\n            \"r2.2\": {\n                \"不匹配\": [\"本类调度单为催办通知，不涉及错误分类评估，该项按固定分值处理。\"],\n                \"大致匹配\": [\"本类调度单为催办通知，不涉及错误分类评估，该项按固定分值处理。\"],\n                \"匹配\": [\"本类调度单为催办通知，不涉及错误分类评估，该项按固定分值处理。\"]\n            },\n            \"r3.1\": {\n                \"较差\": [\n                    \"当前措施对具体办理动作说明不足，建议补充是否已提交、办结或正在推进。\",\n                    \"当前措施未明确体现具体办结动作或处理进度，难以判断事项办理状态。\",\n                    \"现有措施更多停留在确认层面，尚未体现实质办理动作，建议补充当前处理进展。\",\n                ],\n                \"一般\": [\n                    \"已说明处理方向，但对完成节点或具体进展的描述仍可进一步补充。\",\n                    \"建议对正在处理的事项补充当前进展或阶段性结果。\",\n                    \"措施方向基本正确，若能提供更具体的办理进度会更清晰。\",\n                    \"当前措施体现了处理状态，建议进一步补充执行进展。\",\n                ],\n                \"优秀\": [\n                    \"当前措施能够体现实质性办理动作或办结状态，能够反映事项处置情况。\",\n                    \"当前措施已对办理情况作出说明，能够体现处理进展或当前状态。\",\n                    \"措施内容能够体现当前办理结果或推进状态，整体表达较为明确。\",\n                ]\n            },\n            \"r3.2\": {\n                \"不匹配\": [\n                    \"原因分析与采取措施之间存在一定脱节，建议根据实际处理进度统一表述。\",\n                    \"当前措施未能充分对应原因分析中的状态说明，建议调整为更一致的表达。\",\n                    \"措施内容对原因分析的支撑不足，建议重新梳理并确保两者一致。\",\n                ],\n                \"大致匹配\": [\n                    \"原因分析与措施基本对应，建议进一步增强两者在进度描述上的一致性。\",\n                    \"措施与原因分析基本对应，若能更明确呼应关键进度点会更完整。\",\n                    \"整体逻辑较顺畅，建议在措施中更明确回应原因分析中的状态描述。\",\n                ],\n                \"匹配\": [\n                    \"原因分析与采取措施逻辑一致，能够体现从接收到办理推进的对应关系。\",\n                    \"措施与原因分析前后衔接较顺畅，整体对应较好。\",\n                ]\n            }\n        }\n    }\n    output_format = score_rule_map.get(error_type_to_issue_category.get(error_class_name, \"问题处理类\"),\n                                       score_rule_map.get(\"问题处理类\", {})).get(\"output\")\n    score_prompt = f\"\"\" # 角色\n                        你是一个专业的电信客服回复质量评估助手，结合领域的知识，通过以下给定的调度单信息，对客服的回复内容进行评估打分，并帮助他们改进回复的质量。\n                        # 输入\n                        <错误原因分类两级标准>\n                            系统异常：网络问题、基础设施问题、应用软件问题、软件升级(计划外升级)\n                            配置异常：业务参数配置问题、业务规则问题、系统配置问题\n                            数据源本身问题：业务平台数据源问题、集团下发数据源问题、其他外围系统数据源问题\n                            业务异常：用户行为引起的业务波动、其他业务异常\n                        </错误原因分类两级标准>\n                        <调度单信息>\n                        {background}\n                        </调度单信息>\n                        <客服的回复内容>\n                        {query}\n                        </客服的回复内容>\n                        # 任务\n                        {score_rule_map.get(error_type_to_issue_category.get(error_class_name, \"问题处理类\"), score_rule_map.get(\"问题处理类\", {})).get(\"rule\")}\n                        # 输出\n                        请直接按照以下评分报告的json模板输出，每个维度的每个子项都是一个对象，不要包含其他任何字符：\n                        ```json\n                        {json.dumps(output_format, ensure_ascii=False)}\n                        ```\n                    \"\"\"\n\n    def replace_specific_values(target_dict, replacement_map, prefix=None):\n        for key in target_dict:\n            if isinstance(target_dict[key], dict):\n                replace_specific_values(target_dict[key], replacement_map, key)\n            else:\n                if key in replacement_map:\n                    target_dict[key] = replacement_map[key]\n        if prefix in ['r2.1', 'r2.2', 'r3.1', 'r3.2']:\n            for key in replacement_map:\n                if key not in target_dict:\n                    target_dict[key] = replacement_map[key]\n        return target_dict\n\n    model = LocalLLMComponent(inputs=[\n        TextInput(name='query', display_name='Text', value=''),\n        TextInput(name='assistant_code', display_name=\"助手编码\", value='BSS-BASE-QM-32'),\n        FloatInput(name='temperature', display_name='Temperature', value=0.1),\n        TextInput(name='prompt', display_name='Prompt', value=score_prompt),\n        TextInput(name='model_name', display_name='Model name', value=LLM_MODELS[0]),\n    ])\n    model.set_context({})\n    total_tokens = None\n    try:\n        result = await model.run(state={\"query\": query})\n        total_tokens = result.get(\"total_tokens\", None)\n    except BaseException as e:\n        print(f\"大模型调用失败: {e}\")\n        error_obj = {\"explanation\": \"大模型调用失败\", \"score\": -1, \"grade\": \"无法评估\",\n                     \"suggestion\": \"大模型调用失败\"}\n        return {\"answer\": json.dumps({\"score\": -1, **replace_specific_values(output_format, error_obj)}),\n                \"total_tokens\": total_tokens}\n\n    final_response = {}\n    try:\n        answer = result.get(\"answer\", \"\")\n        if \"```\" in answer:\n            match = re.search(r'```(json)?(.*?)```', answer, re.DOTALL)\n            if match:\n                answer = match.group(2)\n        answer_obj = json.loads(answer)\n        evaluate_report = answer_obj.get('evaluate_report', {})\n        r1 = evaluate_report.get('r1', {})\n        r21 = evaluate_report.get('r2', {}).get('r2.1', {})\n        r22 = evaluate_report.get('r2', {}).get('r2.2', {})\n        r31 = evaluate_report.get('r3', {}).get('r3.1', {})\n        r32 = evaluate_report.get('r3', {}).get('r3.2', {})\n        r4 = evaluate_report.get('r4', {})\n        r1_score = int(r1.get('score', 0))\n        r21_score = int(r21.get('score', 0))\n        r22_score = int(r22.get('score', 0))\n        r31_score = int(r31.get('score', 0))\n        r32_score = int(r32.get('score', 0))\n        r4_score = int(r4.get('score', 0))\n        total_score = r1_score + r21_score + r22_score + r31_score + r32_score + r4_score\n\n        final_response[\"score\"] = total_score\n        final_response[\"evaluate_report\"] = evaluate_report\n\n        standard_response_dict = standard_responses.get(\n            error_type_to_issue_category.get(error_class_name, \"问题处理类\"), standard_responses[\"问题处理类\"])\n\n        def get_suggestion_by_grade(dimension: str, grade: str) -> [str, None]:\n            dimension_standard_response_dict = standard_response_dict.get(dimension, {})\n            for k in sorted(dimension_standard_response_dict.keys(), key=len, reverse=True):\n                if k in grade:\n                    return random.choice(dimension_standard_response_dict.get(k))\n            return random.choice(dimension_standard_response_dict.get('较差')) if '无效' in grade else None\n\n        for dimension, score_obj in [(\"r2.1\", r21), (\"r2.2\", r22), (\"r3.1\", r31), (\"r3.2\", r32)]:\n            if len(score_obj) == 0:\n                continue\n            suggestion = get_suggestion_by_grade(dimension, score_obj.get('grade', ''))\n            if suggestion:\n                score_obj['suggestion'] = suggestion\n        return {\"answer\": json.dumps(final_response, ensure_ascii=False), \"total_tokens\": total_tokens}\n    except BaseException as e:\n        print(f\"解析错误评估结果失败: {e}，原始数据：{result.get('answer')}\")\n        error_obj = {\"explanation\": \"大模型返回格式错误导致解析评分结果失败\", \"score\": -1, \"grade\": \"无法评估\",\n                     \"suggestion\": \"大模型返回格式错误导致解析评分结果失败\"}\n        return {\"answer\": json.dumps({\"score\": -1, **replace_specific_values(output_format, error_obj)}),\n                \"total_tokens\": total_tokens}\n", "type": "TextInput"}], "outputs": [{"id": "result-3GmcZj", "name": "result", "display_name": "结果", "info": None, "enable_expr": False, "field_type": "dict", "value": {}, "type": "DictOutput"}, {"id": "total_tokens-46izmH", "name": "total_tokens", "display_name": "总token数量", "info": None, "enable_expr": False, "field_type": "str", "value": None, "type": "TextOutput"}], "type": "PythonREPLComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}, {"node": {"id": "chat_output-43CTSP", "name": "chat_output", "display_name": "聊天输出", "description": "获取聊天输出", "tag": "输出", "icon": None, "inputs": [], "outputs": [{"id": "answer-4GgPTZ", "name": "answer", "display_name": "Answer", "info": None, "enable_expr": True, "field_type": "str", "value": "{{ python_repl-3rPiNu.outputs.result.answer }}", "type": "TextOutput"}], "type": "ChatOutputComponent"}, "position": {"width": 10, "height": 10, "x": -1, "y": -1}}], "edges": [{"source": "chat_input-PBYTfP", "target": "python_repl-3rPiNu"}, {"source": "python_repl-3rPiNu", "target": "chat_output-43CTSP"}]}

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
                    "error_class_name": row['error_class_name'],
                    "background": f"""
                        调度类型：{row['workorder_type_name']}
                        错单类型：{row['error_class_name']}
                        错单代码：{row['error_code']}
                        错单字段名称：{row['field_name']}
                        错单代码描述：{row['error_code_desc']}
                        错单描述：{row['error_description']}
                        """,
                }, workflow_config=flow, stream=False, store_message=False)
            if isinstance(chat_response, EventSourceResponse):
                async for chunk in chat_response.body_iterator:
                    try:
                        result = json.loads(json.loads(chunk)['answer'][-1]['outputs']['answer'])
                    except BaseException as e:
                        raise ValueError(f"{e}：{chunk}")
                    score_list.append(result['score'])
                    er = result['evaluate_report']
                    r1 = er.get('r1', {})
                    r21 = er.get('r2', {}).get('r2.1', {})
                    r22 = er.get('r2', {}).get('r2.2', {})
                    r31 = er.get('r3', {}).get('r3.1', {})
                    r32 = er.get('r3', {}).get('r3.2', {})
                    r4 = er.get('r4', {})
                    er_str = f"""
                        【调度单填写合规性】
                        得分：{r1.get('score')}分
                        评分依据：{r1.get('explanation')}
                    """
                    if r21:
                        er_str += f"""
                        【原因分析的信息完备性】
                        评级：{r21.get('grade')}
                        得分：{r21.get('score')}分
                        评分依据：{r21.get('explanation')}
                        评估建议：{r21.get('suggestion')}
                        """
                    if r22:
                        er_str += f"""    
                        【错误分类与原因分析匹配度】
                        评级：{r22.get('grade')}
                        得分：{r22.get('score')}分
                        评分依据：{r22.get('explanation')}
                        评估建议：{r22.get('suggestion')}
                        """
                    if r31:
                        er_str += f"""    
                        【解决措施的信息完备性】
                        评级：{r31.get('grade')}
                        得分：{r31.get('score')}分
                        评分依据：{r31.get('explanation')}
                        评估建议：{r31.get('suggestion')}
                        """
                    if r32:
                        er_str += f"""    
                        【原因分析与采取措施匹配度】
                        评级：{r32.get('grade')}
                        得分：{r32.get('score')}分
                        评分依据：{r32.get('explanation')}
                        评估建议：{r32.get('suggestion')}
                        """

                    er_str += f"""
                        【调度单回复及时性】
                        得分：{r4.get('score')}分
                        评分依据：{r4.get('explanation')}
                    """
                    evaluate_report.append(er_str)
        except BaseException as e:
            score_list.append(-1)
            evaluate_report.append(f"执行报错：{e}")
    while len(score_list) < len(df):
        score_list.append(None)
        evaluate_report.append("数据缺失")
    df['new_score'] = score_list
    df['new_score_report'] = evaluate_report
    df.to_excel(rf'D:\文档\开发文件\大模型\BSS稽核\{file_name}结果文件.xlsx', index=False)


@pytest.mark.asyncio
async def test_duplicate_alarm_rule():
    query = ''
    rule_a = """
            KPI名称：集团国际清算系统香港和记及时性告警
            公式：列4(业务名称)='香港和记' and 列5(文件传输个数)<1
            字段映射：
            region_id 省份ID
            region_name 省份
            file_type 文件类型
            busi_name 业务名称
            file_num 文件传输个数
            morethan12h_filenum 最晚传输时间大于12点的文件个数
            稽核SQL：SELECT
  r.region_id,
  r.region_name,
  r.file_type,
  r.busi_name,
  COUNT(r.file_name) file_num,
  SUM(r.more_than_12_num) morethan12h_filenum 
FROM
  (
    SELECT
      1 region_id,
      '平台' region_name,
      '*gz' file_type,
      '下发特通业务清单' busi_name,
      file_name,
      indb_time,
    CASE
        
        WHEN begin_datetime > to_timestamp(SUBSTRING(&source_begin_date, 1, 8) || '120000', 'yyyymmddhh24miss') THEN
        1 ELSE 0 
      END more_than_12_num 
FROM
  info_jt_sr_40200010 
WHERE
  file_name LIKE'%gz' 
  AND busi_class = '65020103' 
  AND model_id IN (24, 25, 28) 
  AND begin_datetime >= to_timestamp(&source_begin_date, 'yyyymmddhh24miss') 
  AND begin_datetime <= to_timestamp(&source_end_date, 'yyyymmddhh24miss') 
UNION ALL
SELECT
  1 region_id,
  '平台' region_name,
  'CTG_static_INT_MOBILEPHN_PREFIX.*.dat' file_type,
  '下发国际公司固网CTG_static清单' busi_name,
  file_name,
  indb_time,
CASE
      
      WHEN begin_datetime > to_timestamp(SUBSTRING(&source_begin_date, 1, 8) || '120000', 'yyyymmddhh24miss') THEN
      1 ELSE 0 
  END more_than_12_num 
FROM
  info_jt_sr_40200010 
WHERE
  file_name LIKE'CTG_static_INT_MOBILEPHN_PREFIX.%.dat' 
  AND busi_class = '65100112' 
  AND model_id IN (24, 25, 28) 
  AND begin_datetime >= to_timestamp(&source_begin_date, 'yyyymmddhh24miss') 
  AND begin_datetime <= to_timestamp(&source_end_date, 'yyyymmddhh24miss') 
union all 
select
1 region_id,
'平台' region_name,
'ISS*AUD' file_type,
'下发账务ISS日汇总AUD文件' busi_name,
file_name,
indb_time,
0 morethan12h_filenum
from
info_jt_sr_40200010
where
file_name like 'ISS%AUD'
and busi_class in ('65020052')
and model_id in (24,25,28) 
and begin_datetime >= to_timestamp(&source_begin_date,'yyyymmddhh24miss')
and begin_datetime <= to_timestamp(&source_end_date,'yyyymmddhh24miss')   
union all 
select
1 region_id,
'平台' region_name,
'ISSF*NOR*' file_type,
'下发账务ISSF账单NOR文件' busi_name,
file_name,
indb_time,
0 morethan12h_filenum
from
info_jt_sr_40200010
where
file_name like 'ISSF%NOR%'
and busi_class in ('65020055')
and model_id in (24,25,28) 
and begin_datetime >= to_timestamp(&source_begin_date,'yyyymmddhh24miss')
and begin_datetime <= to_timestamp(&source_end_date,'yyyymmddhh24miss')   
union all 
select
1 region_id,
'平台' region_name,
'SLROAM*' file_type,
'下发国际漫游优选平台' busi_name,
file_name,
indb_time,
0 morethan12h_filenum
from
info_jt_sr_40200010
where
file_name like 'SLROAM%'
and busi_class in ('65010158')
and model_id in (24,25,28) 
and begin_datetime >= to_timestamp(&source_begin_date,'yyyymmddhh24miss')
and begin_datetime <= to_timestamp(&source_end_date,'yyyymmddhh24miss')   
union all 
select
1 region_id,
'平台' region_name,
'IROAM*AUD' file_type,
'下发账务IROAM日汇总AUD文件' busi_name,
file_name,
indb_time,
0 morethan12h_filenum
from
info_jt_sr_40200010
where
file_name like 'IROAM%AUD'
and busi_class in ('65020050')
and model_id in (24,25,28) 
and begin_datetime >= to_timestamp(&source_begin_date,'yyyymmddhh24miss')
and begin_datetime <= to_timestamp(&source_end_date,'yyyymmddhh24miss')   
union all 
select
1 region_id,
'平台' region_name,
'CD*CHNX*' file_type,
'香港和记' busi_name,
file_name,
indb_time,
0 morethan12h_filenum
from
info_jt_sr_40200010
where
file_name like 'CD%CHNX%'
and busi_class in ('63020021')
and model_id in (24,25,28) 
and begin_datetime >= to_timestamp(&source_begin_date,'yyyymmddhh24miss')
and begin_datetime <= to_timestamp(&source_end_date,'yyyymmddhh24miss')     
  ) r
  group by 1,2,3,4
    """
    rule_b = """
            KPI名称：和记0文件告警
            公式：case when 列3(业务名称) ='和记业务文件' then 列4(文件数量) else '96' end ='0'
            字段映射：
            prov   区域
            class_name    文件类型
            class_name_cn   业务名称
            file_num    文件数量
            busi_class_conf   busiID
            稽核SQL：c_jt_guojiqingsuan_20231120_6001
SELECT
	CASE
		WHEN
			busi_class = 65020041 THEN
				63020013 
				WHEN file_name LIKE'SH%' THEN
				40010031 ELSE busi_class 
			END busi_class,
	COUNT ( * ) file_num 
FROM
	info_jt_sr_40200010 
WHERE
	busi_class IN ( 65020061, 65010415, 63020013, 65020041, 65100137, 63020022, 61050011 ) 
	AND model_id IN ( 24, 25 ) 
	and begin_datetime >=to_timestamp( &source_begin_date::varchar, 'yyyymmddhh24miss' )
	and begin_datetime <=to_timestamp(  &source_end_date::varchar, 'yyyymmddhh24miss' )
GROUP BY
CASE
		WHEN busi_class = 65020041 THEN
		63020013 
		WHEN file_name LIKE'SH%' THEN
		40010031 ELSE busi_class 
	END 
	UNION ALL
SELECT
CASE
		
	WHEN
		file_name LIKE'CDHKGTNCHNVT%' THEN
			65100143 ELSE busi_class 
		END busi_Class,
	COUNT ( file_name ) 
FROM
	info_jt_sr_40200010 
WHERE
	busi_class IN ( 65100142 ) 
	AND model_id = 25 
		and begin_datetime >=to_timestamp( &source_begin_date::varchar, 'yyyymmddhh24miss' )
	and begin_datetime <=to_timestamp(  &source_end_date::varchar, 'yyyymmddhh24miss' )
GROUP BY
CASE
		
		WHEN file_name LIKE'CDHKGTNCHNVT%' THEN
		65100143 ELSE busi_class 
	END 
	UNION ALL
SELECT
	63020021,
	COUNT ( file_name ) 
FROM
	info_jt_sr_40200010 
WHERE
	busi_class IN ( 63020021, 63020022 ) 
	AND model_id = 25 
	and begin_datetime >=to_timestamp( &source_begin_date::varchar, 'yyyymmddhh24miss' )
	and begin_datetime <=to_timestamp(  &source_end_date::varchar, 'yyyymmddhh24miss' )

c_jt_guojiqingsuan_20231120_1001表
select
	*
from
	(
		values ( 65020061,'CTISS','国际固网业务送国际公司文件' ),
		( 65010415,'innsms','国际固网短信业务接收文件' ),
		( 61050011,'GZ','国际固网语音业务接收文件(广州)' ),
		( 40010031,'SH','国际固网语音业务接收文件(上海)' ),
		( 63020013,'MS','来访短信业务' ),
		( 65100137,'CDCHNDXHKGCG','下发国际公司TAP文件' ),
		( 63020022,'CD%MVNCT','老前海卡业务文件' ),
		( 65100142,'CDHKGCGCHNVT','新前海卡HKGCG业务文件' ),
		( 65100143,'CDHKGTNCHNVT','新前海卡HKGTN业务文件' ),
		( 63020021,'和记5类文件','和记业务文件' ) 
	) as NAMES ( busi_class_conf,	class_name,	class_name_cn )
预处理SQL
select '平台' prov,c_jt_guojiqingsuan_20231120_1001.class_name,c_jt_guojiqingsuan_20231120_1001.class_name_cn ,  COALESCE ( c_jt_guojiqingsuan_20231120_6001.file_num,0 ) file_num,CASE WHEN c_jt_guojiqingsuan_20231120_1001.busi_class_conf = 40010031 THEN '61050011' WHEN c_jt_guojiqingsuan_20231120_1001.busi_class_conf = 63020013 THEN  '65020041,63020013' ELSE c_jt_guojiqingsuan_20231120_1001.busi_class_conf || '' END busi_class_conf  from  c_jt_guojiqingsuan_20231120_1001 左连接 c_jt_guojiqingsuan_20231120_6001 on c_jt_guojiqingsuan_20231120_1001.busi_class_conf = c_jt_guojiqingsuan_20231120_6001.busi_class   where 1=1 
  """
    prompt = f"""
            【角色设定】
            你是一位专业的数据稽核专家。你的目标是发现“业务逻辑重复”的告警稽核规则。
            【任务背景】
            用户需要对两个不同的稽核规则进行“查重”分析。目的是判断这两个规则是否在业务定义、计算逻辑或底层实现上存在重复或高度相似的情况，以便进行规则合并或优化。
            【输入数据】
            两组数据（规则A 和 规则B），每组数据包含：
            公式：指标的计算逻辑描述（如文本或数学公式）。
            字段映射：公式中的字段与sql中的字段映射关系。
            稽核SQL：实际执行的SQL代码片段，即公式中字段的取值逻辑。
            规则A: {rule_a}
            规则B: {rule_b}
            【分析维度与处理逻辑】
            你需要分别从以下二个维度进行深度比对，并给出0-100的相似度评分（0代表完全无关，100代表完全一致）：
            分为3档：高度相似 70-100 / 中度相似 50-69 / 低度相似 0-49
            一、公式维度
            抽象思维：提取两者主干逻辑，忽略干扰分支，排除不可能触发的分支
            核心判断：运用归一化思维，透过字面差异识别本质，深度分析公式理解公式的数学和业务含义，确定公式的最终目的或结果在逻辑上是否一致（高度一致时不得低于70分）。
            二、公式字段维度
            字段级血缘分析：提取公式中用到的每一个字段。在SQL中定位这些字段的来源（下钻分析最终的结果数据集是否一致）。
            忽略噪音：忽略SQL的结构和语法差异，忽略与核心公式字段无关的排序、展示字段。只关注公式依赖字段所在的那张表或子查询。忽略SQL中其他无关的关联表（JOIN）或无关的过滤条件（WHERE）。
            核心判断：判断两者在字段来源、过滤条件和条件值、统计逻辑上的差异（高度一致时不得低于70分）
            【约束条件】
            评分必须客观公正，避免过度联想。公式和字段两个维度需要作为一个整体来分析，因为公式的运算结果依赖于字段的取值。
            【输出格式】
            请严格按照以下Markdown格式输出分析报告：
            ## 稽核规则相似度分析报告
            ### 详细分析过程
            - 公式逻辑分析：
            [深度思考，然后详细解释为什么给这个分数]
            - 公式字段分析：
            [深度思考，然后详细解释为什么给这个分数]
            ### 评估结果
            | 评估维度 | 相似度评分 (0-100) | 判定结论 |
            | :--- | :--- | :--- |
            | 计算公式 | [分数] | [高度相似 / 中度相似 / 低度相似] |
            | 公式字段 | [分数] | [高度相似 / 中度相似 / 低度相似] |
            | 综合分析 | [平均分] | [建议合并 / 需人工复核 / 建议保留] |
            ### 总结建议
            [根据分析和评估结果给出总结建议]
    """
    model = LocalLLMComponent(inputs=[
        TextInput(name='query', display_name='Text', value=''),
        TextInput(name='assistant_code', display_name="助手编码", value='BSS-BASE-QM'),
        FloatInput(name='temperature', display_name='Temperature', value=0.1),
        TextInput(name='prompt', display_name='Prompt', value=prompt),
        TextInput(name='model_name', display_name='Model name', value=LLM_MODELS[0]),
    ])
    model.set_context({})
    try:
        result = await model.run(state={"query": query})
        print('\n')
        print(result.get('answer'))
    except BaseException as e:
        print(f"大模型调用失败: {e}")
