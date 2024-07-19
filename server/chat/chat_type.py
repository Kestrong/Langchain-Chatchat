import enum


class ChatType(enum.Enum):
    LLM_CHAT = 'llm_chat'
    KNOWLEDGE_BASE_CHAT = 'knowledge_base_chat'
    SEARCH_ENGINE_CHAT = 'search_engine_chat'
    AGENT_CHAT = 'agent_chat'
    FILE_CHAT = 'file_chat'
    COMPLETION = 'completion'
