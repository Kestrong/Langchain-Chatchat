from typing import Dict, Type, Any, Union

import shortuuid
from pydantic import BaseModel

from server.workflow.utils.inputs import FieldTypes


class Output(BaseModel):
    id: str = None
    name: str
    display_name: str

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self.id = self.name + "-" + shortuuid.random(length=6)

    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        d['type'] = self.__class__.__name__
        return d

    def json(self, *args, **kwargs):
        # 确保调用的是我们自定义的 dict 方法
        return super().json(*args, **kwargs)


class TextOutput(Output):
    field_type: FieldTypes = FieldTypes.TEXT
    value: Union[str, None]


class DictOutput(Output):
    field_type: FieldTypes = FieldTypes.DICT
    value: Union[Dict[str, Any], None] = {}


class ListOutput(Output):
    field_type: FieldTypes = FieldTypes.LIST
    value: Union[str, None]


class BooleanOutput(Output):
    field_type: FieldTypes = FieldTypes.BOOLEAN
    value: Union[bool, None]


OutputTypes = [TextOutput, DictOutput, ListOutput, BooleanOutput]
OutputTypesMap: Dict[str, Type] = {i.__name__: i for i in OutputTypes}
