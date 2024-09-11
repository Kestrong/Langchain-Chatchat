from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.schema import AgentFinish
from langchain.schema.output import LLMResult


def dumps(obj: Dict) -> str:
    return json.dumps(obj, ensure_ascii=False)


class AgentStatus:
    llm_start: int = 1
    llm_new_token: int = 2
    llm_end: int = 3
    agent_action: int = 4
    agent_finish: int = 5
    tool_start: int = 6
    tool_end: int = 7
    error: int = 8


class AgentExecutorAsyncIteratorCallbackHandler(AsyncIteratorCallbackHandler):
    def __init__(self):
        super().__init__()
        self.queue = asyncio.Queue()
        self.done = asyncio.Event()
        self.cur_tool = {}
        self.out = True

    async def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
        self.cur_tool.update(
            status=AgentStatus.llm_start,
            llm_token="",
        )
        self.done.clear()
        self.queue.put_nowait(dumps(self.cur_tool))

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        special_tokens = ["\nAction:", "Action:", "\nObservation:", "Observation:", "<|observation|>"]
        for stoken in special_tokens:
            if stoken in token:
                before_action = token.split(stoken)[0]
                self.cur_tool.update(
                    status=AgentStatus.llm_new_token,
                    llm_token=before_action + "\n",
                )
                self.queue.put_nowait(dumps(self.cur_tool))
                self.out = False
                break

        if token and self.out:
            self.cur_tool.update(
                status=AgentStatus.llm_new_token,
                llm_token=token,
            )
            self.queue.put_nowait(dumps(self.cur_tool))

    async def on_chat_model_start(
            self,
            serialized: Dict[str, Any],
            messages: List[List],
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            tags: Optional[List[str]] = None,
            metadata: Optional[Dict[str, Any]] = None,
            **kwargs: Any,
    ) -> None:
        self.cur_tool.update(
            status=AgentStatus.llm_start,
            llm_token="",
        )
        self.done.clear()
        self.queue.put_nowait(dumps(self.cur_tool))

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        self.cur_tool.update(
            status=AgentStatus.llm_end,
            llm_token=response.generations[0][0].text,
        )
        self.queue.put_nowait(dumps(self.cur_tool))

    async def on_llm_error(self, error: Exception | KeyboardInterrupt, **kwargs: Any) -> None:
        self.cur_tool.update(
            status=AgentStatus.error,
            error=str(error),
        )
        self.queue.put_nowait(dumps(self.cur_tool))

    async def on_tool_start(self, serialized: Dict[str, Any], input_str: str, *, run_id: UUID,
                            parent_run_id: UUID | None = None, tags: List[str] | None = None,
                            metadata: Dict[str, Any] | None = None, **kwargs: Any) -> None:

        self.cur_tool = {
            "tool_name": serialized["name"],
            "input_str": input_str,
            "output_str": "",
            "status": AgentStatus.tool_start,
            "run_id": run_id.hex,
            "llm_token": "",
            "final_answer": "",
            "error": "",
        }
        # print("\nInput Str:",self.cur_tool["input_str"])
        self.queue.put_nowait(dumps(self.cur_tool))

    async def on_tool_end(self, output: str, *, run_id: UUID, parent_run_id: UUID | None = None,
                          tags: List[str] | None = None, **kwargs: Any) -> None:
        self.cur_tool.update(
            status=AgentStatus.tool_end,
            output_str=output,
        )
        self.queue.put_nowait(dumps(self.cur_tool))

    async def on_tool_error(self, error: Exception | KeyboardInterrupt, *, run_id: UUID,
                            parent_run_id: UUID | None = None, tags: List[str] | None = None, **kwargs: Any) -> None:
        self.cur_tool.update(
            status=AgentStatus.error,
            error=str(error),
        )
        self.queue.put_nowait(dumps(self.cur_tool))

    async def on_agent_finish(
            self, finish: AgentFinish, *, run_id: UUID, parent_run_id: Optional[UUID] = None,
            tags: Optional[List[str]] = None,
            **kwargs: Any,
    ) -> None:
        if "Thought:" in finish.return_values["output"]:
            finish.return_values["output"] = finish.return_values["output"].replace(
                "Thought:", ""
            )
        # 返回最终答案
        self.cur_tool.update(
            status=AgentStatus.agent_finish,
            final_answer=finish.return_values["output"],
        )
        self.queue.put_nowait(dumps(self.cur_tool))
        self.cur_tool = {}

    async def on_chain_end(
            self,
            outputs: Dict[str, Any],
            *,
            run_id: UUID,
            parent_run_id: UUID | None = None,
            tags: List[str] | None = None,
            **kwargs: Any,
    ) -> None:
        self.out = True
