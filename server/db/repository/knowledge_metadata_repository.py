from sqlalchemy import func

from server.db.models.knowledge_base_model import KnowledgeBaseModel
from server.db.models.knowledge_metadata_model import SummaryChunkModel
from server.db.session import with_session
from typing import List, Dict


@with_session
def list_summary_from_db(session,
                         kb_id: int,
                         metadata: Dict = {},
                         ) -> List[Dict]:
    '''
    列出某知识库chunk summary。
    返回形式：[{"id": str, "summary_context": str, "doc_ids": str}, ...]
    '''

    docs = session.query(SummaryChunkModel).filter(SummaryChunkModel.kb_id == kb_id)

    for k, v in metadata.items():
        docs = docs.filter(SummaryChunkModel.meta_data[k].as_string() == str(v))

    return [{"id": x.id,
             "summary_context": x.summary_context,
             "summary_id": x.summary_id,
             "doc_ids": x.doc_ids,
             "metadata": x.meta_data} for x in docs.all()]


@with_session
def delete_summary_from_db(session,
                           kb_name: str
                           ) -> List[Dict]:
    '''
    删除知识库chunk summary，并返回被删除的Dchunk summary。
    返回形式：[{"id": str, "summary_context": str, "doc_ids": str}, ...]
    '''
    kb: KnowledgeBaseModel = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name == kb_name).first()
    if kb is None:
        return list()
    query = session.query(SummaryChunkModel).filter(SummaryChunkModel.kb_id == kb.id)
    query.delete(synchronize_session=False)
    session.commit()
    return list()


@with_session
def add_summary_to_db(session,
                      kb_name: str,
                      summary_infos: List[Dict]):
    '''
    将总结信息添加到数据库。
    summary_infos形式：[{"summary_context": str, "doc_ids": str}, ...]
    '''
    kb: KnowledgeBaseModel = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name == kb_name).first()
    if kb is None:
        return True
    for summary in summary_infos:
        obj = SummaryChunkModel(
            kb_id=kb.id,
            summary_context=summary["summary_context"],
            summary_id=summary["summary_id"],
            doc_ids=summary["doc_ids"],
            meta_data=summary["metadata"],
        )
        session.add(obj)

    session.commit()
    return True


@with_session
def count_summary_from_db(session, kb_name: str) -> int:
    kb: KnowledgeBaseModel = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name == kb_name).first()
    if kb is None:
        return 0
    return session.query(func.count(SummaryChunkModel.id)).filter(SummaryChunkModel.kb_id == kb.id).scalar()
