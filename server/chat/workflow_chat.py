import asyncio
import json
import uuid
from datetime import datetime
from functools import partial
from typing import Any, AsyncIterable, AsyncIterator, List, Dict, Optional

from fastapi import Body
from starlette.requests import Request

from server.chat.chat_type import ChatType
from server.chat.task_manager import task_manager
from server.chat.utils import choose_response
from server.db.repository import get_assistant_detail_from_db, add_message_to_db, update_message
from server.memory.message_i18n import Message_I18N
from server.utils import BaseResponse
from server.workflow.workflow_engine import WorkflowEngine


def get_safe_forward_headers(request: Optional[Request]) -> Dict[str, str]:
    """提取可安全透传给下游服务的请求头"""
    if not request:
        return {}

    _FORWARD_HEADERS = {"authorization", "cookie", "accept-language", "user-agent"}

    safe_headers = {
        k: v for k, v in request.headers.items()
        if k.lower().startswith("x-") or k.lower() in _FORWARD_HEADERS
    }
    return safe_headers


async def workflow_chat(query: str = Body(..., description="用户输入", examples=["恼羞成怒"]),
                        tag: str = Body(default="", description="会话标签"),
                        assistant_id: int = Body(-1, description="助手ID"),
                        stream: bool = Body(False, description="流式输出"),
                        extra: dict = Body({}, description="额外的属性"),
                        conversation_id: str = Body("", description="对话框ID"),
                        knowledge_id: str = Body("", description="临时知识库ID"),
                        store_message: bool = Body(True, description="是否保存消息到数据库"),
                        request: Request = None,
                        ):
    assistant = None
    if assistant_id >= 0:
        assistant = get_assistant_detail_from_db(assistant_id=assistant_id)
    workflow_config = assistant.get("workflow_config", {})
    return await do_workflow_chat(query=query, stream=stream, assistant_id=assistant_id, extra=extra,
                                  conversation_id=conversation_id, knowledge_id=knowledge_id, tag=tag,
                                  store_message=store_message, workflow_config=workflow_config, request=request, )


async def do_workflow_chat(query: str,
                           tag: str = '',
                           assistant_id: int = -1,
                           extra: dict = {},
                           stream: bool = False,
                           workflow_config: dict = {},
                           conversation_id: str = None,
                           knowledge_id: str = "",
                           store_message: bool = True,
                           request: Request = None,
                           ):
    if workflow_config is None or len(workflow_config) == 0:
        return BaseResponse(code=500, msg=Message_I18N.API_PARAM_NOT_PRESENT.value.format(
            name="workflow_config"))
    origin_query = query
    message_id = uuid.uuid4().hex
    if not conversation_id:
        conversation_id = uuid.uuid4().hex

    async def iter_node_result(queue: asyncio.Queue, event: asyncio.Event) -> AsyncIterator[dict]:
        while not queue.empty() or not event.is_set():
            try:
                # 直接等待队列获取，避免复杂的状态管理
                item = await queue.get()

                # 如果获取到特殊信号，继续循环
                if item is True:
                    continue

                yield item
            except asyncio.CancelledError:
                break

    def execute_node_callback(task: asyncio.Task, event: asyncio.Event, queue: asyncio.Queue):
        event.set()
        queue.put_nowait(True)

    async def chat_iterator() -> AsyncIterable[str]:

        context = {"GLOBAL": {"inputs": {"current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                         "headers": get_safe_forward_headers(request)}}}
        db_message_response: List[Any] = []
        total_tokens = 0
        response_all_nodes = []
        queue = asyncio.Queue()
        event = asyncio.Event()
        task = None
        workflow_engine = None
        try:
            add_message_to_db(chat_type=ChatType.WORKFLOW_CHAT.value, query=origin_query,
                              conversation_id=conversation_id, tag=tag,
                              store=store_message, message_id=message_id, assistant_id=assistant_id)
            nodes = workflow_config.get("nodes", [])
            edges = workflow_config.get("edges", [])
            state = {"query": origin_query, "conversation_id": conversation_id, "store_message": store_message,
                     "assistant_id": assistant_id, "knowledge_id": knowledge_id, "extra": extra, "tag": tag}
            workflow_engine = WorkflowEngine(workflow_id=str(assistant_id), config=workflow_config.get("config", {}),
                                             nodes=nodes, edges=edges, queue=queue, context=context, state=state,
                                             stream=stream)
            task = asyncio.create_task(workflow_engine.run())

            task.add_done_callback(partial(execute_node_callback, event=event, queue=queue))
            task_manager.put(message_id, task)
            if stream:
                yield json.dumps(
                    {"event": "workflow_started", "message_id": message_id, "conversation_id": conversation_id},
                    ensure_ascii=False)
                thought = ''
                async for a in iter_node_result(queue, event):
                    if "node_id" not in a and "event" in a:
                        n_thought = a.get('thought')
                        if n_thought:
                            thought += n_thought
                        yield json.dumps({"message_id": message_id, "conversation_id": conversation_id, **a},
                                         ensure_ascii=False)
                        continue
                    response_all_nodes.append(a)
                    node_outputs = a.get("outputs", {})
                    node_tokens = node_outputs.pop("total_tokens", 0) or 0
                    total_tokens += node_tokens
                    if a.get("node_name") == "chat_output":
                        if thought:
                            db_message_response.append(f'<think>\n{thought}\n</think>')
                            thought = ''
                        db_message_response.append(node_outputs.get("answer"))
                    elif a.get("node_name") == "chat_structure_output":
                        if thought:
                            db_message_response.append(f'<think>\n{thought}\n</think>')
                            thought = ''
                        s_answer = node_outputs.get("answer")
                        s_event = {"event": "message", "message_id": message_id, "conversation_id": conversation_id,
                                   "answer": s_answer}
                        if node_tokens > 0:
                            s_event["total_tokens"] = node_tokens
                        yield json.dumps(s_event, ensure_ascii=False)
                        db_message_response.append(json.dumps(s_answer, ensure_ascii=False))
                    node_result = {"event": "node_finished", "message_id": message_id,
                                   "conversation_id": conversation_id, "answer": a}
                    if node_tokens > 0:
                        node_result["total_tokens"] = node_tokens
                    yield json.dumps(node_result, ensure_ascii=False)
                yield json.dumps(
                    {"event": "workflow_finished", "message_id": message_id, "conversation_id": conversation_id,
                     "total_tokens": total_tokens}, ensure_ascii=False)
            else:
                yield json.dumps({"event": "message", "message_id": message_id, "conversation_id": conversation_id},
                                 ensure_ascii=False)
                async for a in iter_node_result(queue, event):
                    response_all_nodes.append(a)
                    node_outputs = a.get("outputs", {})
                    total_tokens += node_outputs.pop("total_tokens", 0) or 0
                    if a.get("node_name") in ["chat_output", "chat_structure_output"]:
                        db_message_response.append(node_outputs.get("answer"))
                yield json.dumps(
                    {"event": "message", "message_id": message_id, "conversation_id": conversation_id,
                     "answer": "".join(db_message_response) if not db_message_response or all(
                         isinstance(m, str) for m in db_message_response) else db_message_response[0] if len(
                         db_message_response) == 1 else db_message_response,
                     "total_tokens": total_tokens}, ensure_ascii=False)
            await task
        finally:
            try:
                if (task and not task.done()) or not event.is_set():
                    queue.put_nowait(True)
                    event.set()
                    task.cancel()
                    await task
                if workflow_engine:
                    await workflow_engine.cancel()
            except BaseException:
                pass
            task_manager.remove(message_id)
            if store_message:
                response = "".join(
                    [m if isinstance(m, str) else json.dumps(m, ensure_ascii=False) for m in db_message_response])
                update_message(message_id=message_id, response=response, response_time=datetime.now(),
                               total_tokens=total_tokens, metadata={"trace": response_all_nodes}, )

    async def chat_iterator_backend() -> AsyncIterable[str]:
        async def consume_iterator(iterator: AsyncIterable[str]):
            async for _ in iterator:
                pass

        _ = asyncio.create_task(consume_iterator(chat_iterator()))
        yield json.dumps(
            {"event": "message", "message_id": message_id, "conversation_id": conversation_id},
            ensure_ascii=False)

    if not extra.get('backend'):
        return await choose_response(stream, chat_iterator(), request)
    return await choose_response(stream, chat_iterator_backend(), request)
