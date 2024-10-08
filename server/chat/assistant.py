from collections import OrderedDict
from typing import Dict, Any

from fastapi import Body, Query

from configs import LLM_MODELS, HISTORY_LEN
from configs.basic_config import logger, log_verbose
from server.db.repository import get_model_metadata_from_db
from server.db.repository.assistant_repository import add_assistant_to_db, update_assistant_to_db, \
    delete_assistant_from_db, get_assistant_from_db, get_assistant_detail_from_db
from server.memory.message_i18n import Message_I18N
from server.memory.token_info_memory import is_english
from server.utils import BaseResponse


def create_assistant(avatar: str = Body(None, description="头像图标"),
                     name: str = Body(description="助手名称"),
                     name_en: str = Body(default="", description="助手英文名称"),
                     code: str = Body(description="助手编码"),
                     prompt: str = Body(None, description="提示词模板"),
                     model_name: str = Body(LLM_MODELS[0], description="LLM 模型名称。"),
                     prologue: str = Body(None, description="开场白"),
                     knowledge_base_ids: str = Body(None, description="关联的知识库id，例如:1,2,3"),
                     force_feedback: str = Body('0BF', description="是否强制点赞后才能继续对话,0BT是/0BF否，默认0BF"),
                     history_len: int = Body(HISTORY_LEN, description="历史对话轮数，建议0-10"),
                     top_k: int = Body(HISTORY_LEN, description="知识库匹配条数"),
                     score_threshold: int = Body(HISTORY_LEN, description="知识库匹配阈值，建议0.00-1.00"),
                     sort_id: int = Body(0, description="排序顺序,值越小越靠前"),
                     model_config: Dict[str, Any] = Body({}, description="模型附加配置"),
                     tool_config: Dict[str, Any] = Body({}, description="工具配置"),
                     extra: Dict[str, Any] = Body({}, description="附加属性")) -> BaseResponse:
    try:
        assistant_id = add_assistant_to_db(name=name, name_en=name_en, code=code, avatar=avatar, prompt=prompt,
                                           model_name=model_name, prologue=prologue,
                                           knowledge_base_ids=knowledge_base_ids, force_feedback=force_feedback,
                                           history_len=history_len, top_k=top_k, score_threshold=score_threshold,
                                           extra=extra, model_config=model_config,
                                           tool_config=tool_config, sort_id=sort_id)
    except Exception as e:
        msg = f"创建助手出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_CREATE_ERROR.value)
    return BaseResponse(code=200, data={'assistant_id': assistant_id})


def update_assistant(id: int = Body(description="助手id"),
                     name: str = Body(description="助手名称"),
                     name_en: str = Body(default="", description="助手英文名称"),
                     code: str = Body(description="助手编码"),
                     avatar: str = Body(None, description="头像图标"),
                     prompt: str = Body(None, description="提示词模板"),
                     model_name: str = Body(LLM_MODELS[0], description="LLM 模型名称。"),
                     prologue: str = Body(None, description="开场白"),
                     knowledge_base_ids: str = Body(None, description="关联的知识库id，例如:1,2,3"),
                     force_feedback: str = Body('0BF', description="是否强制点赞后才能继续对话,0BT是/0BF否，默认0BF"),
                     history_len: int = Body(HISTORY_LEN, description="历史对话轮数，建议0-10"),
                     top_k: int = Body(HISTORY_LEN, description="知识库匹配条数"),
                     score_threshold: int = Body(HISTORY_LEN, description="知识库匹配阈值，建议0.00-1.00"),
                     sort_id: int = Body(0, description="排序顺序,值越小越靠前"),
                     model_config: Dict[str, Any] = Body(None, description="模型附加配置"),
                     tool_config: Dict[str, Any] = Body({}, description="工具配置"),
                     extra: Dict[str, Any] = Body(None, description="附加属性")) -> BaseResponse:
    try:
        assistant_id = update_assistant_to_db(assistant_id=id, name=name, name_en=name_en, code=code, avatar=avatar,
                                              prompt=prompt, model_name=model_name, prologue=prologue,
                                              model_config=model_config, knowledge_base_ids=knowledge_base_ids,
                                              force_feedback=force_feedback, history_len=history_len, top_k=top_k,
                                              score_threshold=score_threshold, extra=extra,
                                              tool_config=tool_config, sort_id=sort_id)
    except Exception as e:
        msg = f"修改助手出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_UPDATE_ERROR.value)
    return BaseResponse(code=200, data={'assistant_id': assistant_id})


def delete_assistant(id: int = Query(description="助手id")) -> BaseResponse:
    try:
        assistant_id = delete_assistant_from_db(assistant_id=id)
    except Exception as e:
        msg = f"删除助手出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_DELETE_ERROR.value)
    return BaseResponse(code=200, data={'assistant_id': assistant_id})


def get_assistants(page: int = Query(default=1, description="页码"),
                   size: int = Query(default=100, description="分页大小"),
                   group: bool = Query(default=False, description="是否按模型进行分组"),
                   keyword: str = Query(default=None, description="关键字搜索")) -> BaseResponse:
    assistants, total = get_assistant_from_db(page=page, size=size, keyword=keyword)
    result = OrderedDict()
    english = is_english()
    MODEL_METADATA = get_model_metadata_from_db()
    for assistant in assistants:
        if english and assistant.get("name_en"):
            assistant["name"] = assistant["name_en"]
        label = model_name = assistant['model_name']
        icon = ""
        if label in MODEL_METADATA:
            label = MODEL_METADATA[model_name].get('label_en' if english else 'label')
            icon = MODEL_METADATA[model_name].get('icon')
        if group:
            group = result.setdefault(label, {"label": label, "icon": icon, "assistants": []})
            group['assistants'].append(assistant)
        else:
            assistant["model_label"] = label
    if group:
        return BaseResponse(code=200, data={'groups': [v for v in result.values()], 'total': total})
    return BaseResponse(code=200, data={'assistants': assistants, 'total': total})


def get_assistant_detail(id: int = Query(description="助手id")) -> BaseResponse:
    assistant = get_assistant_detail_from_db(assistant_id=id)
    return BaseResponse(code=200, data={'assistant': assistant})
