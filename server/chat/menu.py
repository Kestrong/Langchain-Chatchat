from fastapi import Body, Query

from configs.basic_config import logger, log_verbose
from server.db.repository.chat_menu_repository import add_menu_to_db, update_menu_to_db, \
    delete_menu_from_db, get_menu_from_db, get_menu_detail_from_db
from server.utils import BaseResponse


def create_menu(menu_icon: str = Body(None, description="菜单图标"),
                menu_name: str = Body(description="菜单名称"),
                url: str = Body(None, description="菜单地址"),
                auth_level: int = Body(0, description="权限级别：0所有人可见、1管理员可见"),
                enabled: str = Body("0BT", description="是否启用：0BT是、0BF否"),
                sort_id: int = Body(0, description="排序顺序,值越小越靠前"), ) -> BaseResponse:
    try:
        menu_id = add_menu_to_db(menu_icon=menu_icon, menu_name=menu_name, url=url, auth_level=auth_level,
                                 enabled=enabled, sort_id=sort_id)
    except Exception as e:
        msg = f"创建菜单出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)
    return BaseResponse(code=200, data={'menu_id': menu_id})


def update_menu(id: int = Body(description="菜单id"),
                menu_icon: str = Body(None, description="菜单图标"),
                menu_name: str = Body(description="菜单名称"),
                url: str = Body(None, description="菜单地址"),
                auth_level: int = Body(0, description="权限级别：0所有人可见、1管理员可见"),
                enabled: str = Body("0BT", description="是否启用：0BT是、0BF否"),
                sort_id: int = Body(0, description="排序顺序,值越小越靠前")) -> BaseResponse:
    try:
        menu_id = update_menu_to_db(menu_id=id, menu_icon=menu_icon, menu_name=menu_name, url=url,
                                    auth_level=auth_level, enabled=enabled, sort_id=sort_id)
    except Exception as e:
        msg = f"修改菜单出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)
    return BaseResponse(code=200, data={'menu_id': menu_id})


def delete_menu(id: int = Query(description="菜单id")) -> BaseResponse:
    try:
        menu_id = delete_menu_from_db(menu_id=id)
    except Exception as e:
        msg = f"删除菜单出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)
    return BaseResponse(code=200, data={'menu_id': menu_id})


def get_menus(page: int = Query(default=1, description="页码"),
              size: int = Query(default=10, description="分页大小"),
              keyword: str = Query(default=None, description="关键字搜索")) -> BaseResponse:
    menus, total = get_menu_from_db(page=page, size=size, keyword=keyword)
    return BaseResponse(code=200, data={'menus': menus, 'total': total})


def get_menu_detail(id: int = Query(description="菜单id")) -> BaseResponse:
    menu = get_menu_detail_from_db(menu_id=id)
    return BaseResponse(code=200, data={'menu': menu})
