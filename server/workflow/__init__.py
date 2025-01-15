from itertools import groupby

from server.workflow.component.base.component import Component
from server.workflow.component.condition.condition import IfElseComponent
from server.workflow.component.inputs.chat_input import ChatInputComponent
from server.workflow.component.models.local_llm import LocalLLMComponent
from server.workflow.component.outputs.chat_output import ChatOutputComponent
from server.workflow.component.tools.code import PythonREPLComponent
from server.workflow.component.tools.http_caller import HttpCallerComponent
from server.workflow.component.tools.json_formatter import JsonFormatterComponent
from server.workflow.utils.inputs import *
from server.workflow.utils.outputs import *

components = {key: list(group) for key, group in
              groupby([IfElseComponent(), ChatInputComponent(), ChatOutputComponent(), LocalLLMComponent(),
                       PythonREPLComponent(), HttpCallerComponent(), JsonFormatterComponent()], key=lambda x: x.tag)}

if __name__ == '__main__':
    import json
    from fastapi.encoders import jsonable_encoder

    print(json.dumps(jsonable_encoder(components)))
