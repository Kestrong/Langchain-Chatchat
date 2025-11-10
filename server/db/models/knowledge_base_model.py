from sqlalchemy import Column, Integer, String, DateTime, func

from server.db.base import Base


class KnowledgeBaseModel(Base):
    """
    知识库模型
    """
    __tablename__ = 'knowledge_base'
    id = Column(Integer, primary_key=True, autoincrement=True, comment='知识库ID')
    kb_name = Column(String(50), comment='知识库英文名称')
    kb_name_cn = Column(String(50), comment='知识库中文名称')
    kb_info = Column(String(200), comment='知识库简介(用于Agent)')
    kb_type = Column(String(50), comment='知识库类型')
    vs_type = Column(String(50), comment='向量库类型')
    embed_model = Column(String(50), comment='嵌入模型名称')
    file_count = Column(Integer, default=0, server_default='0', comment='文件数量')
    tag = Column(String(50), comment='标签')
    create_by = Column(String(50), comment='创建人id')
    create_time = Column(DateTime, default=func.now(), server_default=func.now(), comment='创建时间')
    update_time = Column(DateTime, comment='修改时间')
    update_by = Column(String(50), comment='修改人id')
    tenant_id = Column(String(50), comment='租户id')

    def __repr__(self):
        return f"<KnowledgeBase(id='{self.id}', kb_name='{self.kb_name}', kb_name_cn='{self.kb_name_cn}', kb_info='{self.kb_info}, kb_type='{self.kb_type}', vs_type='{self.vs_type}', embed_model='{self.embed_model}', file_count='{self.file_count}', tag='{self.tag}', create_by='{self.create_by}', create_time='{self.create_time}', update_time='{self.update_time}', update_by='{self.update_by}', tenant_id='{self.tenant_id}')>"

    def dict(self):
        return {
            "id": self.id,
            "kb_name": self.kb_name,
            "kb_name_cn": self.kb_name_cn,
            "kb_info": self.kb_info,
            "kb_type": self.kb_type,
            "vs_type": self.vs_type,
            "embed_model": self.embed_model,
            "file_count": self.file_count,
            "tag": self.tag,
            "create_by": self.create_by,
            "tenant_id": self.tenant_id,
            "create_time": self.create_time,
            "update_time": self.update_time,
            "update_by": self.update_by
        }
