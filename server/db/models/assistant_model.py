from sqlalchemy import Column, String, DateTime, func, Text, Integer, JSON

from server.db.base import Base


class AssistantModel(Base):
    """
    助手模型
    """
    __tablename__ = 'assistant'
    id = Column(Integer, primary_key=True, autoincrement=True, comment='助手ID')
    name = Column(Text, default=None, comment='助手名称')
    avatar = Column(Text, default=None, comment='头像图标')
    prompt = Column(String(4096), default=None, comment='提示词')
    model_name = Column(String(64), comment='模型名称')
    prologue = Column(String(4096), comment='开场白')
    knowledge_base_ids = Column(String(512), comment='记录知识库id')
    force_feedback = Column(String(4), default='0BF', comment='是否强制点赞后才能继续对话')
    extra = Column(JSON, default={}, comment='附加属性')
    model_config = Column(JSON, default={}, comment='模型附加配置')
    create_time = Column(DateTime, default=func.now(), comment='创建时间')
    create_by = Column(String(64), comment='创建人id')
    sort_id = Column(Integer, default=0, comment='排序顺序,值越小越靠前')

    def __repr__(self):
        return f"<assistant(id='{self.id}', name='{self.name}', avatar='{self.avatar}', prompt='{self.prompt}', model_name='{self.model_name}', prologue='{self.prologue}', knowledge_base_ids='{self.knowledge_base_ids}', force_feedback='{self.force_feedback}', extra='{self.extra}', model_config='{self.model_config}', create_time='{self.create_time}', create_by='{self.create_by}', sort_id='{self.sort_id}')>"

    def dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "avatar": self.avatar,
            "prompt": self.prompt,
            "model_name": self.model_name,
            "prologue": self.prologue,
            "knowledge_base_ids": self.knowledge_base_ids,
            "force_feedback": self.force_feedback,
            "extra": self.extra,
            "model_config": self.model_config,
            "create_by": self.create_by,
            "create_time": self.create_time,
            "sort_id": self.sort_id
        }
