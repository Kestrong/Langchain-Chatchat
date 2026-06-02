from typing import List

from langchain.schema import BaseMessage, HumanMessage, AIMessage

from server.chat.utils import History
from server.db.repository.message_repository import filter_message
from server.memory.conversation_window_buffer_memory import ConversationBufferWindowMemory


class ConversationBufferDBMemory(ConversationBufferWindowMemory):
    conversation_id: str

    @property
    def history_length(self):
        return self.message_limit * 2

    @property
    def buffer(self) -> List[BaseMessage]:
        """String buffer of memory."""
        # fetch limited messages desc, and return reversed
        from server.chat.utils import un_format_online_llm_model
        un_format = un_format_online_llm_model(self.model_name)
        messages = filter_message(conversation_id=self.conversation_id, limit=self.message_limit)
        # 返回的记录按时间倒序，转为正序
        messages = list(reversed(messages))
        for message in messages:
            chat_files = (message.get('meta_data') or {}).get('chat_files')
            msg_tuple = History(role="user", content=message["query"], chat_files=chat_files).to_msg_tuple(
                format_openai=not un_format)
            self.chat_memory.add_user_message(HumanMessage(content=msg_tuple[1]))
            self.chat_memory.add_ai_message(AIMessage(content=message["response"]))
        return super().buffer
