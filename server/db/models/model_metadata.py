from sqlalchemy import Integer, Column, String

from server.db.base import Base


class ModelMetadataModel(Base):
    """
    模型元数据
    """
    __tablename__ = 'model_metadata'
    id = Column(Integer, primary_key=True, autoincrement=True, comment='ID')
    label = Column(String(32), default=None, comment='模型展示中文名称')
    label_en = Column(String(32), default=None, comment='模型展示英文名称')
    model_name = Column(String(64), comment='模型名称')
    icon = Column(String(4096), comment='模型图标')

    def __repr__(self):
        return f"<model_metadata(id='{self.id}', label='{self.label}', label_en='{self.label_en}', model_name='{self.model_name}', icon='{self.icon}')>"

    def dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "label_en": self.label_en,
            "model_name": self.model_name,
            "icon": self.icon
        }
