import asyncio
import json
import uuid
from asyncio import CancelledError
from collections import defaultdict
from functools import partial
from typing import Dict, Any, AsyncIterable, AsyncIterator

from fastapi import Body
from sse_starlette import EventSourceResponse

from configs import logger
from server.chat.chat_type import ChatType
from server.chat.task_manager import task_manager
from server.db.repository import get_assistant_detail_from_db, add_message_to_db, update_message
from server.memory.message_i18n import Message_I18N
from server.utils import BaseResponse
from server.workflow import components
from server.workflow.component.base.component import Component


async def workflow_chat(query: str = Body(..., description="用户输入", examples=["恼羞成怒"]),
                        assistant_id: int = Body(-1, description="助手ID"),
                        stream: bool = False,
                        extra: dict = Body({}, description="额外的属性"),
                        conversation_id: str = Body("", description="对话框ID"),
                        store_message: bool = Body(True, description="是否保存消息到数据库"),
                        ):
    assistant = None
    if assistant_id >= 0:
        assistant = get_assistant_detail_from_db(assistant_id=assistant_id)
    workflow_config = assistant.get("workflow_config", {})
    return do_workflow_chat(query=query, stream=stream, assistant_id=assistant_id, extra=extra,
                            conversation_id=conversation_id,
                            store_message=store_message, workflow_config=workflow_config)


def get_component_type(name: str):
    for tag, group in components.items():
        for g in group:
            if g.__class__.__name__ == name:
                return type(g)
    raise ValueError(f"Unknown component type: {name}")


async def do_workflow_chat(query: str,
                           assistant_id: int = -1,
                           extra: dict = {},
                           stream: bool = False,
                           workflow_config: dict = {},
                           conversation_id: str = None,
                           store_message: bool = True,
                           ):
    if workflow_config is None or len(workflow_config) == 0:
        return BaseResponse(code=500, msg=Message_I18N.API_PARAM_NOT_PRESENT.value.format(
            name="workflow_config"))
    origin_query = query
    message_id = uuid.uuid4().hex
    if not conversation_id:
        conversation_id = uuid.uuid4().hex

    async def execute_nodes(graph, context, state, next_node, queue):
        while next_node:
            next_node_type = next_node.get("type")
            response_node_result = {"node_id": next_node.get("id"), "node_name": next_node.get("name"),
                                    "node_display_name": next_node.get("display_name")}
            target_node_component: Component = get_component_type(next_node_type)(**next_node)
            target_node_component.set_context(context)
            try:
                result: Dict[str, Any] = await target_node_component.run(state)
                response_node_result.update(context[next_node.get("id")])
                queue.put_nowait(response_node_result)
                target_node = None
                if next_node_type == "IfElseComponent":
                    next_nodes = graph[next_node.get("id")]
                    for n in next_nodes:
                        if result.get("condition_result") == n.get("condition"):
                            target_node = n
                            break
                else:
                    next_nodes: list = graph.get(next_node.get("id"))
                    if next_nodes:
                        target_node = next_nodes[0]
                next_node = target_node
            except BaseException as e:
                msg = f"{e}"
                logger.error(msg)
                node_context = context[next_node.get("id")]
                if "outputs" not in node_context:
                    node_context["outputs"] = {}
                node_context["outputs"]["error_info"] = msg
                response_node_result.update(node_context)
                queue.put_nowait(response_node_result)
                break

    async def iter_node_result(queue: asyncio.Queue, event: asyncio.Event) -> AsyncIterator[dict]:
        while not queue.empty() or not event.is_set():
            done, other = await asyncio.wait(
                [
                    asyncio.ensure_future(queue.get()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel the other task
            if other:
                other.pop().cancel()

            # Extract the value of the first completed task
            token_or_done = done.pop().result()

            # If the extracted value is the boolean True, the done event was set
            if token_or_done is True:
                continue

            yield token_or_done

    def execute_node_callback(task: asyncio.Task, event: asyncio.Event, queue: asyncio.Queue):
        event.set()
        queue.put_nowait(True)

    async def chat_iterator() -> AsyncIterable[str]:

        context = {}
        db_message_response: Dict[str, Any] = {}
        response_all_nodes = []
        queue = asyncio.Queue()
        event = asyncio.Event()
        task = None
        try:
            add_message_to_db(chat_type=ChatType.WORKFLOW_CHAT.value, query=origin_query,
                              conversation_id=conversation_id,
                              store=store_message, message_id=message_id, assistant_id=assistant_id)
            nodes = workflow_config.get("nodes", [])
            node_map = {}
            start_node = None
            for n in nodes:
                node = n.get("node", {})
                if node.get("type") == "ChatInputComponent":
                    start_node = node
                node_map[node.get("id")] = node
            edges = workflow_config.get("edges", [])
            graph = defaultdict(list)
            for e in edges:
                target_node = node_map[e.get("target")]
                target_node["condition"] = e.get("condition")
                graph[e.get("source")].append(target_node)

            state = {"query": origin_query, "conversation_id": conversation_id, "store_message": store_message,
                     "assistant_id": assistant_id, "extra": extra}
            next_node = start_node
            task = asyncio.create_task(execute_nodes(graph=graph, state=state, context=context, next_node=next_node,
                                                     queue=queue))

            task.add_done_callback(partial(execute_node_callback, event=event, queue=queue))
            task_manager.put(message_id, task)
            if stream:
                async for a in iter_node_result(queue, event):
                    response_all_nodes.append(a)
                    db_message_response = a.get("outputs")
                    yield {"message_id": message_id, "conversation_id": conversation_id, "result": a}
            else:
                async for a in iter_node_result(queue, event):
                    response_all_nodes.append(a)
                if response_all_nodes:
                    db_message_response = response_all_nodes[-1].get("outputs")
                yield {"message_id": message_id, "conversation_id": conversation_id, "result": response_all_nodes}
            await task
        except BaseException as ex:
            msg = Message_I18N.WORKER_CHAT_CANCELLED.value if isinstance(ex, CancelledError) else f"{ex}"
            if not msg:
                msg = type(ex).__name__
            logger.error(msg)
            db_message_response = {"error_info": msg}
        finally:
            try:
                if (task and not task.done()) or not event.is_set():
                    event.set()
                    task.cancel()
            except BaseException:
                pass
            task_manager.remove(message_id)
            if store_message:
                update_message(message_id=message_id, response=json.dumps(db_message_response),
                               metadata={"trace": response_all_nodes})

    return EventSourceResponse(chat_iterator())
