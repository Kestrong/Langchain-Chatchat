import re
from copy import deepcopy
from typing import Dict, Any, Union

import shortuuid
from langchain_core.prompts.string import DEFAULT_FORMATTER_MAPPING
from pydantic import BaseModel, Field

from configs import logger
from server.workflow.utils.inputs import InputTypes, InputTypesMap
from server.workflow.utils.outputs import OutputTypes, OutputTypesMap


class Component(BaseModel):
    id: Union[str, None]
    name: str
    display_name: str
    description: str
    tag: Union[str, None]
    icon: Union[str, None]
    inputs: type(InputTypes) = []
    outputs: type(OutputTypes) = []
    _context: Dict = Field(default_factory=dict)

    class Config:
        underscore_attrs_are_private = True  # 这个配置可以让带有下划线的属性被视为私有属性

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.id is None:
            self.id = self.name + "-" + shortuuid.random(length=6)
        if self.inputs and isinstance(self.inputs[0], dict):
            inputs = []
            for i in self.inputs:
                type = InputTypesMap.get(i.get("type"))
                inputs.append(deepcopy(type(**i)))
            self.inputs = inputs
        if self.outputs and isinstance(self.outputs[0], dict):
            outputs = []
            for i in self.outputs:
                type = OutputTypesMap.get(i.get("type"))
                outputs.append(deepcopy(type(**i)))
            self.outputs = outputs

    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        d['type'] = self.__class__.__name__
        return d

    def json(self, *args, **kwargs):
        # 确保调用的是我们自定义的 dict 方法
        return super().json(*args, **kwargs)

    def prepare_input(self, inputs: Dict[str, Any]):
        if self.inputs:
            for i in self.inputs:
                if i.value and isinstance(i.value, str):
                    if i.value.startswith("{{") and i.value.endswith("}}"):
                        expr_value = self.get_expr_value(i.value)
                        i.value = expr_value
                    elif self.contains_variable_template(i.value):
                        i.value = self.parse_template(i.value)

    def update_input_context(self):
        inputs = {}
        self._context.setdefault(self.id, {})
        if self.inputs:
            for i in self.inputs:
                inputs[i.name] = i.value
        self._context[self.id]["inputs"] = inputs

    def parse_template(self, template: str):
        try:
            return DEFAULT_FORMATTER_MAPPING["jinja2"](template, **self._context)
        except Exception as e:
            logger.error(f"{e}")
            return template

    def get_expr_value(self, expr: str):
        expr = expr.lstrip("{{").rstrip("}}")
        parts = expr.split(".")
        params = self._context.get(parts[0].strip(), {}).get(parts[1].strip(), {})
        for p in parts[2:]:
            if not params:
                return None
            params = params.get(p.strip())
        return params

    def contains_variable_template(self, template: str):
        # 定义正则表达式模式，匹配{{任意字符}}
        pattern = r'\{\{[^}]+\}\}'
        match = re.search(pattern, template)
        return match is not None

    def prepare_output(self, outputs: Dict[str, Any]):
        if self.outputs:
            for i in self.outputs:
                if i.value and isinstance(i.value, str):
                    if i.value.startswith("{{") and i.value.endswith("}}"):
                        expr_value = self.get_expr_value(i.value)
                        i.value = expr_value
                    elif self.contains_variable_template(i.value):
                        i.value = self.parse_template(i.value)
                else:
                    i.value = outputs.get(i.name)

    def update_output_context(self):
        outputs = {}
        self._context.setdefault(self.id, {})
        if self.outputs:
            for i in self.outputs:
                outputs[i.name] = i.value
        self._context[self.id]["outputs"] = outputs

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        self.prepare_input(state)
        self.update_input_context()
        result = await self._run(state)
        self.prepare_output(result)
        self.update_output_context()
        return self._context[self.id]["outputs"]

    async def _run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError(f"not implemented run method for {self.name} component")

    def get_context(self):
        return self._context

    def set_context(self, value):
        self._context = value
