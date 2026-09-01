import copy
import functools
import inspect
import json
import sys
from typing import Optional, Type, Union, Dict, Any, Tuple, List, Callable

from fastapi import Body, Query
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Extra, Field, create_model

from configs.basic_config import logger, log_verbose
from server.db.repository import get_tool_by_name_en_from_db
from server.db.repository.chat_tool_repository import (
    add_tool_to_db,
    update_tool_to_db,
    delete_tool_from_db,
    get_tool_from_db,
    get_tool_detail_from_db,
)
from server.memory.message_i18n import Message_I18N
from server.utils import BaseResponse
from server.utils import get_tool_config


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


def parse_tool_info(tool_config_template, tools):
    description_format = lambda description: description.split(" - ")[
        1].strip() if description and " - " in description else description
    toos_info = [{"tool_name": t.title, "tool_name_en": t.name, "tool_description": description_format(t.description),
                  "function_name": t.func_or_co.__name__,
                  "function_properties": t.args_schema.schema_json(ensure_ascii=False),
                  "tool_config": tool_config_template.get(t.func_or_co.__name__, {})}
                 for t in tools]
    return toos_info


def built_in_tools() -> BaseResponse:
    tool_config_template = copy.deepcopy(get_tool_config().TOOL_CONFIG)
    clear_values(tool_config_template)
    toos_info = parse_tool_info(tool_config_template, _TOOLS_REGISTRY.values())
    return BaseResponse(code=200, data=toos_info)


async def child_tools(tool_name_en: str = Query(description="工具名称")) -> BaseResponse:
    child_tools, _ = await get_available_tools([tool_name_en])
    return BaseResponse(code=200, data=parse_tool_info({}, child_tools))


def create_tool(
        tool_name: str = Body(description="工具中文名称"),
        tool_name_en: str = Body(description="工具英文名称"),
        tool_description: str = Body(description="工具描述"),
        function_name: str = Body(description="工具调用的函数名称"),
        function_properties: dict = Body(None, description="函数的参数定义"),
        function_source: str = Body(None, description="函数源码"),
        tool_config: dict = Body(None, description="工具配置信息"),
        state: str = Body("0BT", description="状态：0BT启用，0BF禁用"),
) -> BaseResponse:
    """
    创建工具
    """
    try:
        tool_id = add_tool_to_db(
            tool_name=tool_name,
            tool_name_en=tool_name_en,
            tool_description=tool_description,
            function_name=function_name,
            function_properties=function_properties,
            function_source=function_source,
            tool_config=tool_config,
            state=state,
        )
    except Exception as e:
        msg = f"创建工具出错： {e}"
        logger.error(f"{e.__class__.__name__}: {msg}", exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_CREATE_ERROR.value)
    return BaseResponse(code=200, data={"tool_id": tool_id})


def update_tool(
        tool_id: int = Body(description="工具id"),
        tool_name: str = Body(description="工具中文名称"),
        tool_name_en: str = Body(description="工具英文名称"),
        tool_description: str = Body(description="工具描述"),
        function_name: str = Body(description="工具调用的函数名称"),
        function_properties: dict = Body(None, description="函数的参数定义"),
        function_source: str = Body(None, description="函数源码"),
        tool_config: dict = Body(None, description="工具配置信息"),
        state: str = Body("0BT", description="状态：0BT启用，0BF禁用"),
) -> BaseResponse:
    """
    更新工具
    """
    try:
        update_tool_to_db(
            tool_id=tool_id,
            tool_name=tool_name,
            tool_name_en=tool_name_en,
            tool_description=tool_description,
            function_name=function_name,
            function_properties=function_properties,
            function_source=function_source,
            tool_config=tool_config,
            state=state,
        )
    except Exception as e:
        msg = f"修改工具出错： {e}"
        logger.error(f"{e.__class__.__name__}: {msg}", exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_UPDATE_ERROR.value)
    return BaseResponse(code=200, data={"tool_id": tool_id})


def delete_tool(tool_id: int = Query(description="工具id")) -> BaseResponse:
    """
    删除工具
    """
    try:
        delete_tool_from_db(tool_id=tool_id)
    except Exception as e:
        msg = f"删除工具出错： {e}"
        logger.error(f"{e.__class__.__name__}: {msg}", exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_DELETE_ERROR.value)
    return BaseResponse(code=200, data={"tool_id": tool_id})


def get_tools(
        page: int = Query(default=1, description="页码"),
        size: int = Query(default=10, description="分页大小"),
        keyword: str = Query(default=None, description="关键字搜索"),
) -> BaseResponse:
    """
    分页查询工具列表
    """
    tools, total = get_tool_from_db(page=page, size=min(abs(size), 1000), keyword=keyword)
    return BaseResponse(code=200, data={"tools": tools, "total": total})


def get_tool_detail(tool_id: int = Query(description="工具id")) -> BaseResponse:
    """
    获取工具详情
    """
    tool = get_tool_detail_from_db(tool_id=tool_id)
    return BaseResponse(code=200, data={"tool": tool})


class CustomStructuredTool(StructuredTool):
    title: str = ""
    dynamic: bool = False

    @property
    def func_or_co(self):
        return self.func or self.coroutine

    def _to_args_and_kwargs(self, tool_input: Union[str, Dict]) -> Tuple[Tuple, Dict]:
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

    class Config:
        extra = Extra.allow


_TOOLS_REGISTRY: Dict[str, CustomStructuredTool] = {}
_FUNC_REGISTRY: Dict[str, Any] = {}

TYPE_MAP = {
    "string": str,
    "integer": int,
    "long": int,
    "number": float,
    "boolean": bool,
    "null": type(None),
    "any": Any,
}


def resolve_json_schema(field_schema: Dict[str, Any], model_name: str = "SubModel") -> Any:
    """
    递归解析 JSON Schema，将其转换为 Python 类型或嵌套的 Pydantic BaseModel。
    """
    if not isinstance(field_schema, dict):
        return Any

    json_type = field_schema.get("type")

    # 处理嵌套对象 (Object with properties)
    if json_type == "object" or "properties" in field_schema:
        properties = field_schema.get("properties", {})
        required_fields = set(field_schema.get("required", []))

        # 如果没有 properties，返回一个通用的字典类型
        if not properties:
            return Dict[str, Any]

        # 递归构建嵌套的动态模型
        return create_dynamic_model(model_name, properties, required_fields)

    # 处理数组 (Array)
    if json_type == "array":
        items_schema = field_schema.get("items", {})
        # 递归解析数组内部元素的类型
        inner_type = resolve_json_schema(items_schema, f"{model_name}Item")
        return List[inner_type]

    if json_type in TYPE_MAP:
        return TYPE_MAP[json_type]

    if "enum" in field_schema:
        # 简单处理：返回基础类型，实际业务中可转换为 Literal 或 Enum 类
        return TYPE_MAP.get(json_type, str)

    # 6. 未知类型兜底
    return Any


def create_dynamic_model(
        model_name: str,
        model_schema: Dict[str, Any],
        required_fields: Optional[set] = None
):
    """
    根据 JSON Schema 动态生成 Pydantic 模型。
    """
    if required_fields is None:
        required_fields = set()

    fields = {}
    for field_name, field_schema in model_schema.items():
        # 获取解析后的 Python 类型（可能是基础类型，也可能是嵌套的 BaseModel）
        python_type = resolve_json_schema(field_schema, model_name=field_name.capitalize())

        # 判断是否为必填项，如果不是必填项，将其设为 Optional 并赋予默认值 None
        if field_name not in required_fields:
            python_type = Optional[python_type]
            field_info = Field(default=None, description=field_schema.get("description"))
        else:
            field_info = Field(description=field_schema.get("description"))

        fields[field_name] = (python_type, field_info)

    # 使用 Pydantic 的 create_model 动态生成类
    return create_model(f"{model_name}DynamicModel", **fields)


def create_dynamic_tool(tool_config: dict, tool_name: str, tool_name_en: str, description: str, func_name: str,
                        function_source: str, func_properties: dict = None,
                        kwargs_collector: Callable = None) -> StructuredTool:
    built_in_func = _FUNC_REGISTRY.get(func_name)
    args_schema = None
    func = None
    if built_in_func:
        func = built_in_func
        built_in_tool = _TOOLS_REGISTRY.get(func_name)
        if not built_in_tool.dynamic:
            args_schema = built_in_tool.args_schema
    else:
        if function_source:
            from server.workflow.component.tools.python_repl import compile_dynamic_func
            func, _ = compile_dynamic_func(function_source, func_name)

    if not func:
        raise ValueError(f"Function {func_name} not found")
    if not args_schema:
        args_schema = create_dynamic_model(tool_name_en, func_properties.get("properties", {}),
                                           set(func_properties.get("required", [])))
    is_async, func_or_co = wrapper_func(tool_config, func, kwargs_collector)
    t = CustomStructuredTool.from_function(func=None if is_async else func_or_co,
                                           coroutine=func_or_co if is_async else None,
                                           name=tool_name_en,
                                           description=description,
                                           return_direct=tool_config.get("return_direct", True),
                                           args_schema=args_schema, infer_schema=False)
    t.title = tool_name or t.name
    return t


def get_candidate_tools(tool_name_ens: List[str]):
    tool_configs_in_file = copy.deepcopy(get_tool_config().TOOL_CONFIG)
    candidate_tools = []
    tool_config_map = {**tool_configs_in_file}
    if tool_name_ens:
        db_tools: List[dict] = get_tool_by_name_en_from_db(tool_name_ens=tool_name_ens)
        db_tool_map = {tool.get("tool_name_en"): tool for tool in db_tools}
        for tool_name_en in tool_name_ens:
            if tool_name_en in db_tool_map:
                tool = db_tool_map[tool_name_en]
                tool_config = tool.get("tool_config") or {}
                for key, value in tool_configs_in_file.get(tool.get("function_name"), {}).items():
                    if key not in tool_config:
                        tool_config[key] = value
                tool_config_map[tool.get("tool_name_en")] = tool_config
                try:
                    structured_tool = create_dynamic_tool(tool_config=tool_config,
                                                          tool_name=tool.get("tool_name"),
                                                          tool_name_en=tool.get("tool_name_en"),
                                                          description=tool.get("tool_description"),
                                                          func_name=tool.get("function_name"),
                                                          function_source=tool.get("function_source"),
                                                          func_properties=tool.get("function_properties")) or {}
                    candidate_tools.append(structured_tool)
                except Exception as e:
                    logger.error(f"Failed to create dynamic tool for {tool_name_en}: {e}")
            else:
                structured_tool = _TOOLS_REGISTRY.get(tool_name_en)
                if structured_tool:
                    candidate_tools.append(structured_tool)
    else:
        candidate_tools = [t for t in _TOOLS_REGISTRY.values()]

    return candidate_tools, tool_config_map


async def get_available_tools(tool_name_ens: List[str]):
    candidate_tools, tool_config_map = get_candidate_tools(tool_name_ens)

    available_tools = []
    for tool in candidate_tools:
        if tool.func_or_co.__name__ == "mcp":
            from server.agent.tools.mcp import mcp_async
            mcp_config = tool_config_map.get(tool.name)
            disable_tools = mcp_config.get('disable_tools')
            enable_tools = mcp_config.get('enable_tools')
            try:
                mcp_list_result = await mcp_async(tool_config=mcp_config, method="tools/list", params={})
                m_result = json.loads(mcp_list_result) or {}
                for mcp_tool in m_result.get("tools", []):
                    if enable_tools and mcp_tool.get("name") not in enable_tools:
                        continue
                    if disable_tools and mcp_tool.get("name") in disable_tools:
                        continue
                    mcp_tool_name = mcp_tool.get("name")
                    kwargs_collector = lambda x, name=mcp_tool_name: {"method": "tools/call",
                                                                      "params": {"name": name,
                                                                                 "arguments": x}}
                    structured_tool = create_dynamic_tool(tool_config=mcp_config,
                                                          tool_name=mcp_tool.get("title"),
                                                          tool_name_en=mcp_tool_name,
                                                          description=mcp_tool.get("tool_description"),
                                                          func_name=tool.func_or_co.__name__,
                                                          function_source='',
                                                          func_properties=mcp_tool.get("inputSchema", {}) or {},
                                                          kwargs_collector=kwargs_collector)
                    available_tools.append(structured_tool)
            except Exception as e:
                logger.error(f"Failed to create dynamic tool for {tool.name}: {e}")

        elif tool.func_or_co.__name__ == "http_request":
            http_config = tool_config_map.get(tool.name)
            apis = http_config.get('apis', [])
            for api in apis:
                try:
                    structured_tool = create_dynamic_tool(tool_config=api,
                                                          tool_name=api.get("title"),
                                                          tool_name_en=api.get("name"),
                                                          description=api.get("description"),
                                                          func_name=tool.func_or_co.__name__,
                                                          function_source='',
                                                          func_properties=api.get("inputSchema", {}) or {})
                    available_tools.append(structured_tool)
                except Exception as e:
                    logger.error(f"Failed to create dynamic tool for {api.get('name')}: {e}")
        else:
            available_tools.append(tool)

    return available_tools, tool_config_map


def get_all_tools():
    data, count = get_tool_from_db(size=sys.maxsize)
    tool_name_ens = set()
    for tool in data:
        tool_name_ens.add(tool.get("tool_name_en"))
    for name in _TOOLS_REGISTRY.keys():
        tool_name_ens.add(name)
    return get_candidate_tools(tool_name_ens=list(tool_name_ens))


def wrapper_func(tool_config: dict, func, kwargs_collector: Callable = None):
    """
    智能包装器：自动识别同步/异步函数，并安全注入 tool_config。
    """
    is_async = inspect.iscoroutinefunction(func)

    need_inject = False
    try:
        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        if params:
            first_param = params[0]
            # 判断第一个参数是否为 tool_config: dict
            if first_param.name == "tool_config" and first_param.annotation == dict:
                need_inject = True
    except (ValueError, TypeError):
        # 如果动态生成的函数无法提取签名，默认不注入，避免崩溃
        pass

    # 根据同步/异步生成对应的包装器
    if need_inject:
        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                kwargs.pop("tool_config", None)
                if kwargs_collector:
                    kwargs = kwargs_collector(kwargs)
                return await func(tool_config, *args, **kwargs)

            return is_async, async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                kwargs.pop("tool_config", None)
                if kwargs_collector:
                    kwargs = kwargs_collector(kwargs)
                return func(tool_config, *args, **kwargs)

            return is_async, sync_wrapper
    else:
        # 如果不需要注入，直接返回原函数
        return is_async, func


def register_tool(
        title: str = "",
        description: str = "",
        return_direct: bool = False,
        args_schema: Optional[Type[BaseModel]] = None,
        infer_schema: bool = True,
        dynamic: bool = False
):
    def decorator(func):
        tool_name = func.__name__
        tool_configs_module = get_tool_config()
        is_async, target_func = wrapper_func(tool_config=tool_configs_module.TOOL_CONFIG.get(tool_name, {}), func=func)

        _return_direct = tool_configs_module.TOOL_CONFIG.get(tool_name, {}).get("return_direct") or return_direct
        t = CustomStructuredTool.from_function(func=None if is_async else target_func,
                                               coroutine=target_func if is_async else None,
                                               name=tool_name,
                                               description=description,
                                               args_schema=args_schema, return_direct=_return_direct,
                                               infer_schema=infer_schema)
        t.dynamic = dynamic
        t.title = title
        enable_tools = tool_configs_module.ENABLE_TOOLS
        if enable_tools:
            if t.name in enable_tools:
                _TOOLS_REGISTRY[t.name] = t
        else:
            _TOOLS_REGISTRY[t.name] = t
        _FUNC_REGISTRY[func.__name__] = func

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator
