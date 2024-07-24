import json
from typing import Any, Dict, List

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult

from server.chat.utils import UN_FORMAT_ONLINE_LLM_MODELS
from server.db.repository import update_message


class ConversationCallbackHandler(BaseCallbackHandler):
    raise_error: bool = True

    def __init__(self, model_name: str, conversation_id: str, message_id: str, chat_type: str, query: str):
        self.model_name = model_name
        self.conversation_id = conversation_id
        self.message_id = message_id
        self.chat_type = chat_type
        self.query = query
        self.start_at = None

    @property
    def always_verbose(self) -> bool:
        """Whether to call verbose callbacks even if verbose is False."""
        return True

    def on_llm_start(
            self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        # 如果想存更多信息，则prompts 也需要持久化
        pass

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        answer = response.generations[0][0].text
        mark = f'###[{self.model_name}]###'
        if self.model_name in UN_FORMAT_ONLINE_LLM_MODELS and answer.startswith(mark) and answer.endswith(mark):
            parts = answer.split(mark)
            answer = ''
            for part in parts:
                if part is not None and part.strip() != '':
                    if part.startswith('{') and part.endswith('}'):
                        answer += json.loads(part).get('answer')
                    else:
                        answer += part
        update_message(self.message_id, answer)
