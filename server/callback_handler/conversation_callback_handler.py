import json
from asyncio import CancelledError
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult
from langchain_core.agents import AgentFinish
from langchain_core.outputs import GenerationChunk, ChatGenerationChunk

from common.exceptions import ChatBusinessException
from server.chat.utils import UN_FORMAT_ONLINE_LLM_MODELS
from server.db.repository import update_message
from server.memory.message_i18n import Message_I18N


class ConversationCallbackHandler(BaseCallbackHandler):
    raise_error: bool = True

    def __init__(self, model_name: str, conversation_id: str, message_id: str, chat_type: str, query: str,
                 agent: bool = False):
        self.model_name = model_name
        self.conversation_id = conversation_id
        self.message_id = message_id
        self.chat_type = chat_type
        self.query = query
        self.agent = agent
        self.updated = False
        self.generated_tokens = []
        self.docs = None

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
            self.update_message(finish.return_values.get('output'))
            self.generated_tokens = []
            self.updated = True

    def on_llm_start(
            self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        # 如果想存更多信息，则prompts 也需要持久化
        pass

    def on_llm_new_token(
            self,
            token: str,
            *,
            chunk: Optional[Union[GenerationChunk, ChatGenerationChunk]] = None,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
    ) -> Any:
        if not self.agent:
            self.generated_tokens.append(token)

    def update_message(self, answer: str, error: str = None):
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
        if error:
            metadata["error_info"] = error
        else:
            if self.docs:
                metadata["docs"] = self.docs
        update_message(self.message_id, answer, metadata if len(metadata) > 0 else None)

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if not self.agent and not self.updated:
            answer = response.generations[0][0].text
            self.update_message(answer)
            self.generated_tokens = []
            self.updated = True

    def on_chain_error(
            self,
            error: BaseException,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
    ) -> Any:
        if not self.updated:
            msg = ""
            answer = "".join(self.generated_tokens)
            error_info = f'{error.__class__.__name__}: {error}'
            if answer.strip() == "":
                if isinstance(error, CancelledError):
                    msg = answer = Message_I18N.WORKER_CHAT_CANCELLED.value
                else:
                    msg = answer = Message_I18N.WORKER_CHAT_ERROR.value
            self.update_message(answer, error=error_info)
            self.updated = True
            self.generated_tokens = []
            b_error = ChatBusinessException(msg)
            b_error.__cause__ = error
            raise b_error
