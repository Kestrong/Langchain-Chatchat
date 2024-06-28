from asyncio import Task

from fastapi import Query

from configs.basic_config import logger
from server.utils import BaseResponse

task_map = dict({})


def put(task_id: str, task: Task):
    if task is not None:
        task_map[task_id] = task


def get(task_id: str) -> [Task, None]:
    if task_id in task_map:
        return task_map[task_id]
    return None


def remove(task_id: str):
    if task_id in task_map:
        del task_map[task_id]


def stop(task_id: str = Query(description="任务id")) -> BaseResponse:
    task = get(task_id)
    if task is not None:
        try:
            task.cancel()
        except Exception as e:
            logger.error(e)
        finally:
            remove(task_id)
        return BaseResponse(code=200, data={'task_id': task_id})
    return BaseResponse(code=500, msg=f'task[{task_id}] is not exist')
