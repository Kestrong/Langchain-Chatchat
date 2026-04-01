from sqlalchemy import Column, Integer, String, Index

from server.db.base import Base


class ChatDictModel(Base):
    """
    字典表
    """
    __tablename__ = 'chat_dict'
    __table_args__ = (Index('idx_dict_type_value', 'dict_type', 'dict_value', unique=True),)
    id = Column(Integer, primary_key=True, autoincrement=True, comment='助手ID')
    dict_type = Column(String(64), default=None, comment='字典类型')
    dict_value = Column(String(512), default=None, comment='字典值')
    dict_name = Column(String(64), default=None, comment='字典英文名称')
    dict_name_cn = Column(String(64), default=None, comment='字典中文名称')
    sort_id = Column(Integer, default=0, server_default='0', comment='排序顺序,值越小越靠前')

    def __repr__(self):
        return f"<chat_dict(id='{self.id}', dict_type='{self.dict_type}', dict_value='{self.dict_value}', dict_name='{self.dict_name}', dict_name_cn='{self.dict_name_cn}', sort_id='{self.sort_id}')>"

    def dict(self):
        return {
            "id": self.id,
            "dict_type": self.dict_type,
            "dict_value": self.dict_value,
            "dict_name": self.dict_name,
            "dict_name_cn": self.dict_name_cn,
            "sort_id": self.sort_id
        }
