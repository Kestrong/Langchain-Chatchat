from sqlalchemy import Column, String, DateTime, func, Integer

from server.db.base import Base


class ChatAppModel(Base):
    """
    应用模型
    """
    __tablename__ = 'chat_app'
    id = Column(Integer, primary_key=True, autoincrement=True, comment='ID')
    name = Column(String(32), default=None, comment='助手名称')
    name_en = Column(String(32), default=None, comment='助手英文名称')
    api_key = Column(String(512), default=None, comment='app编码', unique=True)
    secret_key = Column(String(512), default=None, comment='认证密钥')
    create_time = Column(DateTime, default=func.now(), server_default=func.now(), comment='创建时间')
    expired_time = Column(DateTime, default=None, comment='过期时间，为空不过期')

    def __repr__(self):
        return f"<chat_app(id='{self.id}', name='{self.name}', name_en='{self.name_en}', api_key='{self.api_key}', secret_key='{self.secret_key}', create_time='{self.create_time}', expired_time='{self.expired_time}')>"

    def dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "name_en": self.name_en,
            "api_key": self.api_key,
            "secret_key": self.secret_key,
            "create_time": self.create_time,
            "expired_time": self.expired_time
        }
