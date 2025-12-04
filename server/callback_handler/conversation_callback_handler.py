import datetime
import json
import os
import time
from asyncio import CancelledError
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult
from langchain_core.agents import AgentFinish
from langchain_core.outputs import GenerationChunk, ChatGenerationChunk

from common.exceptions import ChatBusinessException
from configs import logger
from server.db.repository import update_message
from server.memory.message_i18n import Message_I18N


class ConversationCallbackHandler(BaseCallbackHandler):
    raise_error: bool = True
    token_save_interval: int = int(os.environ.get("TOKEN_SAVE_INTERVAL", 100))

    def __init__(self, model_name: str, conversation_id: str, message_id: str, chat_type: str, query: str,
                 agent: bool = False, stream: bool = False, realtime_token_save: bool = False):
        self.model_name = model_name
        self.conversation_id = conversation_id
        self.message_id = message_id
        self.chat_type = chat_type
        self.query = query
        self.agent = agent
        self.updated = False
        self.generated_tokens = []
        self.start_time = None
        self.first_token_time = None
        self.token_count = 0
        self.docs = None
        self.extra = {'stream': stream, 'realtime_token_save': realtime_token_save, 'answer': '', 'metadata': {},
                      'response_time_updated': False}

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
            final_answer = finish.return_values["output"]
            metadata = None
            if final_answer.startswith("{") and final_answer.endswith("}"):
                try:
                    f = json.loads(final_answer)
                    if 'metadata' in f:
                        metadata = f['metadata']
                        del f['metadata']
                    final_answer = json.dumps(f, ensure_ascii=False)
                except Exception:
                    pass
            self.update_message(final_answer, metadata=metadata)
            self.generated_tokens = []
            self.updated = True
            self.token_count += len(final_answer)
            self._log_performance_metrics()

    def on_llm_start(
            self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        # 如果想存更多信息，则prompts 也需要持久化
        self.start_time = time.time()
        self.first_token_time = None

    def on_llm_new_token(
            self,
            token: str,
            *,
            chunk: Optional[Union[GenerationChunk, ChatGenerationChunk]] = None,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
    ) -> Any:
        if self.first_token_time is None and token:
            self.first_token_time = time.time()
        if not self.agent:
            self.generated_tokens.append(token)
            realtime_token_save = self.extra.get("realtime_token_save", False)
            if realtime_token_save and os.environ.get("REALTIME_TOKEN_SAVE", "True") == "True":
                answer, metadata = self.parse_token(token)
                self.extra['answer'] = self.extra.get('answer', '') + answer
                self.extra['metadata'].update(metadata)
                if len(self.extra['answer']) >= self.token_save_interval:
                    update_message(message_id=self.message_id, response=self.extra['answer'],
                                   metadata=self.extra['metadata'], append=True,
                                   response_time=datetime.datetime.now())
                    self.extra['answer'] = ''
                    self.extra['metadata'].clear()
            else:
                stream = self.extra.get("stream", False)
                response_time_updated = self.extra.get("response_time_updated", False)
                if stream and not response_time_updated and token:
                    update_message(message_id=self.message_id, response_time=datetime.datetime.now(), )
                    self.extra['response_time_updated'] = True
        else:
            self.token_count += len(token)

    def parse_token(self, token: str, metadata: dict = None, error: str = None):
        mark = f'###[{self.model_name}]###'
        answer = ''
        if metadata is None:
            metadata = {}
        if mark in token:
            parts = token.split(mark)
            extra_key_map = {"message_id": "third_message_id", "conversation_id": "third_conversation_id",
                             "user": "user", "api_key": "api_key", "appId": "appId", "docs": "docs"}
            for part in parts:
                if part is not None and part.strip() != '':
                    if part.startswith('{') and part.endswith('}'):
                        json_obj = json.loads(part)
                        if 'answer' in json_obj:
                            answer += json_obj.get('answer')
                        for key, value in extra_key_map.items():
                            if key in json_obj:
                                metadata[value] = json_obj.get(key)
                    else:
                        answer += part
        else:
            if token:
                answer = token
        if error:
            metadata["error_info"] = error
        else:
            if self.docs:
                metadata["docs"] = self.docs
        return answer, metadata

    def update_message(self, answer: str, metadata: dict = None, error: str = None):
        answer, metadata = self.parse_token(answer, metadata, error)
        update_message(self.message_id, answer, metadata if len(metadata) > 0 else None,
                       response_time=datetime.datetime.now())
        return answer

    def _log_performance_metrics(self):
        """记录性能指标到日志"""
        if self.start_time is None:
            return

        end_time = time.time()
        total_time = end_time - self.start_time

        # 计算各项指标
        first_token_latency = (self.first_token_time - self.start_time) if self.first_token_time else 0
        tokens_per_second = self.token_count / total_time if total_time > 0 else 0

        # 使用logger记录性能指标
        logger.info(
            f"Model Performance Metrics - "
            f"Model: {self.model_name}, "
            f"Conversation ID: {self.conversation_id}, "
            f"Message ID: {self.message_id}, "
            f"First Token Latency: {first_token_latency:.4f}s, "
            f"Tokens/Second: {tokens_per_second:.2f}, "
            f"Total Tokens: {self.token_count}, "
            f"Total Time: {total_time:.4f}s"
        )

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if not self.agent and not self.updated:
            answer = response.generations[0][0].text
            answer = self.update_message(answer)
            self.generated_tokens = []
            self.updated = True
            self.token_count = len(answer)

            self._log_performance_metrics()

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
