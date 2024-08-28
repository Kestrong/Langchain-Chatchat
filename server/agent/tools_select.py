from typing import Optional, Type

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Extra

_TOOLS_REGISTRY = {}


def get_tools(tool_name: str = None):
    if tool_name:
        return [_TOOLS_REGISTRY[tool_name]] if tool_name in _TOOLS_REGISTRY else []
    return [t for t in _TOOLS_REGISTRY.values()]


def get_tool_names(tool_name: str = None):
    if tool_name:
        return [tool_name] if tool_name in _TOOLS_REGISTRY else []
    return [t for t in _TOOLS_REGISTRY.keys()]


StructuredTool.Config.extra = Extra.allow


def register_tool(
        title: str = "",
        description: str = "",
        return_direct: bool = False,
        args_schema: Optional[Type[BaseModel]] = None,
        infer_schema: bool = True,
):
    def decorator(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        t = StructuredTool.from_function(func=func, name=func.__name__,
                                         description=description,
                                         args_schema=args_schema, return_direct=return_direct,
                                         infer_schema=infer_schema)
        t.title = title
        _TOOLS_REGISTRY[t.name] = t
        return wrapper

    return decorator
