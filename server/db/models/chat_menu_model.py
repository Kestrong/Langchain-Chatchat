from sqlalchemy import Column, String, DateTime, func, Text, Integer

from server.db.base import Base


class ChatMenuModel(Base):
    """
    菜单模型
    """
    __tablename__ = 'chat_menu'
    id = Column(Integer, primary_key=True, autoincrement=True, comment='菜单ID')
    menu_name = Column(String(64), default=None, comment='中文菜单名称')
    menu_name_en = Column(String(64), default=None, comment='英文菜单名称')
    menu_icon = Column(Text, default=None, comment='菜单图标')
    url = Column(String(256), comment='菜单地址')
    open_type = Column(String(16), default='router', server_default='router', comment='嵌入方式：router、iframe')
    component_url = Column(String(256), default=None, comment='iframe嵌入地址')
    auth_level = Column(Integer, default=0, server_default='0', comment='权限级别：0所有人可见、1管理员可见')
    auth_users = Column(String(512), comment='授权用户id')
    enabled = Column(String(4), default='0BT', server_default='0BT', comment='是否启用：0BT是、0BF否')
    create_time = Column(DateTime, default=func.now(), server_default=func.now(), comment='创建时间')
    create_by = Column(String(64), comment='创建人id')
    sort_id = Column(Integer, default=0, server_default='0', comment='排序顺序,值越小越靠前')

    def __repr__(self):
        return f"<chat_menu(id='{self.id}', menu_name='{self.menu_name}', menu_name_en='{self.menu_name_en}', menu_icon='{self.menu_icon}', url='{self.url}', open_type='{self.open_type}', component_url='{self.component_url}', auth_level='{self.auth_level}', auth_users='{self.auth_users}', enabled='{self.enabled}', create_time='{self.create_time}', create_by='{self.create_by}', sort_id='{self.sort_id}')>"

    def dict(self):
        return {
            "id": self.id,
            "menu_name": self.menu_name,
            "menu_name_en": self.menu_name_en,
            "menu_icon": self.menu_icon,
            "url": self.url,
            "open_type": self.open_type,
            "component_url": self.component_url,
            "auth_level": self.auth_level,
            "auth_users": self.auth_users,
            "enabled": self.enabled,
            "create_by": self.create_by,
            "create_time": self.create_time,
            "sort_id": self.sort_id
        }
