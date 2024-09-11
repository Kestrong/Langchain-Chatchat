import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult
from langchain_core.agents import AgentFinish

from server.chat.utils import UN_FORMAT_ONLINE_LLM_MODELS
from server.db.repository import update_message


class ConversationCallbackHandler(BaseCallbackHandler):
    raise_error: bool = True

    def __init__(self, model_name: str, conversation_id: str, message_id: str, chat_type: str, query: str,
                 agent: bool = False):
        self.model_name = model_name
        self.conversation_id = conversation_id
        self.message_id = message_id
        self.chat_type = chat_type
        self.query = query
        self.start_at = None
        self.agent = agent
        self.updated = False

    @property
    def always_verbose(self) -> bool:
        """Whether to call verbose callbacks even if verbose is False."""
        return True

    def on_agent_finish(
            self,
            finish: AgentFinish,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
    ) -> Any:
        if self.agent and not self.updated:
            update_message(self.message_id, finish.return_values.get('output'))
            self.updated = True

    def on_llm_start(
            self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        # 如果想存更多信息，则prompts 也需要持久化
        pass

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if not self.agent and not self.updated:
            answer = response.generations[0][0].text
            mark = f'###[{self.model_name}]###'
            metadata = {}
            if self.model_name in UN_FORMAT_ONLINE_LLM_MODELS and answer.startswith(mark) and answer.endswith(mark):
                parts = answer.split(mark)
                answer = ''
                extra_key_map = {"message_id": "third_message_id", "conversation_id": "third_conversation_id",
                                 "user": "user", "api_key": "api_key"}
                for part in parts:
                    if part is not None and part.strip() != '':
                        if part.startswith('{') and part.endswith('}'):
                            json_obj = json.loads(part)
                            answer += json_obj.get('answer')
                            for key, value in extra_key_map.items():
                                if key in json_obj:
                                    metadata[value] = json_obj.get(key)
                        else:
                            answer += part
            update_message(self.message_id, answer, metadata if len(metadata) > 0 else None)
            self.updated = True
