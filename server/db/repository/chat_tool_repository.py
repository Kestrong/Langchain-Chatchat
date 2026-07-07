import re
from typing import List

from sqlalchemy import func, or_

from server.db.models.chat_tool_model import ChatToolModel
from server.db.session import with_session

# 定义正则表达式模式：仅允许字母、数字和下划线
_VALID_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]+$')


def _validate_tool_names(tool_name_en: str, function_name: str):
    """
    校验 tool_name_en 和 function_name 是否符合规范
    """
    if not _VALID_NAME_PATTERN.match(tool_name_en):
        raise ValueError("The tool_name_en must consist solely of letters, digits, and underscores.")

    if not _VALID_NAME_PATTERN.match(function_name):
        raise ValueError("The function_name must consist solely of letters, digits, and underscores.")


@with_session
def add_tool_to_db(session, tool_name: str, tool_name_en: str, tool_description: str, function_name: str,
                   function_properties: dict = None, function_source: str = None, tool_config: dict = None,
                   state: str = '0BT'):
    """
    添加工具到数据库
    """
    _validate_tool_names(tool_name_en, function_name)

    function_properties = function_properties or {}
    tool_config = tool_config or {}

    tool = ChatToolModel(
        tool_name=tool_name,
        tool_name_en=tool_name_en,
        tool_description=tool_description,
        function_name=function_name,
        function_properties=function_properties,
        function_source=function_source,
        tool_config=tool_config,
        state=state
    )
    session.add(tool)
    session.flush()
    return tool.id


@with_session
def update_tool_to_db(session, tool_id: int, tool_name: str, tool_name_en: str, tool_description: str,
                      function_name: str, function_properties: dict = None, function_source: str = None,
                      tool_config: dict = None, state: str = '0BT'):
    """
    更新数据库中的工具信息
    """
    _validate_tool_names(tool_name_en, function_name)

    tool: ChatToolModel = session.query(ChatToolModel).filter(ChatToolModel.id == tool_id).first()
    if tool is not None:
        tool.tool_name = tool_name
        tool.tool_name_en = tool_name_en
        tool.tool_description = tool_description
        tool.function_name = function_name
        tool.function_properties = function_properties or {}
        tool.function_source = function_source
        tool.tool_config = tool_config or {}
        tool.state = state
    else:
        raise ValueError("ChatTool with id {} does not exist".format(tool_id))
    return tool.id


@with_session
def delete_tool_from_db(session, tool_id: int):
    """
    从数据库中删除工具
    """
    session.query(ChatToolModel).filter(ChatToolModel.id == tool_id).delete()
    return tool_id


@with_session
def get_tool_from_db(session, page: int = 1, size: int = 10, keyword: str = None):
    """
    分页查询工具列表，支持关键词搜索
    """
    page_size = abs(size)
    page_num = max(page, 1)
    offset = (page_num - 1) * page_size

    filters = [ChatToolModel.state == '0BT']
    if keyword is not None and keyword.strip() != '':
        # 在中文名称和英文名称中进行模糊搜索
        filters.append(or_(
            ChatToolModel.tool_name.ilike('%{}%'.format(keyword)),
            ChatToolModel.tool_name_en.ilike('%{}%'.format(keyword))
        ))

    tools = (session.query(ChatToolModel)
             .filter(*filters)
             .offset(offset)
             .limit(page_size)
             .all())

    total = session.query(func.count(ChatToolModel.id)).filter(*filters).scalar()

    data = []
    for tool in tools:
        data.append(tool.dict())

    return data, total


@with_session
def get_tool_detail_from_db(session, tool_id: int):
    """
    获取工具详情
    """
    filters = [ChatToolModel.state == '0BT', ChatToolModel.id == tool_id]
    tool: ChatToolModel = session.query(ChatToolModel).filter(*filters).first()
    if tool is None:
        return None
    return tool.dict()


@with_session
def get_tool_by_name_en_from_db(session, tool_name_ens: List[str]):
    """
    根据英文名称获取工具信息
    """
    if not tool_name_ens:
        return []
    filters = [ChatToolModel.state == '0BT', ChatToolModel.tool_name_en.in_(tool_name_ens)]
    tools: List[ChatToolModel] = session.query(ChatToolModel).filter(*filters).all()
    if not tools:
        return []
    return [tool.dict() for tool in tools]
