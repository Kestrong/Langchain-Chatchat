import json
import threading
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult
from langchain_core.agents import AgentFinish
from langchain_core.outputs import GenerationChunk, ChatGenerationChunk

from configs import logger
from server.chat.utils import get_tiktoken_num
from server.db.repository import update_message


class TokenCallbackHandler(BaseCallbackHandler):

    def __init__(self, model_name: str, message_id: str):
        self.model_name = model_name
        self.message_id = message_id
        self.inner_total_tokens = 0
        self.outside_total_tokens = 0
        self.outside_final_total_tokens = 0
        self.last_total_tokens = 0
        from server.chat.utils import un_format_online_llm_model
        self.unformat = un_format_online_llm_model(self.model_name)
        self._lock = threading.Lock()

    def on_agent_finish(
            self,
            finish: AgentFinish,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
    ) -> Any:
        self.update_message_cb()

    def on_llm_start(
            self,
            serialized: Dict[str, Any],
            prompts: List[str],
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            tags: Optional[List[str]] = None,
            metadata: Optional[Dict[str, Any]] = None,
            **kwargs: Any,
    ) -> Any:
        if prompts:
            with self._lock:
                self.inner_total_tokens += get_tiktoken_num(prompts)

    def on_llm_new_token(
            self,
            token: str,
            *,
            chunk: Optional[Union[GenerationChunk, ChatGenerationChunk]] = None,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
    ) -> Any:
        answer, total_tokens, final_total_tokens = self.parse_token(token)
        with self._lock:
            if self.unformat:
                if final_total_tokens:
                    self.outside_final_total_tokens += final_total_tokens
                elif total_tokens:
                    self.outside_total_tokens += total_tokens
            else:
                if answer:
                    self.inner_total_tokens += get_tiktoken_num(answer)

    def parse_token(self, token: str):
        mark = f'###[{self.model_name}]###'
        answer = ''
        total_tokens = None
        final_total_tokens = None
        if mark in token:
            parts = token.split(mark)
            for part in parts:
                if part is not None and part.strip() != '':
                    if part.startswith('{') and part.endswith('}'):
                        json_obj = json.loads(part)
                        if 'answer' in json_obj:
                            answer += json_obj.get('answer')
                        if 'total_tokens' in json_obj:
                            total_tokens = json_obj.get('total_tokens')
                        if 'final_total_tokens' in json_obj:
                            final_total_tokens = json_obj.get('final_total_tokens')
                    else:
                        answer += part
        else:
            if token:
                answer = token
        return answer, total_tokens, final_total_tokens

    def update_message_cb(self):
        tokens_to_update = 0
        with self._lock:
            current_tokens = self._get_current_tokens()
            if current_tokens > self.last_total_tokens:
                self.last_total_tokens = current_tokens
                tokens_to_update = current_tokens
        if tokens_to_update > 0:
            try:
                update_message(self.message_id, total_tokens=tokens_to_update)
            except BaseException as e:
                logger.error(f"[TokenCallback] update db error: {e}")

    def on_llm_end(
            self,
            response: LLMResult,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
    ) -> Any:
        self.update_message_cb()

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
        self.update_message_cb()

    def _get_current_tokens(self):
        if self.unformat:
            return self.outside_final_total_tokens if self.outside_final_total_tokens > 0 else self.outside_total_tokens
        return self.inner_total_tokens

    @property
    def total_tokens(self):
        return self._get_current_tokens()
