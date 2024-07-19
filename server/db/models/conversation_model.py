from sqlalchemy import Column, String, DateTime, func, Integer

from server.db.base import Base


class ConversationModel(Base):
    """
    聊天记录模型
    """
    __tablename__ = 'conversation'
    id = Column(String(32), primary_key=True, comment='对话框ID')
    name = Column(String(50), comment='对话框名称')
    assistant_id = Column(Integer, comment='助手ID')
    # chat/agent_chat等
    chat_type = Column(String(50), comment='聊天类型')
    create_time = Column(DateTime, default=func.now(), comment='创建时间')
    create_by = Column(String(50), index=True, comment='创建人id')

    def __repr__(self):
        return f"<Conversation(id='{self.id}', name='{self.name}', assistant_id='{self.assistant_id}', chat_type='{self.chat_type}', create_time='{self.create_time}', create_by='{self.create_by}')>"

    def dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "assistant_id": self.assistant_id,
            "chat_type": self.chat_type,
            "create_by": self.create_by,
            "create_time": self.create_time
        }
