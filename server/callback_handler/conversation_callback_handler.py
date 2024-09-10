import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult
from langchain_core.agents import AgentFinish

from server.chat.utils import UN_FORMAT_ONLINE_LLM_MODELS, MaxInputTokenException
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
                for part in parts:
                    if part is not None and part.strip() != '':
                        if part.startswith('{') and part.endswith('}'):
                            json_obj = json.loads(part)
                            answer += json_obj.get('answer')
                            if 'message_id' in json_obj:
                                metadata['third_message_id'] = json_obj.get('message_id')
                            if 'conversation_id' in json_obj:
                                metadata['third_conversation_id'] = json_obj.get('conversation_id')
                            if 'user' in json_obj:
                                metadata['user'] = json_obj.get('user')
                            if 'api_key' in json_obj:
                                metadata['api_key'] = json_obj.get('api_key')
                        else:
                            answer += part
            update_message(self.message_id, answer, metadata if len(metadata) > 0 else None)
            self.updated = True

    def on_llm_error(
            self,
            error: BaseException,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
    ) -> Any:
        return self.on_chain_error(error, run_id=run_id, parent_run_id=parent_run_id, **kwargs)

    def on_chain_error(
            self,
            error: BaseException,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
    ) -> Any:
        if not self.updated:
            if isinstance(error, MaxInputTokenException):
                response = json.loads(f"{error}").get('answer')
            else:
                response = f"{error}"
            update_message(message_id=self.message_id, response=response)
            self.updated = True
