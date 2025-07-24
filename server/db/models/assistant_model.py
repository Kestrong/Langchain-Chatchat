from sqlalchemy import Column, String, DateTime, func, Text, Integer, JSON, Float

from configs import HISTORY_LEN
from server.db.base import Base


class AssistantModel(Base):
    """
    助手模型
    model_config一些配置样例
    1、文件上传组件：{"uploader":{"uploader_display":true,"max_files":1,"allowed_types":["docx"],"third_attachement":{"tab_name":"流程附件","url":"http://ip:port/path/to","search_params":[{"param_name":"keyword","param_type":"string","element_type":"text","param_description":"附件名称关键词搜索","required":false},{"param_name":"type","param_type":"enum","element_type":"tab","values":[{"label":"故障报告附件","value":"fault"},{"label":"应急预案附件","value":"emergency"}],"param_description":"附件类型搜索","required":true}],"show_fields":[{"label":"文件名","field_name":"name"}],"response_show_format":"selector"}}}
    2、对话框嵌入页面：{"form":{"display":true,"url":"https://ip:port/path","width":"500px","height":"400px"}}
    """
    __tablename__ = 'assistant'
    id = Column(Integer, primary_key=True, autoincrement=True, comment='助手ID')
    name = Column(String(32), default=None, comment='助手名称')
    name_en = Column(String(32), default=None, comment='助手英文名称')
    code = Column(String(32), default=None, comment='助手编码', unique=True)
    avatar = Column(Text, default=None, comment='头像图标')
    prompt = Column(String(4096), default=None, comment='提示词')
    model_name = Column(String(64), comment='模型名称')
    prologue = Column(String(4096), comment='开场白')
    knowledge_base_ids = Column(String(512), comment='记录知识库id')
    force_feedback = Column(String(4), default='0BF', comment='是否强制点赞后才能继续对话')
    state = Column(String(4), default='0BT', comment='状态：0BF禁用，0BT启用')
    history_len = Column(Integer, default=HISTORY_LEN, comment='历史对话轮数')
    top_k = Column(Integer, default=-1, comment='知识库匹配条数')
    score_threshold = Column(Float, default=-1.0, comment='知识库匹配阈值')
    extra = Column(JSON, default={}, comment='附加属性')
    model_config = Column(JSON, default={}, comment='模型附加配置')
    tool_config = Column(JSON, default={}, comment='工具配置')
    create_time = Column(DateTime, default=func.now(), comment='创建时间')
    create_by = Column(String(64), comment='创建人id')
    sort_id = Column(Integer, default=0, comment='排序顺序,值越小越靠前')

    def __repr__(self):
        return f"<assistant(id='{self.id}', name='{self.name}', name_en='{self.name_en}', code='{self.code}', avatar='{self.avatar}', prompt='{self.prompt}', model_name='{self.model_name}', prologue='{self.prologue}', knowledge_base_ids='{self.knowledge_base_ids}', force_feedback='{self.force_feedback}', state='{self.state}', history_len='{self.history_len}', top_k='{self.top_k}', score_threshold='{self.score_threshold}', extra='{self.extra}', model_config='{self.model_config}', tool_config='{self.tool_config}', create_time='{self.create_time}', create_by='{self.create_by}', sort_id='{self.sort_id}')>"

    def dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "name_en": self.name_en,
            "code": self.code,
            "avatar": self.avatar,
            "prompt": self.prompt,
            "model_name": self.model_name,
            "prologue": self.prologue,
            "knowledge_base_ids": self.knowledge_base_ids,
            "force_feedback": self.force_feedback,
            "state": self.state,
            "history_len": self.history_len,
            "top_k": self.top_k,
            "score_threshold": self.score_threshold,
            "extra": self.extra,
            "model_config": self.model_config,
            "tool_config": self.tool_config,
            "create_by": self.create_by,
            "create_time": self.create_time,
            "sort_id": self.sort_id
        }


class WorkflowAssistantModel(AssistantModel):
    workflow_config = Column(JSON, default={}, comment='流程配置')

    def __repr__(self):
        return f"<assistant(id='{self.id}', name='{self.name}', name_en='{self.name_en}', code='{self.code}', avatar='{self.avatar}', prompt='{self.prompt}', model_name='{self.model_name}', prologue='{self.prologue}', knowledge_base_ids='{self.knowledge_base_ids}', force_feedback='{self.force_feedback}', state='{self.state}', history_len='{self.history_len}', top_k='{self.top_k}', score_threshold='{self.score_threshold}', extra='{self.extra}', model_config='{self.model_config}', tool_config='{self.tool_config}', workflow_config='{self.workflow_config}', create_time='{self.create_time}', create_by='{self.create_by}', sort_id='{self.sort_id}')>"

    def dict(self):
        d = super().dict()
        d['workflow_config'] = self.workflow_config
        return d
