import urllib.parse

from fastapi import Body, Query
from shortuuid import uuid

from common.exceptions import ChatBusinessException
from configs import EMBEDDING_MODEL, logger, log_verbose, DEFAULT_VS_TYPE
from server.db.repository.knowledge_base_repository import list_kbs_from_db, get_kb_detail as get_kb_detail_by_name, \
    update_kb_to_db
from server.knowledge_base.kb_service.base import KBServiceFactory
from server.knowledge_base.utils import validate_kb_name
from server.memory.message_i18n import Message_I18N
from server.utils import BaseResponse, PageResponse, Page


def list_kbs(page_size: int = Query(default=10, description="分页大小"),
             page_num: int = Query(default=1, description="页数"),
             knowledge_base_type: str = Query(None, description="知识库类型"),
             tag: str = Query(None, description="标签，使用场景"),
             keyword: str = Query(None, allow_inf_nan=True, description="模糊搜索知识库名称"),
             ) -> PageResponse:
    # Get List of Knowledge Base
    data, total = list_kbs_from_db(page_size=page_size, page_num=page_num, keyword=keyword, kb_type=knowledge_base_type,
                                   tag=tag)
    return PageResponse(data=Page(records=data, total=total))


def get_kb_detail(kb_name: str = Query(default=None, description="知识库名称"), ) -> BaseResponse:
    data = get_kb_detail_by_name(kb_name)
    return BaseResponse(data=data)


def create_kb(knowledge_base_name: str = Body(None, max_length=50, examples=["samples"],
                                              description="向量库的英文名称，只允许英文、数字和下划线，一旦创建不允许修改"),
              knowledge_base_name_cn: str = Body(max_length=50, examples=["samples知识库"], description="知识库的名称"),
              knowledge_base_info: str = Body(None, max_length=200,
                                              description="向量库的介绍，方便对话时模型进行智能匹配"),
              vector_store_type: str = Body(DEFAULT_VS_TYPE, max_length=50, description="向量库类型"),
              embed_model: str = Body(EMBEDDING_MODEL, max_length=50, description="向量化使用的嵌入模型"),
              knowledge_base_type: str = Body(None, max_length=50, description="知识库类型"),
              tag: str = Body(None, max_length=50, description="标签，使用场景"),
              ) -> BaseResponse:
    # Create selected knowledge base
    if knowledge_base_name is None or knowledge_base_name.strip() == "":
        knowledge_base_name = str(uuid())
    if not validate_kb_name(knowledge_base_name) or knowledge_base_name.lower() == 'temp':
        return BaseResponse(code=500, msg="Invalid Knowledge Base Name")
    if knowledge_base_name_cn is None or knowledge_base_name_cn.strip() == "":
        return BaseResponse(code=500, msg=Message_I18N.API_PARAM_NOT_PRESENT.value.format(
            name="knowledge_base_name_cn"))

    kb = KBServiceFactory.get_service(knowledge_base_name, vector_store_type, embed_model)
    try:
        if knowledge_base_info is not None and knowledge_base_info.strip() != "":
            kb.kb_info = knowledge_base_info
        kb.kb_name_cn = knowledge_base_name_cn
        kb.kb_type = knowledge_base_type
        kb.tag = tag
        kb.create_kb(update=False)
    except ChatBusinessException as e:
        logger.error(f"{e}")
        return BaseResponse(code=500, msg=f"{e}")
    except Exception as e:
        msg = f"创建知识库出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}', exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_CREATE_ERROR.value)

    return BaseResponse(code=200, data=get_kb_detail_by_name(kb_name=knowledge_base_name))


def update_info(
        knowledge_base_name: str = Body(max_length=50, examples=["samples"], description="不允许修改"),
        knowledge_base_name_cn: str = Body(max_length=50, examples=["samples知识库"]),
        kb_info: str = Body(..., description="知识库介绍", examples=["这是一个知识库"]),
        tag: str = Body(None, max_length=50, description="标签，使用场景"),
):
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=500, msg="Invalid Knowledge Base Name")
    try:
        update_kb_to_db(knowledge_base_name, knowledge_base_name_cn, kb_info, tag)
    except ChatBusinessException as e:
        logger.error(f"{e}")
        return BaseResponse(code=500, msg=f"{e}")
    except Exception as e:
        msg = f"修改知识库出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}', exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_UPDATE_ERROR.value)
    return BaseResponse(code=200, msg=Message_I18N.COMMON_CALL_SUCCESS.value,
                        data=get_kb_detail_by_name(kb_name=knowledge_base_name))


def delete_kb(
        knowledge_base_name: str = Query(..., examples=["samples"])
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
        logger.error(f'{e.__class__.__name__}: {msg}', exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_DELETE_ERROR.value)

    return BaseResponse(code=500, msg=Message_I18N.API_DELETE_ERROR.value)
