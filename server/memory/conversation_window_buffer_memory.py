from typing import Any, List, Dict, Union

from langchain.memory.chat_memory import BaseChatMemory
from langchain.schema import get_buffer_string, BaseMessage

from configs import LLM_MODELS
from server.chat.utils import calculate_token_len, has_input_memory_key


class ConversationBufferWindowMemory(BaseChatMemory):
    human_prefix: str = "human"
    ai_prefix: str = "ai"
    model_name: str = LLM_MODELS[0]
    memory_key: str = "history"
    message_limit: int = 10
    prompt_length: int = 0  # just for calculate token length.

    @property
    def history_length(self):
        return self.message_limit

    @property
    def buffer(self) -> Union[str, List[BaseMessage]]:
        """String buffer of memory."""
        return self.buffer_as_messages if self.return_messages else self.buffer_as_str

    @property
    def buffer_as_str(self) -> str:
        """Exposes the buffer as a string in case return_messages is False."""
        messages = self.buffer_as_messages
        return get_buffer_string(
            messages,
            human_prefix=self.human_prefix,
            ai_prefix=self.ai_prefix,
        )

    @property
    def buffer_as_messages(self) -> List[BaseMessage]:
        """Exposes the buffer as a list of messages in case return_messages is False."""
        from server.chat.utils import get_max_token_limit
        max_token_limit = int(get_max_token_limit(self.model_name) * 0.85)
        messages = []
        length = self.prompt_length
        for m in self.chat_memory.messages:
            if len(messages) >= self.history_length:
                break
            length += calculate_token_len(m.type, m.content)
            if length > max_token_limit:
                break
            messages.append(m)
        return messages

    @property
    def memory_variables(self) -> List[str]:
        """Will always return list of memory variables.

        :meta private:
        """
        return [self.memory_key]

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Return history buffer."""
        return {self.memory_key: self.buffer}

    def buffer_history(self, input_variables: List[str]) -> List[BaseMessage]:
        if has_input_memory_key(input_variables, self.memory_variables):
            return []
        return self.buffer_as_messages
