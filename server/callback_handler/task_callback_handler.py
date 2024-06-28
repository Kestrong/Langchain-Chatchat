from typing import Any, Dict, List

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

import server.chat.task_manager as tm


class TaskCallbackHandler(BaseCallbackHandler):
    raise_error: bool = True

    def __init__(self,conversation_id: str,  message_id: str):
        self.conversation_id = conversation_id
        self.message_id = message_id

    @property
    def always_verbose(self) -> bool:
        """Whether to call verbose callbacks even if verbose is False."""
        return True

    def on_llm_start(
            self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        pass

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        tm.remove(self.message_id)
