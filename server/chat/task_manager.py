import threading
from asyncio import Task
from typing import Dict

from fastapi import Query

from configs.basic_config import logger
from server.memory.message_i18n import Message_I18N
from server.utils import BaseResponse


class TaskManager:
    lock = threading.Lock()

    def __init__(self):
        self.task_map: Dict[str, Task] = dict({})
        self.count_down = 10000
        self.count_up = 0

    def put(self, task_id: str, task: Task):
        if task is not None:
            self.task_map[task_id] = task
            self.count_up += 1
            if self.count_up > self.count_down:
                with self.lock:
                    if self.count_up > self.count_down:
                        keys = []
                        for k, v in self.task_map.items():
                            if v.done():
                                keys.append(k)
                        for key in keys:
                            self.remove(key)
                        self.count_up = 0

    def get(self, task_id: str) -> [Task, None]:
        if task_id in self.task_map:
            return self.task_map[task_id]
        return None

    def remove(self, task_id: str):
        if task_id in self.task_map:
            del self.task_map[task_id]


task_manager = TaskManager()


def stop(task_id: str = Query(description="任务id")) -> BaseResponse:
    task = task_manager.get(task_id)
    if task is not None:
        try:
            task.cancel()
        except Exception as e:
            logger.error(e)
        finally:
            task_manager.remove(task_id)
        return BaseResponse(code=200, data={'task_id': task_id})
    return BaseResponse(code=500, msg=Message_I18N.API_TASK_NOT_EXIST.value.format(task_id=task_id))
