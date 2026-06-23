import json
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult
from langchain_core.agents import AgentFinish
from langchain_core.outputs import GenerationChunk, ChatGenerationChunk

from server.chat.utils import get_tiktoken_num
from server.db.repository import update_message


class TokenCallbackHandler(BaseCallbackHandler):

    def __init__(self, model_name: str, message_id: str, agent: bool = False, ):
        self.model_name = model_name
        self.message_id = message_id
        self.inner_total_tokens = 0
        self.outside_total_tokens = 0
        self.updated = False
        self.agent = agent
        self.remaining_runs = 0
        from server.chat.utils import un_format_online_llm_model
        self.unformat = un_format_online_llm_model(self.model_name)

    def on_agent_finish(
            self,
            finish: AgentFinish,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
    ) -> Any:
        if self.agent and not self.updated:
            self.update_message_cb()
            self.updated = True

    def on_llm_start(
            self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        self.remaining_runs += 1
        if prompts:
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
        if self.unformat:
            if final_total_tokens:
                self.outside_total_tokens = final_total_tokens
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
        if self.unformat:
            update_message(self.message_id, total_tokens=self.outside_total_tokens)
        else:
            update_message(self.message_id, total_tokens=self.inner_total_tokens)

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if not self.agent and not self.updated and self.remaining_runs == 1:
            self.update_message_cb()
            self.updated = True
        self.remaining_runs -= 1

    @property
    def total_tokens(self):
        if self.unformat:
            return self.outside_total_tokens
        return self.inner_total_tokens
