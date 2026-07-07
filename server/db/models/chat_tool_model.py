from sqlalchemy import Column, String, Integer, JSON, Text

from server.db.base import Base


class ChatToolModel(Base):
    """
    工具模型
    """
    __tablename__ = 'chat_tool'
    id = Column(Integer, primary_key=True, autoincrement=True, comment='ID')
    tool_name = Column(String(32), comment='工具中文名称', nullable=False, unique=True)
    tool_name_en = Column(String(64), comment='工具英文名称', nullable=False, unique=True)
    tool_description = Column(String(2048), comment='工具描述')
    function_name = Column(String(64), comment='工具调用的函数名称', nullable=False)
    function_properties = Column(JSON, default={}, comment='函数的参数定义')
    function_source = Column(Text, comment='函数脚本')
    tool_config = Column(JSON, default={}, comment='工具配置信息')
    state = Column(String(3), default='0BT', server_default='0BT', comment='状态：0BF禁用，0BT启用')

    def __repr__(self):
        return f"<chat_tool(id='{self.id}', tool_name='{self.tool_name}', tool_name_en='{self.tool_name_en}', tool_description='{self.tool_description}', function_name='{self.function_name}', function_properties='{self.function_properties}', function_source='{self.function_source}', tool_config='{self.tool_config}', state='{self.state}')>"

    def dict(self):
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "tool_name_en": self.tool_name_en,
            "tool_description": self.tool_description,
            "function_name": self.function_name,
            "function_properties": self.function_properties,
            "function_source": self.function_source,
            "tool_config": self.tool_config,
            "state": self.state
        }
