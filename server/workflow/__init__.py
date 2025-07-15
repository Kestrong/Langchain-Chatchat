from itertools import groupby

from server.workflow.component.base.component import Component
from server.workflow.component.condition.condition import IfElseComponent
from server.workflow.component.inputs.chat_input import ChatInputComponent
from server.workflow.component.models.local_llm import LocalLLMComponent
from server.workflow.component.outputs.chat_output import ChatOutputComponent
from server.workflow.component.tools.code import PythonREPLComponent
from server.workflow.component.tools.document_extractor import DocumentExtractorComponent
from server.workflow.component.tools.http_caller import HttpCallerComponent
from server.workflow.component.tools.json_formatter import JsonFormatterComponent
from server.workflow.component.tools.knowledge_retrieval import KnowledgeRetrievalComponent
from server.workflow.utils.inputs import *
from server.workflow.utils.outputs import *


def components() -> dict:
    components = {key: list(group) for key, group in
                  groupby([IfElseComponent(), ChatInputComponent(), ChatOutputComponent(), LocalLLMComponent(),
                           PythonREPLComponent(), HttpCallerComponent(), JsonFormatterComponent(),
                           KnowledgeRetrievalComponent(), DocumentExtractorComponent()], key=lambda x: x.tag)}

    for cc in components.values():
        for c in cc:
            c.id = c.name
            if c.inputs:
                for i in c.inputs:
                    i.id = i.name
            if c.outputs:
                for o in c.outputs:
                    o.id = o.name
    return components


if __name__ == '__main__':
    import json
    from fastapi.encoders import jsonable_encoder

    print(json.dumps(jsonable_encoder(components())))
