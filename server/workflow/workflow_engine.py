import asyncio
import time
import uuid
from collections import defaultdict, deque
from typing import Dict, Any

from common.exceptions import ChatBusinessException
from configs import logger, log_verbose
from server.workflow import ALL_COMPONENT_CLASSES_MAP
from server.workflow.component.base.component import Component
from server.workflow.component.outputs.chat_output import ChatOutputComponent
from server.workflow.utils.event_manager import AsyncPubSub, SSEEventType, SSEEvent


def get_component_type(name: str):
    component_type = ALL_COMPONENT_CLASSES_MAP.get(name)
    if not component_type:
        raise ValueError(f"Unknown component type: {name}")
    return component_type


class WorkflowEngine:
    def __init__(self, workflow_id: str, config: dict, nodes: list, edges: list, queue: asyncio.Queue,
                 context: dict, state: dict, stream: bool = True):
        self.workflow_id = workflow_id
        self.workflow_run_id = uuid.uuid4().hex
        self.config = config
        self.context = context
        self.state = state
        self.nodes = {}
        self.node_done_events = {}
        self.start_node = None
        self.node_lock = asyncio.Lock()
        self.pubsub = AsyncPubSub() if stream else None
        self.state.setdefault("pubsub", self.pubsub)
        self.execution_semaphore = asyncio.Semaphore(1)

        for n in nodes:
            n = n.get("node") if "node" in n else n
            node_id = n.get("id")
            if n.get("type") == "ChatInputComponent":
                self.start_node = n
            self.nodes[node_id] = n
            self.node_done_events[node_id] = asyncio.Event()

        if not self.start_node:
            raise ValueError("Workflow must have a ChatInputComponent as start node")

        self.edges = edges
        self.queue = queue

        self.successors = defaultdict(list)
        self.predecessors = defaultdict(list)
        for edge in edges:
            self.successors[edge.get("source")].append(edge)
            self.predecessors[edge.get("target")].append(edge)

        self._validate_dag()

        self.skipped_nodes = set()
        self.results = {}
        self.canceled_event = asyncio.Event()
        self.tasks_queue = asyncio.Queue()
        self.stream = stream

    def _get_node_timeout(self, node: dict) -> float:
        node_timeout = node.get("timeout")
        if node_timeout is not None:
            return float(node_timeout)
        env_timeout = self.config.get("WORKFLOW_NODE_TIMEOUT")
        if env_timeout is not None:
            return float(env_timeout)
        return 300

    def _validate_dag(self):
        in_degree = defaultdict(int)
        for node_id in self.nodes:
            in_degree[node_id] = 0
        for edge in self.edges:
            in_degree[edge.get("target")] += 1

        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        visited_count = 0
        while queue:
            node_id = queue.popleft()
            visited_count += 1
            for edge in self.successors.get(node_id, []):
                target = edge.get("target")
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    queue.append(target)

        if visited_count != len(self.nodes):
            raise ValueError("Workflow contains a cycle! It must be a DAG.")

    def _propagate_skip(self, node_id, exclude_nodes=None):
        """
        【条件传播机制】
        级联跳过下游节点：只有当某个下游节点的【所有】上游都被跳过时，
        它才会被标记为跳过，并继续向它的下游传播。
        这完美解决了非对称分支汇合（如 B-E-F 和 C-D-E）的死锁问题。
        """
        # 使用队列来存储待处理的节点，实现BFS
        queue = deque([node_id])

        while queue:
            current_node = queue.popleft()

            # 遍历当前节点的所有下游节点
            for edge in self.successors.get(current_node, []):
                target = edge.get("target")
                if exclude_nodes and target in exclude_nodes:
                    continue

                # 如果目标节点已经被跳过，或者已经在处理中，则跳过
                if target in self.skipped_nodes or self.node_done_events[target].is_set():
                    continue

                # 检查目标节点的所有上游是否都已经被跳过
                all_preds_skipped = True
                for pred in self.predecessors.get(target, []):
                    if pred.get('source') not in self.skipped_nodes:
                        all_preds_skipped = False
                        break

                if all_preds_skipped:
                    self.skipped_nodes.add(target)
                    self.node_done_events[target].set()  # 唤醒以防死锁
                    # 将该节点加入队列，继续处理它的下游
                    queue.append(target)

    def get_active_predecessors(self, node_id):
        """
        获取真正需要等待的上游节点：
        过滤掉已经被跳过的节点，以及已经执行完毕的节点。
        """
        return [
            pred.get('source') for pred in self.predecessors.get(node_id, [])
            if pred.get('source') not in self.skipped_nodes and not self.node_done_events[pred.get('source')].is_set()
        ]

    async def run(self):
        try:
            # 纯异步模式：启动起始节点任务，并等待全局完成信号
            start_task = asyncio.create_task(self._execute_node(self.start_node))
            self.tasks_queue.put_nowait(start_task)
            await asyncio.wait_for(self.tasks_queue.join(), timeout=self.config.get("WORKFLOW_TIMEOUT", 1800))
            while not self.tasks_queue.empty():
                task = self.tasks_queue.get_nowait()
                if isinstance(task, asyncio.Task):
                    task.result()
        except Exception as e:
            logger.error(f"[Workflow-{self.workflow_id}] 执行失败 | workflow_run_id={self.workflow_run_id} | error={e}",
                         exc_info=e if log_verbose else None)
            self.queue.put_nowait(True)
            await self.cancel()
            raise e

    async def _stream_process(self, component: Component):
        if not self.pubsub:
            return
        async with self.execution_semaphore:
            async for chunk in component.chunk_answer():
                if not chunk:
                    continue
                if chunk.startswith("{{") and chunk.endswith("}}"):
                    streamable = False
                    variable = chunk[2:-2]
                    v_node_id = variable.split(".")[0].strip()
                    if v_node_id in self.nodes:
                        v_node = self.nodes.get(v_node_id)
                        v_type = get_component_type(v_node.get("type"))
                        if hasattr(v_type, "streamable") and v_type.streamable:
                            streamable = True

                    already_streamable = False
                    if streamable:
                        sub = await self.pubsub.subscribe(v_node_id)
                        if sub:
                            async for event in sub.stream():
                                if event.event_type == SSEEventType.DONE:
                                    break
                                if event.event_type == SSEEventType.HEARTBEAT:
                                    if not already_streamable and self.node_done_events[v_node_id].is_set():
                                        break
                                    continue
                                already_streamable = True
                                self.queue.put_nowait(event.data)

                    if not already_streamable:
                        if v_node_id in self.node_done_events:
                            await self.node_done_events[v_node_id].wait()
                        value = component.get_nested_value(self.context, variable)
                        self.queue.put_nowait({"event": "message", "answer": value or ""})
                else:
                    self.queue.put_nowait({"event": "message", "answer": chunk})

    async def _execute_node(self, node):

        node_id = node.get("id")
        node_name = node.get("name")
        node_type = node.get("type")

        try:
            if self.canceled_event.is_set():
                return

            if node_type in ["ChatOutputComponent", "ChatStructureOutputComponent"]:
                output_component = ChatOutputComponent(**node)
                await self._stream_process(output_component)

            predecessors = self.get_active_predecessors(node_id)
            if len(predecessors) > 0:
                await asyncio.gather(*[
                    self.node_done_events[pred_id].wait()
                    for pred_id in predecessors
                ])

            if self.canceled_event.is_set():
                return

            response_node_result = {
                "workflow_run_id": self.workflow_run_id,
                "node_id": node_id,
                "node_name": node_name,
                "node_display_name": node.get("display_name")
            }

            start_time = time.monotonic()
            logger.info(
                f"[Workflow-{self.workflow_id}] 节点开始执行 | workflow_run_id={self.workflow_run_id} | node_id={node_id} | node_name={node_name} | node_type={node_type}")

            max_retries = int(node.get("max_retries", 0))
            retry_delay = float(node.get("retry_delay", 0))
            error_handler = node.get('error_handler')
            attempt = 0

            while True:
                try:
                    target_node_component: Component = get_component_type(node_type)(**node)
                    target_node_component.set_context(self.context)

                    if target_node_component.max_retries:
                        max_retries = target_node_component.max_retries
                    if target_node_component.retry_delay:
                        retry_delay = target_node_component.retry_delay
                    if target_node_component.error_handler:
                        error_handler = target_node_component.error_handler

                    timeout = self._get_node_timeout(node)
                    result: Dict[str, Any] = await asyncio.wait_for(
                        target_node_component.run(self.state),
                        timeout=timeout
                    )

                    self.results[node_id] = result
                    response_node_result.update(self.context[node_id])
                    self.queue.put_nowait(response_node_result)

                    elapsed = round(time.monotonic() - start_time, 3)
                    logger.info(
                        f"[Workflow-{self.workflow_id}] 节点执行成功 | workflow_run_id={self.workflow_run_id} | node_id={node_id} | node_name={node_name} | 耗时={elapsed}s")
                    break
                except Exception as e:
                    elapsed = round(time.monotonic() - start_time, 3)
                    msg = f"{e.__class__.__name__}: {e}"
                    if attempt < max_retries and not self.canceled_event.is_set():
                        attempt += 1
                        logger.warning(
                            f"[Workflow-{self.workflow_id}] 节点执行失败，准备重试 | workflow_run_id={self.workflow_run_id} | node_id={node_id} | node_name={node_name} | "
                            f"attempt={attempt}/{max_retries} | delay={retry_delay}s | error={msg}"
                        )
                        # 在重试等待期间，如果全局超时触发取消，sleep会被打断并抛出CancelledError
                        await asyncio.sleep(retry_delay)
                        continue

                    logger.error(
                        f"[Workflow-{self.workflow_id}] 节点执行最终失败 | workflow_run_id={self.workflow_run_id} | node_id={node_id} | node_name={node_name} | 耗时={elapsed}s | error={msg}",
                        exc_info=e if log_verbose else None)
                    node_context = self.context.get(node_id, {})
                    if "outputs" not in node_context:
                        node_context["outputs"] = {}

                    if isinstance(e, ChatBusinessException) and e.__cause__:
                        node_context["outputs"]["error_info"] = str(e.__cause__)
                    else:
                        node_context["outputs"]["error_info"] = msg
                    error_edges = [e for e in self.successors.get(node_id, []) if e.get("is_error_edge")]
                    if error_handler == "error_edges" and error_edges:
                        response_node_result.update(node_context)
                        self.queue.put_nowait(response_node_result)
                        self.state["__workflow_error__"] = {"node_id": node_id, "error_msg": msg}
                        self.node_done_events[node_id].set()
                        exclude_nodes = []
                        for edge in error_edges:
                            target_node_id = edge.get("target")
                            exclude_nodes.append(target_node_id)
                            await self._create_task_with_output(node_id=target_node_id)
                        self._propagate_skip(node_id, exclude_nodes=exclude_nodes)
                        return
                    elif error_handler == "continue":
                        default_outputs = node.get("default_outputs", [])
                        default_output_map = {d.get("name"): d.get("value") for d in default_outputs}
                        node_context["outputs"].update(default_output_map)
                        response_node_result.update(node_context)
                        self.queue.put_nowait(response_node_result)
                        break
                    else:
                        response_node_result.update(node_context)
                        self.queue.put_nowait(response_node_result)
                        self.node_done_events[node_id].set()
                        self.canceled_event.set()
                        self._propagate_skip(node_id)
                        return

            # 正常执行完毕（或静默失败完毕），唤醒下游
            self.node_done_events[node_id].set()
            for edge in self.successors[node_id]:
                target = edge.get("target")
                if edge.get("is_error_edge") is True:
                    self._propagate_skip(target)
                    continue
                if node.get("type") == "IfElseComponent" and edge.get("condition"):
                    if self.results.get(node_id, {}).get("condition_result") != edge.get("condition"):
                        self.skipped_nodes.add(target)
                        self.node_done_events[target].set()
                        self._propagate_skip(target)
                        continue
                target_node_id = edge.get("target")
                await self._create_task_with_output(node_id=target_node_id)
        except Exception as e:
            await self.cancel()
            raise e
        finally:
            if self.pubsub:
                await self.pubsub.publish(topic=node_id, event=SSEEvent(SSEEventType.DONE, topic=node_id, data=None))
            self.tasks_queue.task_done()

    async def _create_task(self, node_id: str):
        target_node = self.nodes.get(node_id)
        if not target_node.get("executed"):
            async with self.node_lock:
                if not target_node.get("executed"):
                    target_node["executed"] = True
                    task = asyncio.create_task(self._execute_node(target_node))
                    self.tasks_queue.put_nowait(task)

    async def _create_task_with_output(self, node_id: str):
        await self._create_task(node_id)
        if self.pubsub:
            for edge in self.successors[node_id]:
                target = edge.get("target")
                node = self.nodes.get(target)
                if node.get("type") in ["ChatOutputComponent", "ChatStructureOutputComponent"]:
                    await self._create_task(node_id=target)

    async def cancel(self):
        """取消所有运行中的任务"""
        if not self.canceled_event.is_set():
            self.canceled_event.set()
            if self.pubsub:
                await self.pubsub.stop()
