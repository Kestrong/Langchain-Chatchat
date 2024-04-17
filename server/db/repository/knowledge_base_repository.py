from sqlalchemy import func

from server.db.models.knowledge_base_model import KnowledgeBaseModel
from server.db.session import with_session


@with_session
def add_kb_to_db(session, kb_name, kb_name_cn, kb_info, vs_type, embed_model):
    # 创建知识库实例
    kb = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name == kb_name).first()
    if not kb:
        kb_cn = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name_cn == kb_name_cn).first()
        if kb_cn is not None:
            raise Exception(f"已存在同名知识库 {kb_name_cn}")
        kb = KnowledgeBaseModel(kb_name=kb_name, kb_name_cn=kb_name_cn, kb_info=kb_info, vs_type=vs_type,
                                embed_model=embed_model)
        session.add(kb)
    else:  # update kb with new vs_type and embed_model
        if kb_name_cn is not None:
            kb_cn = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name_cn == kb_name_cn,
                                                             KnowledgeBaseModel.id != kb.id).first()
            if kb_cn is not None:
                raise Exception(f"已存在同名知识库 {kb_name_cn}")
        kb.kb_info = kb_info if kb_info is not None else kb.kb_info
        kb.vs_type = vs_type if vs_type is not None else kb.vs_type
        kb.kb_name_cn = kb_name_cn if kb_name_cn is not None else kb.kb_name_cn
        kb.embed_model = embed_model if embed_model is not None else kb.embed_model
    return True


@with_session
def list_kbs_from_db(session, page_size: int = 10, page_num: int = 1, keyword: str = None, min_file_count: int = -1
                     , all_kbs: bool = False):
    page_size = min(abs(page_size), 1000)
    page_num = max(page_num, 1)
    offset = (page_num - 1) * page_size
    filters = [KnowledgeBaseModel.file_count > min_file_count]
    if keyword is not None and keyword.strip() != "":
        filters.append(KnowledgeBaseModel.kb_name.like(f"%{keyword}%"))
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
