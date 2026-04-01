import re
from copy import deepcopy
from typing import Dict, Any, Union

import shortuuid
from pydantic import BaseModel, Field

from server.memory.message_i18n import i18n_property
from server.workflow.utils.inputs import InputTypes, InputTypesMap
from server.workflow.utils.outputs import OutputTypes, OutputTypesMap

EXPR_PATTERN = re.compile(r'\{\{(\s*[\w-]+\.(inputs|outputs)\.[\w.]+\s*)}}')


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
        self.display_name = i18n_property(self.display_name)
        self.tag = i18n_property(self.tag)
        self.description = i18n_property(self.description)
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

    def parse_expr(self, value):
        if not value or not isinstance(value, str):
            return value

        matches = EXPR_PATTERN.findall(value)
        if not matches:
            return value

        context = self.get_context()
        unique_matches = set(match[0] for match in matches)

        for var_path in unique_matches:
            try:
                # 使用安全的路径访问函数
                var_val = self._get_nested_value(context, var_path)
                if var_val is not None:
                    original_placeholder = f'{{{{{var_path}}}}}'
                    # 使用字符串替换
                    value = value.replace(original_placeholder, str(var_val))
            except Exception:
                continue

        return value

    def _get_nested_value(self, obj, path):
        """安全获取嵌套字典值"""
        parts = path.split('.')
        current = obj

        for part in parts:
            if isinstance(current, dict):
                part_strip = part.strip()
                if part_strip in current:
                    current = current.get(part_strip)
                    if current is None:
                        return ''
                else:
                    return None
            else:
                return None

        return current

    def prepare_input(self, inputs: Dict[str, Any]):
        if self.inputs:
            for i in self.inputs:
                if not i.enable_expr:
                    continue
                if isinstance(i.value, dict):
                    i.value = {k: self.parse_expr(v) for k, v in i.value.items()}
                elif isinstance(i.value, list):
                    i.value = [self.parse_expr(v) for v in i.value]
                else:
                    i.value = self.parse_expr(i.value)

    def update_input_context(self):
        inputs = {}
        self.get_context().setdefault(self.id, {})
        if self.inputs:
            for i in self.inputs:
                inputs[i.name] = i.value
        self.get_context()[self.id]["inputs"] = inputs

    def prepare_output(self, outputs: Dict[str, Any]):
        if self.outputs:
            for i in self.outputs:
                if not i.enable_expr:
                    i.value = outputs.get(i.name)
                    continue
                if isinstance(i.value, dict):
                    i.value = {k: self.parse_expr(v) for k, v in i.value.items()}
                elif isinstance(i.value, list):
                    i.value = [self.parse_expr(v) for v in i.value]
                elif isinstance(i.value, str):
                    i.value = self.parse_expr(i.value)
                else:
                    i.value = outputs.get(i.name)

    def update_output_context(self):
        outputs = {}
        self.get_context().setdefault(self.id, {})
        if self.outputs:
            for i in self.outputs:
                outputs[i.name] = i.value
        self.get_context()[self.id]["outputs"] = outputs

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        self.prepare_input(state)
        self.update_input_context()
        result = await self._run(state)
        self.prepare_output(result)
        self.update_output_context()
        return self.get_context()[self.id]["outputs"]

    async def _run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError(f"not implemented run method for {self.name} component")

    def get_context(self):
        return self._context

    def set_context(self, value):
        self._context = value
