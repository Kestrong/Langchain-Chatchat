from sqlalchemy import Integer, Column, String, Float, DateTime, JSON, func

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


class ModelPerformanceMetricsModel(Base):
    """
    性能指标监控日志模型
    """
    __tablename__ = 'model_performance_metrics'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='性能指标ID')
    conversation_id = Column(String(32), index=True, comment='对话框ID')
    message_id = Column(String(32), index=True, comment='消息ID')
    model_name = Column(String(64), comment='模型名称')
    chat_type = Column(String(50), comment='聊天类型')
    start_time = Column(DateTime, comment='开始时间')
    first_token_latency = Column(Float, comment='首token延迟(秒)')
    tokens_per_second = Column(Float, comment='每秒tokens数')
    total_tokens = Column(Integer, default=0, server_default='0', comment='总token数')
    total_time = Column(Float, comment='总耗时(秒)')
    end_time = Column(DateTime, comment='结束时间')
    create_time = Column(DateTime, index=True, default=func.now(), server_default=func.now(), comment='创建时间')
    extra_info = Column(JSON, default={}, comment='额外信息')

    def __repr__(self):
        return f"<ModelPerformanceMetrics(id='{self.id}', conversation_id='{self.conversation_id}', message_id='{self.message_id}', model_name='{self.model_name}', chat_type='{self.chat_type}', start_time='{self.start_time}', first_token_latency='{self.first_token_latency}', tokens_per_second='{self.tokens_per_second}', total_tokens='{self.total_tokens}', total_time='{self.total_time}', end_time='{self.end_time}', create_time='{self.create_time}')>"

    def dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "model_name": self.model_name,
            "chat_type": self.chat_type,
            "start_time": self.start_time,
            "first_token_latency": self.first_token_latency,
            "tokens_per_second": self.tokens_per_second,
            "total_tokens": self.total_tokens,
            "total_time": self.total_time,
            "end_time": self.end_time,
            "create_time": self.create_time,
            "extra_info": self.extra_info,
        }
