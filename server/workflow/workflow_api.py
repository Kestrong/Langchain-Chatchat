from fastapi import Query

from server.memory.message_i18n import Message_I18N
from server.utils import BaseResponse
from server.workflow import components


def get_components() -> BaseResponse:
    return BaseResponse(code=200, data=components())


def construct_component(component_type: str = Query("", description="组件类型")) -> BaseResponse:
    if not component_type:
        return BaseResponse(code=500, msg=Message_I18N.API_PARAM_NOT_PRESENT.value.format(name="component_type"))
    component_types = {c.__class__.__name__: type(c) for cc in components().values() for c in cc}
    if component_type not in component_types:
        return BaseResponse(code=500,
                            msg=Message_I18N.API_COMPONENT_NOT_FOUND.value.format(component_type=component_type))
    return BaseResponse(code=200, data=component_types[component_type]())
