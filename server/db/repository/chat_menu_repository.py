from sqlalchemy import func

from server.db.models.chat_menu_model import ChatMenuModel
from server.db.session import with_session
from server.memory.token_info_memory import get_token_info


@with_session
def add_menu_to_db(session, menu_name: str, menu_icon: str, url: str, auth_level: int, enabled: str, sort_id: int):
    c = ChatMenuModel(menu_name=menu_name, menu_icon=menu_icon, url=url, auth_level=auth_level, enabled=enabled,
                      create_by=get_token_info().get("userId"), sort_id=sort_id)
    session.add(c)
    session.flush()
    return c.id


@with_session
def update_menu_to_db(session, menu_id: int, menu_name: str, menu_icon: str, url: str, auth_level: int, enabled: str,
                      sort_id: int):
    menu: ChatMenuModel = session.query(ChatMenuModel).filter(ChatMenuModel.id == menu_id).first()
    if menu is not None:
        menu.menu_name = menu_name
        menu.menu_icon = menu_icon
        menu.url = url
        menu.auth_level = auth_level
        menu.enabled = enabled
        menu.sort_id = sort_id
    else:
        raise ValueError("ChatMenu with id {} does not exist".format(menu))
    return menu.id


@with_session
def delete_menu_from_db(session, menu_id: int):
    session.query(ChatMenuModel).filter(ChatMenuModel.id == menu_id).delete()
    return menu_id


@with_session
def get_menu_from_db(session, page: int = 1, size: int = 10, keyword: str = None):
    page_size = abs(size)
    page_num = max(page, 1)
    offset = (page_num - 1) * page_size
    filters = []
    userId = get_token_info().get("userId")
    auth_level = 0
    if userId and str(userId) == '1':
        auth_level = 1
    filters.append(ChatMenuModel.auth_level <= auth_level)
    if keyword is not None and keyword.strip() != '':
        filters.append(ChatMenuModel.menu_name.ilike('%{}%'.format(keyword)))
    menus = (session.query(ChatMenuModel).filter(*filters).order_by(ChatMenuModel.sort_id.asc()).offset(offset)
             .limit(page_size).all())
    total = session.query(func.count(ChatMenuModel.id)).filter(*filters).scalar()
    data = []
    for c in menus:
        data.append(c.dict())
    return data, total


@with_session
def get_menu_detail_from_db(session, menu_id: int):
    filters = []
    userId = get_token_info().get("userId")
    auth_level = 0
    if userId and str(userId) == '1':
        auth_level = 1
    filters.append(ChatMenuModel.auth_level <= auth_level)
    filters.append(ChatMenuModel.id == menu_id)
    menu: ChatMenuModel = session.query(ChatMenuModel).filter(*filters).first()
    if menu is None:
        return None
    data = menu.dict()
    return data
