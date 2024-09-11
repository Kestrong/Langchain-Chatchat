import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.agents import AgentFinish
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from server.chat.task_manager import task_manager as tm
from configs import MAX_TOKENS_INPUT
from server.chat.utils import MaxInputTokenException


class TaskCallbackHandler(BaseCallbackHandler):
    raise_error: bool = True

    def __init__(self, conversation_id: str, message_id: str, agent: bool = False):
        self.conversation_id = conversation_id
        self.message_id = message_id
        self.agent = agent

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
        if self.agent:
            tm.remove(self.message_id)

    def on_llm_start(
            self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        token_num = 0
        for prompt in prompts:
            token_num += len(prompt)

        if token_num > MAX_TOKENS_INPUT:
            msg = f"当前限制输入不能超过{MAX_TOKENS_INPUT}个字符，您的输入长度为{token_num}(包含提示词、输入文档和历史对话内容)"
            raise MaxInputTokenException(msg)

    def on_llm_end(
            self,
            response: LLMResult,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
    ) -> Any:
        if not self.agent:
            tm.remove(self.message_id)

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
        tm.remove(self.message_id)
