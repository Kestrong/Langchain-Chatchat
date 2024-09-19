import urllib

from fastapi import Body, Query

from configs import EMBEDDING_MODEL, logger, log_verbose, DEFAULT_VS_TYPE
from server.db.repository.knowledge_base_repository import list_kbs_from_db
from server.knowledge_base.kb_service.base import KBServiceFactory
from server.knowledge_base.utils import validate_kb_name
from server.memory.message_i18n import Message_I18N
from server.memory.token_info_memory import is_english
from server.utils import BaseResponse, PageResponse, Page


def list_kbs(page_size: int = Query(default=10, description="分页大小"),
             page_num: int = Query(default=1, description="页数"),
             keyword: str = Query(None, allow_inf_nan=True, description="模糊搜索向量库名称"),
             ) -> PageResponse:
    # Get List of Knowledge Base
    data, total = list_kbs_from_db(page_size=page_size, page_num=page_num, keyword=keyword)
    if is_english():
        for d in data:
            d["kb_name_cn"] = d.get("kb_name")
    return PageResponse(data=Page(records=data, total=total))


def create_kb(knowledge_base_name: str = Body(max_length=50, examples=["samples"],
                                              description="向量库的英文名称，只允许英文、数字和下划线"),
              knowledge_base_name_cn: str = Body(max_length=50, examples=["samples知识库"],
                                                 description="向量库的中文名称"),
              knowledge_base_info: str = Body(None, max_length=200,
                                              description="向量库的介绍，方便对话时模型进行智能匹配"),
              vector_store_type: str = Body(DEFAULT_VS_TYPE, max_length=50, description="向量库类型"),
              embed_model: str = Body(EMBEDDING_MODEL, max_length=50, description="向量化使用的嵌入模型"),
              ) -> BaseResponse:
    # Create selected knowledge base
    if knowledge_base_name is None or knowledge_base_name.strip() == "":
        return BaseResponse(code=500, msg=Message_I18N.API_PARAM_NOT_PRESENT.value.format(
            name="knowledge_base_name"))
    if not validate_kb_name(knowledge_base_name) or knowledge_base_name.lower() == 'temp':
        return BaseResponse(code=500, msg="Invalid Knowledge Base Name")

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is not None:
        return BaseResponse(code=500, msg=Message_I18N.API_KB_EXIST.value.format(kb_name=knowledge_base_name))

    kb = KBServiceFactory.get_service(knowledge_base_name, vector_store_type, embed_model)
    try:
        if knowledge_base_info is not None and knowledge_base_info.strip() != "":
            kb.kb_info = knowledge_base_info
        if knowledge_base_name_cn is not None and knowledge_base_name_cn.strip() != "":
            kb.kb_name_cn = knowledge_base_name_cn
        kb.create_kb()
    except Exception as e:
        msg = f"创建知识库出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_CREATE_ERROR.value)

    return BaseResponse(code=200, data={"knowledge_base_name": knowledge_base_name})


def delete_kb(
        knowledge_base_name: str = Body(..., examples=["samples"])
) -> BaseResponse:
    # Delete selected knowledge base
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=500, msg="Invalid knowledge base name")
    knowledge_base_name = urllib.parse.unquote(knowledge_base_name)

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)

    if kb is None:
        return BaseResponse(code=500, msg=Message_I18N.API_KB_NOT_EXIST.value.format(kb_name=knowledge_base_name))

    try:
        status = kb.clear_vs()
        status = kb.drop_kb()
        if status:
            return BaseResponse(code=200, data={})
    except Exception as e:
        msg = f"删除知识库时出现意外： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_DELETE_ERROR.value)

    return BaseResponse(code=500, msg=Message_I18N.API_DELETE_ERROR.value)
