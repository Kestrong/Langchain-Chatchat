from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, JSON, func, BigInteger

from configs import SQLALCHEMY_DATABASE_URI
from server.db.base import Base


class KnowledgeFileModel(Base):
    """
    知识文件模型
    """
    __tablename__ = 'knowledge_file'
    id = Column(Integer, primary_key=True, autoincrement=True, comment='知识文件ID')
    file_name = Column(String(255), index=True, comment='文件名')
    file_ext = Column(String(10), comment='文件扩展名')
    kb_id = Column(Integer, index=True, comment='所属知识库id')
    document_loader_name = Column(String(50), comment='文档加载器名称')
    text_splitter_name = Column(String(50), comment='文本分割器名称')
    file_version = Column(Integer, default=1, comment='文件版本')
    file_mtime = Column(Float, default=0.0, comment="文件修改时间")
    file_size = Column(Integer, default=0, comment="文件大小")
    custom_docs = Column(Boolean, default=False, comment="是否自定义docs")
    docs_count = Column(Integer, default=0, comment="切分文档数量")
    create_by = Column(String(50), comment='创建人id')
    create_time = Column(DateTime, index=True, default=func.now(), comment='创建时间')

    def __repr__(self):
        return f"<KnowledgeFile(id='{self.id}', file_name='{self.file_name}', file_ext='{self.file_ext}', kb_id='{self.kb_id}', document_loader_name='{self.document_loader_name}', text_splitter_name='{self.text_splitter_name}', file_version='{self.file_version}', create_time='{self.create_time}', create_by='{self.create_by}')>"

    def dict(self):
        return {
            "id": self.id,
            "file_name": self.file_name,
            "file_ext": self.file_ext,
            "kb_id": self.kb_id,
            "file_mtime": self.file_mtime,
            "document_loader": self.document_loader_name,
            "text_splitter": self.text_splitter_name,
            "file_version": self.file_version,
            "file_size": self.file_size,
            "custom_docs": self.custom_docs,
            "docs_count": self.docs_count,
            "create_by": self.create_by,
            "create_time": self.create_time
        }


class FileDocModel(Base):
    """
    文件-向量库文档模型
    """
    __tablename__ = 'file_doc'
    id = Column(Integer if SQLALCHEMY_DATABASE_URI.__contains__("sqlite") else BigInteger, primary_key=True,
                autoincrement=True, comment='ID')
    kb_id = Column(Integer, index=True, comment='知识库id')
    file_id = Column(Integer, index=True, comment='文件id')
    doc_id = Column(String(50), comment="向量库文档ID")
    meta_data = Column(JSON, default={})

    def __repr__(self):
        return f"<FileDoc(id='{self.id}', kb_id='{self.kb_id}', file_id='{self.file_id}', doc_id='{self.doc_id}', metadata='{self.meta_data}')>"

    def dict(self):
        return {
            "id": self.id,
            "kb_id": self.kb_id,
            "file_id": self.file_id,
            "doc_id": self.doc_id,
            "meta_data": self.meta_data
        }
