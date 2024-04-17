import urllib
from server.utils import BaseResponse, PageResponse, Page
from server.knowledge_base.utils import validate_kb_name
from server.knowledge_base.kb_service.base import KBServiceFactory
from server.db.repository.knowledge_base_repository import list_kbs_from_db
from configs import EMBEDDING_MODEL, logger, log_verbose, DEFAULT_VS_TYPE
from fastapi import Body, Query


def list_kbs(page_size: int = Query(default=10, description="分页大小"),
             page_num: int = Query(default=1, description="页数"),
             keyword: str = Query(None, allow_inf_nan=True, description="模糊搜索向量库名称"),
             ) -> PageResponse:
    # Get List of Knowledge Base
    data, total = list_kbs_from_db(page_size=page_size, page_num=page_num, keyword=keyword)
    return PageResponse(data=Page(records=data, total=total))


def create_kb(knowledge_base_name: str = Body(max_length=50, examples=["samples"], description="向量库的英文名称，只允许英文、数字和下划线"),
              knowledge_base_name_cn: str = Body(max_length=50, examples=["samples知识库"], description="向量库的中文名称"),
              knowledge_base_info: str = Body(None, max_length=200, description="向量库的介绍，方便对话时模型进行智能匹配"),
              vector_store_type: str = Body(DEFAULT_VS_TYPE, max_length=50, description="向量库类型"),
              embed_model: str = Body(EMBEDDING_MODEL, max_length=50, description="向量化使用的嵌入模型"),
              ) -> BaseResponse:
    # Create selected knowledge base
    if knowledge_base_name is None or knowledge_base_name.strip() == "" or knowledge_base_name_cn is None or knowledge_base_name_cn.strip() == "":
        return BaseResponse(code=404, msg="知识库名称不能为空，请重新填写知识库名称")
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Invalid Knowledge Base Name")

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is not None:
        return BaseResponse(code=404, msg=f"已存在同名知识库 {knowledge_base_name}")

    kb = KBServiceFactory.get_service(knowledge_base_name, vector_store_type, embed_model)
    try:
        if knowledge_base_info is not None and knowledge_base_info.strip() != "":
            kb.kb_info = knowledge_base_info
        kb.kb_name_cn = knowledge_base_name_cn
        kb.create_kb()
    except Exception as e:
        msg = f"创建知识库出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)

    return BaseResponse(code=200, msg=f"已新增知识库 {knowledge_base_name}")


def delete_kb(
        knowledge_base_name: str = Body(..., examples=["samples"])
) -> BaseResponse:
    # Delete selected knowledge base
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")
    knowledge_base_name = urllib.parse.unquote(knowledge_base_name)

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)

    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {knowledge_base_name}")

    try:
        status = kb.clear_vs()
        status = kb.drop_kb()
        if status:
            return BaseResponse(code=200, msg=f"成功删除知识库 {knowledge_base_name}")
    except Exception as e:
        msg = f"删除知识库时出现意外： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)

    return BaseResponse(code=500, msg=f"删除知识库失败 {knowledge_base_name}")
