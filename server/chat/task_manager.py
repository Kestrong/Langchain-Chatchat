import threading
from asyncio import Task
from typing import Optional, Dict

from fastapi import Query

from configs.basic_config import logger
from server.memory.message_i18n import Message_I18N
from server.utils import BaseResponse


class TaskManager:

    def __init__(self):
        self.task_map: Dict[str, Task] = {}
        self.lock = threading.RLock()

    def put(self, task_id: str, task: Task):
        if task is not None:
            with self.lock:
                self.task_map[task_id] = task

    def get(self, task_id: str) -> Optional[Task]:
        with self.lock:
            return self.task_map.get(task_id)

    def remove(self, task_id: str):
        with self.lock:
            self.task_map.pop(task_id, None)
            if len(self.task_map) > 1000:
                keys = []
                for k, v in self.task_map.items():
                    if v.done():
                        keys.append(k)
                for key in keys:
                    self.task_map.pop(key, None)


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
