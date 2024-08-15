from fastapi import Body, Query

from configs import LLM_MODELS
from configs.basic_config import logger, log_verbose
from server.db.repository.assistant_repository import add_assistant_to_db, update_assistant_to_db, \
    delete_assistant_from_db, get_assistant_from_db, get_assistant_detail_from_db
from server.utils import BaseResponse


def create_assistant(avatar: str = Body(None, description="头像图标"),
                     name: str = Body(description="助手名称"),
                     prompt: str = Body(None, description="提示词模板"),
                     model_name: str = Body(LLM_MODELS[0], description="LLM 模型名称。"),
                     prologue: str = Body(None, description="开场白"),
                     knowledge_base_ids: str = Body(None, description="关联的知识库id，例如:1,2,3"),
                     force_feedback: str = Body('0BF', description="是否强制点赞后才能继续对话,0BT是/0BF否，默认0BF"),
                     sort_id: int = Body(0, description="排序顺序,值越小越靠前"),
                     model_config: dict = Body({}, description="模型附加配置"),
                     extra: dict = Body({}, description="附加属性")) -> BaseResponse:
    try:
        assistant_id = add_assistant_to_db(name=name, avatar=avatar, prompt=prompt, model_name=model_name,
                                           prologue=prologue, knowledge_base_ids=knowledge_base_ids,
                                           force_feedback=force_feedback, extra=extra,
                                           model_config=model_config, sort_id=sort_id)
    except Exception as e:
        msg = f"创建助手出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)
    return BaseResponse(code=200, data={'assistant_id': assistant_id})


def update_assistant(id: int = Body(description="助手id"),
                     name: str = Body(description="助手名称"),
                     avatar: str = Body(None, description="头像图标"),
                     prompt: str = Body(None, description="提示词模板"),
                     model_name: str = Body(LLM_MODELS[0], description="LLM 模型名称。"),
                     prologue: str = Body(None, description="开场白"),
                     knowledge_base_ids: str = Body(None, description="关联的知识库id，例如:1,2,3"),
                     force_feedback: str = Body('0BF', description="是否强制点赞后才能继续对话,0BT是/0BF否，默认0BF"),
                     sort_id: int = Body(0, description="排序顺序,值越小越靠前"),
                     model_config: dict = Body(None, description="模型附加配置"),
                     extra: dict = Body(None, description="附加属性")) -> BaseResponse:
    try:
        assistant_id = update_assistant_to_db(assistant_id=id, name=name, avatar=avatar, prompt=prompt,
                                              model_name=model_name, prologue=prologue, model_config=model_config,
                                              knowledge_base_ids=knowledge_base_ids, force_feedback=force_feedback,
                                              extra=extra, sort_id=sort_id)
    except Exception as e:
        msg = f"修改助手出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)
    return BaseResponse(code=200, data={'assistant_id': assistant_id})


def delete_assistant(id: int = Query(description="助手id")) -> BaseResponse:
    try:
        assistant_id = delete_assistant_from_db(assistant_id=id)
    except Exception as e:
        msg = f"删除助手出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)
    return BaseResponse(code=200, data={'assistant_id': assistant_id})


def get_assistants(page: int = Query(default=1, description="页码"),
                   size: int = Query(default=10, description="分页大小"),
                   keyword: str = Query(default=None, description="关键字搜索")) -> BaseResponse:
    assistants, total = get_assistant_from_db(page=page, size=size, keyword=keyword)
    return BaseResponse(code=200, data={'assistants': assistants, 'total': total})


def get_assistant_detail(id: int = Query(description="助手id")) -> BaseResponse:
    assistant = get_assistant_detail_from_db(assistant_id=id)
    return BaseResponse(code=200, data={'assistant': assistant})
