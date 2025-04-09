from enum import Enum
from typing import Dict, Type, Any, Union, List

import shortuuid
from pydantic import BaseModel


class FieldTypes(str, Enum):
    TEXT = "str"
    INTEGER = "int"
    PASSWORD = "str"
    FLOAT = "float"
    BOOLEAN = "bool"
    DICT = "dict"
    PROMPT = "prompt"
    CODE = "code"
    LIST = "list"


class Input(BaseModel):
    id: str = None
    name: str
    display_name: str
    required: bool = False
    enable_expr: bool = True
    info: Union[str, None]
    options: list = []

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.id is None:
            self.id = self.name + "-" + shortuuid.random(length=6)

    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        d['type'] = self.__class__.__name__
        return d

    def json(self, *args, **kwargs):
        # 确保调用的是我们自定义的 dict 方法
        return super().json(*args, **kwargs)


class TextInput(Input):
    field_type: FieldTypes = FieldTypes.TEXT
    value: Union[str, None]


class IntegerInput(Input):
    field_type: FieldTypes = FieldTypes.INTEGER
    value: Union[int, None]


class PasswordInput(Input):
    field_type: FieldTypes = FieldTypes.PASSWORD
    value: Union[str, None]


class FloatInput(Input):
    field_type: FieldTypes = FieldTypes.FLOAT
    value: Union[float, None]


class BooleanInput(Input):
    field_type: FieldTypes = FieldTypes.BOOLEAN
    value: Union[bool, None]


class DictInput(Input):
    field_type: FieldTypes = FieldTypes.DICT
    value: Union[Dict[str, Any], None] = {}


class ListInput(Input):
    field_type: FieldTypes = FieldTypes.LIST
    value: Union[List[Any], None] = []


class PromptInput(Input):
    field_type: FieldTypes = FieldTypes.PROMPT
    value: Union[str, None]


class CodeInput(Input):
    field_type: FieldTypes = FieldTypes.CODE
    value: Union[str, None]


InputTypes = [TextInput, IntegerInput, PasswordInput, FloatInput, BooleanInput, DictInput, ListInput, PromptInput,
              CodeInput]
InputTypesMap: Dict[str, Type] = {i.__name__: i for i in InputTypes}
