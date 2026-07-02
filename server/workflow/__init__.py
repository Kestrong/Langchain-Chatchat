from collections import defaultdict

from server.workflow.component.base.component import Component
from server.workflow.component.condition.condition import IfElseComponent
from server.workflow.component.inputs.chat_input import ChatInputComponent
from server.workflow.component.models.local_llm import LocalLLMComponent
from server.workflow.component.outputs.chat_output import ChatOutputComponent
from server.workflow.component.outputs.chat_structure_output import ChatStructureOutputComponent
from server.workflow.component.tools.code import PythonREPLComponent
from server.workflow.component.tools.document_extractor import DocumentExtractorComponent
from server.workflow.component.tools.http_caller import HttpCallerComponent
from server.workflow.component.tools.json_formatter import JsonFormatterComponent
from server.workflow.component.tools.knowledge_retrieval import KnowledgeRetrievalComponent
from server.workflow.utils.inputs import *
from server.workflow.utils.outputs import *

ALL_COMPONENT_CLASSES: List[type] = [
    IfElseComponent,
    ChatInputComponent,
    ChatOutputComponent,
    ChatStructureOutputComponent,
    LocalLLMComponent,
    PythonREPLComponent,
    HttpCallerComponent,
    JsonFormatterComponent,
    KnowledgeRetrievalComponent,
    DocumentExtractorComponent,
]

ALL_COMPONENT_CLASSES_MAP = {cls.__name__: cls for cls in ALL_COMPONENT_CLASSES}


def _init_component(comp: Component) -> Component:
    """
    统一初始化组件及其输入/输出的 ID。
    将嵌套循环抽离为独立函数，提升主逻辑可读性。
    """
    comp.id = comp.name
    if comp.inputs:
        for inp in comp.inputs:
            inp.id = inp.name
    if comp.outputs:
        for out in comp.outputs:
            out.id = out.name
    return comp


def components() -> Dict[str, List[Component]]:
    """
    获取按 tag 分组的组件映射。
    """
    component_map = defaultdict(list)

    for comp_cls in ALL_COMPONENT_CLASSES:
        comp = _init_component(comp_cls())
        component_map[comp.tag].append(comp)

    return dict(component_map)


if __name__ == '__main__':
    import json
    from fastapi.encoders import jsonable_encoder

    print(json.dumps(jsonable_encoder(components())))
