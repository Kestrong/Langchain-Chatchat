import copy
from typing import Optional, Type, Callable, Union, Dict, Any, Tuple

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Extra, Field, create_model

from server.utils import get_tool_config

_TOOLS_REGISTRY = {}


def clear_values(d: dict):
    for key, value in d.items():
        if isinstance(value, dict):
            clear_values(value)
        elif isinstance(value, list):
            if len(value) == 0 or not isinstance(value[0], dict):
                d[key] = []
            else:
                for v in value:
                    clear_values(v)
        else:
            d[key] = None


def get_tools_info():
    tool_config_template = copy.deepcopy(get_tool_config().TOOL_CONFIG)
    clear_values(tool_config_template)

    description_format = lambda description: description.split(" - ")[
        1].strip() if description and " - " in description else description
    return {"tools_info": [
        {"name": t.name, "title": t.title, "description": description_format(t.description), "parameters": t.args}
        for t in
        _TOOLS_REGISTRY.values()], "tool_config_template": tool_config_template}


def create_dynamic_tool(api: dict, func: Callable):
    def create_field(name, field_schema: dict):
        if field_schema.get("parameters", {}):
            return create_dynamic_model(name, field_schema["parameters"])
        else:
            return (type(field_schema.get("type")), Field(description=field_schema.get("description")))

    def create_dynamic_model(model_name, api: {}):
        fields = {}
        for name, field in api.get("parameters", {}).items():
            fields[name] = create_field(name, field)
        return create_model(model_name + 'DynamicModel', **fields)

    def func_wrapper(**kwargs: Any):
        return func(api_info=api, args=kwargs)

    args_schema = create_dynamic_model(api.get("name"), api)
    t = StructuredTool.from_function(func=func_wrapper, name=api.get("name"),
                                     description=api.get("description"), return_direct=api.get("return_direct", True),
                                     args_schema=args_schema, infer_schema=False)
    t.title = api.get("title") or t.name
    return t


def get_tool(tool_name: str):
    return _TOOLS_REGISTRY[tool_name] if tool_name in _TOOLS_REGISTRY else None


def get_all_tools():
    return [t for t in _TOOLS_REGISTRY.values()]


StructuredTool.Config.extra = Extra.allow


def _new_parse_input(
        self,
        tool_input: Union[str, Dict],
) -> Union[str, Dict[str, Any]]:
    """Convert tool input to pydantic model."""
    input_args = self.args_schema
    if isinstance(tool_input, str):
        if input_args is not None:
            key_ = next(iter(input_args.__fields__.keys()))
            input_args.validate({key_: tool_input})
        return tool_input
    else:
        if input_args is not None:
            result = input_args.parse_obj(tool_input)
            return result.dict()


def _new_to_args_and_kwargs(self, tool_input: Union[str, Dict]) -> Tuple[Tuple, Dict]:
    # For backwards compatibility, if run_input is a string,
    # pass as a positional argument.
    if isinstance(tool_input, str):
        return (tool_input,), {}
    else:
        # for tool defined with `*args` parameters
        # the args_schema has a field named `args`
        # it should be expanded to actual *args
        # e.g.: test_tools
        #       .test_named_tool_decorator_return_direct
        #       .search_api
        if "args" in tool_input:
            args = tool_input["args"]
            if args is None:
                tool_input.pop("args")
                return (), tool_input
            elif isinstance(args, tuple):
                tool_input.pop("args")
                return args, tool_input
        return (), tool_input


StructuredTool._parse_input = _new_parse_input
StructuredTool._to_args_and_kwargs = _new_to_args_and_kwargs


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

        _return_direct = get_tool_config().TOOL_CONFIG.get(func.__name__, {}).get("return_direct", return_direct)
        t = StructuredTool.from_function(func=func, name=func.__name__,
                                         description=description,
                                         args_schema=args_schema, return_direct=_return_direct,
                                         infer_schema=infer_schema)
        t.title = title
        enable_tools = get_tool_config().ENABLE_TOOLS
        if enable_tools:
            if t.name in enable_tools:
                _TOOLS_REGISTRY[t.name] = t
        else:
            _TOOLS_REGISTRY[t.name] = t
        return wrapper

    return decorator
