from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy import func

from configs import logger
from server.memory.token_info_memory import get_token_info
from server.db.models.knowledge_base_model import KnowledgeBaseModel
from server.db.models.knowledge_file_model import KnowledgeFileModel, FileDocModel
from server.db.repository import get_kb_detail
from server.db.session import with_session
from server.knowledge_base.utils import KnowledgeFile


@with_session
def list_file_doc_model_by_kb_name_and_file_name(session,
                                                 kb_name: str,
                                                 file_name: str,
                                                 query: Any,
                                                 metadata=None,
                                                 ):
    '''
    列出某知识库某文件对应的所有Document
    '''
    kb = get_kb_detail(kb_name)
    if kb is None:
        return None
    kb_id = kb["id"]
    filters = [FileDocModel.kb_id == kb_id]
    if file_name:
        file = get_file_detail_by_kb_id(kb_id, file_name)
        if len(file) == 0:
            return None
        filters.append(FileDocModel.file_id == file["id"])
    if metadata is not None:
        for k, v in metadata.items():
            filters.append(FileDocModel.meta_data[k].as_string() == str(v))
    return session.query(query).filter(*filters)


def list_file_num_docs_id_by_kb_name_and_file_name(kb_name: str,
                                                   file_name: str,
                                                   ) -> List[int]:
    '''
    列出某知识库某文件对应的所有Document的id。
    返回形式：[str, ...]
    '''
    if kb_name is None or file_name is None:
        return list()
    docs = list_file_doc_model_by_kb_name_and_file_name(kb_name=kb_name, file_name=file_name,
                                                        query=FileDocModel.doc_id)
    if docs is None:
        return list()
    return [int(doc.doc_id) for doc in docs.all()]


@with_session
def list_docs_from_db(session,
                      kb_name: str,
                      file_name: str = None,
                      metadata=None,
                      ) -> List[Dict]:
    '''
    列出某知识库某文件对应的所有Document。
    返回形式：[{"id": str, "metadata": dict}, ...]
    '''
    if metadata is None:
        metadata = {}
    docs = list_file_doc_model_by_kb_name_and_file_name(kb_name=kb_name, file_name=file_name,
                                                        query=FileDocModel,
                                                        metadata=metadata)
    if docs is None:
        return list()
    return [{"id": x.doc_id, "metadata": x.meta_data} for x in docs.all()]


@with_session
def delete_docs_from_db(session,
                        kb_id: int,
                        file_id: int,
                        ) -> List[Dict]:
    '''
    删除某知识库某文件对应的所有Document，并返回被删除的Document。
    返回形式：[{"id": str, "metadata": dict}, ...]
    '''
    query = session.query(FileDocModel).filter(FileDocModel.kb_id == kb_id, FileDocModel.file_id == file_id)
    query.delete(synchronize_session=False)
    session.commit()
    return list()


@with_session
def add_docs_to_db(session,
                   kb_id: int,
                   file_id: int,
                   doc_infos: List[Dict]):
    '''
    将某知识库某文件对应的所有Document信息添加到数据库。
    doc_infos形式：[{"id": str, "metadata": dict}, ...]
    '''
    # ! 这里会出现doc_infos为None的情况，需要进一步排查
    if doc_infos is None:
        logger.error("输入的server.db.repository.knowledge_file_repository.add_docs_to_db的doc_infos参数为None")
        return False
    begin = datetime.utcnow()
    docs = []
    for d in doc_infos:
        obj = FileDocModel(
            kb_id=kb_id,
            file_id=file_id,
            doc_id=d["id"],
            meta_data=d["metadata"],
        )
        docs.append(obj)
    session.bulk_save_objects(docs)
    end = datetime.utcnow()
    logger.debug(f"bulk insert {len(doc_infos)} file_docs to db cost {(end - begin).total_seconds()} seconds")
    return True


@with_session
def count_files_from_db(session, kb_name: str) -> int:
    kb = get_kb_detail(kb_name)
    if kb is None:
        return 0
    return session.query(func.count(KnowledgeFileModel.id)).filter(KnowledgeFileModel.kb_id == kb["id"]).scalar()


@with_session
def list_files_from_db(session, kb_name,
                       page_size: int = 1000,
                       page_num: int = 1,
                       keyword: str = None,
                       create_time_begin: datetime = None,
                       create_time_end: datetime = None,
                       only_name: bool = True):
    kb = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name == kb_name).first()
    if kb is None:
        if only_name:
            return list()
        return list(), 0
    page_size = abs(page_size)
    page_num = max(page_num, 1)
    offset = (page_num - 1) * page_size
    filters = [KnowledgeFileModel.kb_id == kb.id]
    if keyword is not None and keyword.strip() != "":
        filters.append(KnowledgeFileModel.file_name.like(f"%{keyword}%"))

    if create_time_begin is not None:
        filters.append(KnowledgeFileModel.create_time >= create_time_begin)

    if create_time_end is not None:
        filters.append(KnowledgeFileModel.create_time <= create_time_end)

    if only_name:
        files = session.query(KnowledgeFileModel.file_name).filter(*filters).all()
        return [f.file_name for f in files]
    else:
        files = session.query(KnowledgeFileModel).filter(*filters).order_by(
            KnowledgeFileModel.create_time.desc()).offset(offset).limit(page_size).all()
        docs = [f.dict() for f in files]
        total = session.query(func.count(KnowledgeFileModel.id)).filter(*filters).scalar()
        return docs, total


@with_session
def add_file_to_db(session,
                   kb_file: KnowledgeFile,
                   docs_count: int = 0,
                   custom_docs: bool = False,
                   doc_infos: List[Dict] = [],  # 形式：[{"id": str, "metadata": dict}, ...]
                   ):
    kb = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_file.kb_name).first()
    if kb:
        # 如果已经存在该文件，则更新文件信息与版本号
        existing_file: KnowledgeFileModel = (session.query(KnowledgeFileModel)
                                             .filter(KnowledgeFileModel.kb_id == kb.id,
                                                     KnowledgeFileModel.file_name == kb_file.filename)
                                             .first())
        mtime = kb_file.get_mtime()
        size = kb_file.get_size()

        if existing_file:
            file_id = existing_file.id
            existing_file.file_mtime = mtime
            existing_file.file_size = size
            existing_file.docs_count = docs_count
            existing_file.custom_docs = custom_docs
            existing_file.file_version += 1
        # 否则，添加新文件
        else:
            user_id = get_token_info().get("userId")
            new_file = KnowledgeFileModel(
                file_name=kb_file.filename,
                file_ext=kb_file.ext,
                kb_id=kb.id,
                document_loader_name=kb_file.document_loader_name,
                text_splitter_name=kb_file.text_splitter_name or "SpacyTextSplitter",
                file_mtime=mtime,
                file_size=size,
                docs_count=docs_count,
                custom_docs=custom_docs,
                create_by=user_id
            )
            kb.file_count += 1
            session.add(new_file)
            session.flush()
            file_id = new_file.id
        session.commit()
        add_docs_to_db(kb_id=kb.id, file_id=file_id, doc_infos=doc_infos)
    return True


@with_session
def delete_file_from_db(session, kb_file: KnowledgeFile):
    kb = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_file.kb_name).first()
    if kb is None:
        return True
    existing_file = (session.query(KnowledgeFileModel)
                     .filter(KnowledgeFileModel.file_name == kb_file.filename,
                             KnowledgeFileModel.kb_id == kb.id)
                     .first())
    if existing_file:
        session.delete(existing_file)
        delete_docs_from_db(kb_id=kb.id, file_id=existing_file.id)

        kb.file_count -= 1
        session.commit()
    return True


@with_session
def delete_files_from_db(session, knowledge_base_name: str):
    kb = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name == knowledge_base_name).first()
    if kb is None:
        return True
    session.query(KnowledgeFileModel).filter(KnowledgeFileModel.kb_id == kb.id).delete(
        synchronize_session=False)
    session.query(FileDocModel).filter(FileDocModel.kb_id == kb.id).delete(
        synchronize_session=False)
    kb.file_count = 0

    session.commit()
    return True


@with_session
def file_exists_in_db(session, kb_file: KnowledgeFile):
    kb = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name == kb_file.kb_name).first()
    if kb is None:
        return False
    existing_file = (session.query(KnowledgeFileModel)
                     .filter(KnowledgeFileModel.file_name == kb_file.filename,
                             KnowledgeFileModel.kb_id == kb.id)
                     .first())
    return True if existing_file else False


@with_session
def get_file_detail(session, kb_name: str, filename: str) -> dict:
    kb = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.kb_name == kb_name).first()
    if kb is None:
        return {}
    file: KnowledgeFileModel = (session.query(KnowledgeFileModel)
                                .filter(KnowledgeFileModel.file_name == filename,
                                        KnowledgeFileModel.kb_id == kb.id)
                                .first())
    if file:
        return file.dict()
    else:
        return {}


@with_session
def get_file_detail_by_kb_id(session, kb_id: int, filename: str) -> dict:
    file: KnowledgeFileModel = (session.query(KnowledgeFileModel)
                                .filter(KnowledgeFileModel.file_name == filename,
                                        KnowledgeFileModel.kb_id == kb_id)
                                .first())
    if file is None:
        return {}
    return file.dict()
