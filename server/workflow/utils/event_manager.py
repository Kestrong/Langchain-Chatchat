import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, AsyncIterator, Optional


class SSEEventType(str, Enum):
    """
    SSE 事件类型枚举。
    继承 str 是为了让它在序列化为 JSON 或拼接字符串时，自动变成字符串值。
    """
    DATA = "data"  # 数据事件
    HEARTBEAT = "heartbeat"  # 心跳事件
    DONE = "done"  # 结束事件
    ERROR = "error"  # 异常事件


@dataclass
class SSEEvent:
    event_type: SSEEventType
    topic: str
    data: Any


class AsyncSubscriber:

    def __init__(self, topic: str, queue: asyncio.Queue):
        self.topic = topic
        self.queue = queue

    async def stream(self) -> AsyncIterator[SSEEvent]:
        """
        业务层直接调用此方法获取消息流。
        自动处理了超时、断线重连、结束信号。
        """

        if self.queue is None:
            raise ValueError(f"Topic {self.topic} not subscribed or already consumed")

        while True:
            try:
                # 设置超时，防止协程永久挂起，方便外部取消
                event = await asyncio.wait_for(self.queue.get(), timeout=3.0)

                # 业务层收到结束信号，自动退出循环
                if event.event_type == SSEEventType.DONE:
                    break

                yield event  # 将消息抛给业务层处理

            except asyncio.TimeoutError:
                # 可以在此处向业务层发送心跳，或者继续等待
                yield SSEEvent(event_type=SSEEventType.HEARTBEAT, topic=self.topic, data=None)
                continue
            except asyncio.CancelledError:
                # 客户端断开连接或任务被取消
                break


class AsyncPubSub:
    def __init__(self, max_queue_size: int = 0):
        self.max_queue_size = max_queue_size
        # 存储主题对应的队列
        self._queues: Dict[str, asyncio.Queue] = {}
        # 记录哪些队列已经被消费者绑定（核心状态）
        self._bound_topics: set = set()
        # 保护状态变更的并发锁
        self._lock = asyncio.Lock()

    async def publish(self, topic: str, event: SSEEvent) -> bool:
        """
        发布消息。
        如果队列不存在，直接创建队列并放入消息（防丢数据）。
        """

        if topic not in self._queues:
            async with self._lock:
                # 如果队列不存在，直接创建（此时处于 unbound 状态）
                if topic not in self._queues:
                    self._queues[topic] = asyncio.Queue(maxsize=self.max_queue_size)

        queue = self._queues[topic]

        try:
            queue.put_nowait(event)
            return True
        except asyncio.QueueFull:
            return False

    async def subscribe(self, topic: str) -> Optional[AsyncSubscriber]:
        """
        订阅主题。
        无论队列是刚被 publish 创建的，还是还不存在，都保证只能被绑定一次。
        """
        async with self._lock:
            # 已经被绑定，其他消费者直接返回 None (False)
            if topic in self._bound_topics:
                return None

            # 队列不存在，创建队列
            if topic not in self._queues:
                self._queues[topic] = asyncio.Queue(maxsize=self.max_queue_size)

            # 绑定队列，并返回
            self._bound_topics.add(topic)
            return AsyncSubscriber(topic, self._queues[topic])

    async def unsubscribe(self, topic: str):
        """
        消费者断开连接时释放资源。
        注意：这里必须同时清理 _bound_topics 和 _queues，
        否则下一次 publish 会往一个没人消费的旧队列里塞数据。
        """
        async with self._lock:
            self._bound_topics.discard(topic)

    async def stop(self):
        """彻底清理队列，防止内存泄漏"""
        async with self._lock:
            for topic in list(self._queues.keys()):
                self._queues[topic].put_nowait(SSEEvent(event_type=SSEEventType.DONE, topic=topic, data=None))
