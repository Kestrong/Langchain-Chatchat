import datetime

from sqlalchemy import func

from common.exceptions import ChatBusinessException
from server.db.models.knowledge_base_model import KnowledgeBaseModel
from server.db.session import with_session
from server.memory.message_i18n import Message_I18N
from server.memory.token_info_memory import get_token_info


@with_session
def add_kb_to_db(session, kb_name, kb_name_cn, kb_info, kb_type, tag, vs_type, embed_model, update=True):
    # 创建知识库实例
    kb_cn = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name_cn == kb_name_cn).first()
    if kb_cn and not update:
        raise ChatBusinessException(Message_I18N.API_KB_EXIST.value.format(kb_name=kb_name_cn))
    kb_en = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name == kb_name).first()
    if kb_en and not update:
        raise ChatBusinessException(Message_I18N.API_KB_EXIST.value.format(kb_name=kb_name))
    if kb_en and update:
        kb_en.kb_info = kb_info if kb_info is not None else kb_en.kb_info
        kb_en.kb_name_cn = kb_name_cn if kb_name_cn is not None else kb_en.kb_name_cn
    else:
        token_info = get_token_info()
        user_id = token_info.get("userId")
        kb = KnowledgeBaseModel(kb_name=kb_name, kb_name_cn=kb_name_cn, kb_info=kb_info, vs_type=vs_type,
                                embed_model=embed_model, create_by=user_id, update_by=user_id, kb_type=kb_type,
                                update_time=datetime.datetime.now(), tag=tag, tenant_id=token_info.get("tenantId"))
        session.add(kb)
    return True


@with_session
def update_kb_to_db(session, kb_name, kb_name_cn, kb_info, tag):
    kb = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name == kb_name).first()
    if not kb:
        raise ChatBusinessException(Message_I18N.API_KB_NOT_EXIST.value.format(kb_name=kb_name))
    kb_cn = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name_cn == kb_name_cn).first()
    if kb_cn and kb_cn.id != kb.id:
        raise ChatBusinessException(Message_I18N.API_KB_EXIST.value.format(kb_name=kb_name_cn))
    kb.kb_info = kb_info if kb_info is not None else kb.kb_info
    kb.kb_name_cn = kb_name_cn if kb_name_cn is not None else kb.kb_name_cn
    kb.tag = tag if tag is not None else kb.tag
    kb.update_time = datetime.datetime.now()
    kb.update_by = get_token_info().get("userId")
    return True


@with_session
def list_kbs_from_db(session, page_size: int = 10, page_num: int = 1, kb_type: str = None, tag: str = None,
                     keyword: str = None, min_file_count: int = -1, all_kbs: bool = False):
    page_size = min(abs(page_size), 1000)
    page_num = max(page_num, 1)
    offset = (page_num - 1) * page_size
    filters = [KnowledgeBaseModel.file_count > min_file_count]
    tenant_id = get_token_info().get("tenantId")
    if tenant_id is not None and tenant_id != "":
        filters.append(KnowledgeBaseModel.tenant_id == tenant_id)
    if keyword is not None and keyword.strip() != "":
        filters.append(KnowledgeBaseModel.kb_name_cn.like(f"%{keyword}%"))
    if kb_type is not None and kb_type.strip() != "":
        filters.append(KnowledgeBaseModel.kb_type == kb_type)
    if tag is not None and tag.strip() != "":
        filters.append(KnowledgeBaseModel.tag == tag)
    if not all_kbs:
        kbs = session.query(KnowledgeBaseModel).filter(*filters).offset(offset).limit(page_size).all()
        total = session.query(func.count(KnowledgeBaseModel.id)).filter(*filters).scalar()
    else:
        kbs = session.query(KnowledgeBaseModel).filter(*filters).all()
        total = len(kbs)
    kbs = [kb.dict() for kb in kbs]
    return kbs, total


@with_session
def kb_exists(session, kb_name):
    kb = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name == kb_name).first()
    status = True if kb else False
    return status


@with_session
def load_kb_from_db(session, kb_name):
    kb = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name == kb_name).first()
    if kb:
        kb_name, vs_type, embed_model = kb.kb_name, kb.vs_type, kb.embed_model
    else:
        kb_name, vs_type, embed_model = None, None, None
    return kb_name, vs_type, embed_model


@with_session
def delete_kb_from_db(session, kb_name):
    kb = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name == kb_name).first()
    if kb:
        session.delete(kb)
    return True


@with_session
def get_kb_detail(session, kb_name: str) -> dict:
    kb: KnowledgeBaseModel = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name == kb_name).first()
    if kb:
        return kb.dict()
    else:
        return {}


@with_session
def get_kb_detail_by_id(session, kb_id: int) -> dict:
    kb: KnowledgeBaseModel = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.id == kb_id).first()
    if kb:
        return kb.dict()
    else:
        return {}
