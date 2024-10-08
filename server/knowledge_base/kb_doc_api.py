import json
import mimetypes
import urllib
from datetime import datetime
from typing import List, Dict
from urllib.parse import quote

from fastapi import File, Form, Body, Query, UploadFile
from langchain.docstore.document import Document
from pydantic import Json
from sse_starlette import EventSourceResponse
from starlette.responses import StreamingResponse

from configs import (DEFAULT_VS_TYPE, EMBEDDING_MODEL,
                     VECTOR_SEARCH_TOP_K, SCORE_THRESHOLD,
                     CHUNK_SIZE, OVERLAP_SIZE, ZH_TITLE_ENHANCE,
                     logger, log_verbose, MAX_KNOWLEDGE_FILE_SIZE)
from server.db.repository.knowledge_file_repository import get_file_detail
from server.knowledge_base.kb_service.base import KBServiceFactory
from server.knowledge_base.model.kb_document_model import DocumentWithVSId
from server.knowledge_base.oss import default_oss
from server.knowledge_base.utils import (validate_kb_name, list_files_from_folder, files2docs_in_thread, KnowledgeFile)
from server.memory.message_i18n import Message_I18N
from server.utils import BaseResponse, run_in_thread_pool, PageResponse, Page
from common.exceptions import ChatBusinessException


def search_docs(
        query: str = Body("", description="用户输入", examples=["你好"]),
        knowledge_base_name: str = Body(..., description="知识库名称", examples=["samples"]),
        top_k: int = Body(VECTOR_SEARCH_TOP_K, description="匹配向量数"),
        score_threshold: float = Body(SCORE_THRESHOLD,
                                      description="知识库匹配相关度阈值，取值范围在0-1之间，"
                                                  "SCORE越小，相关度越高，"
                                                  "取到1相当于不筛选，建议设置在0.5左右",
                                      ge=0, le=1),
        file_name: str = Body("", description="文件名称，支持 sql 通配符"),
        metadata: dict = Body({}, description="根据 metadata 进行过滤，仅支持一级键"),
) -> List[DocumentWithVSId]:
    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    data = []
    if kb is not None:
        if query:
            docs = kb.search_docs(query, top_k, score_threshold)
            data = [DocumentWithVSId(**x[0].dict(), score=x[1], id=x[0].metadata.get("id")) for x in docs]
        elif file_name or metadata:
            data = kb.list_docs(file_name=file_name, metadata=metadata)
            for d in data:
                if "vector" in d.metadata:
                    del d.metadata["vector"]
    return data


def update_docs_by_id(
        knowledge_base_name: str = Body(..., description="知识库名称", examples=["samples"]),
        docs: Dict[str, Document] = Body(..., description="要更新的文档内容，形如：{id: Document, ...}")
) -> BaseResponse:
    '''
    按照文档 ID 更新文档内容
    '''
    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return BaseResponse(code=500, msg=Message_I18N.API_KB_NOT_EXIST.value.format(kb_name=knowledge_base_name))
    if kb.update_doc_by_ids(docs=docs):
        return BaseResponse(msg=Message_I18N.COMMON_CALL_SUCCESS.value)
    else:
        return BaseResponse(msg=Message_I18N.API_UPDATE_ERROR.value)


def list_files(
        knowledge_base_name: str = Query(description="知识库名称"),
        page_size: int = Query(default=10, description="分页大小"),
        page_num: int = Query(default=1, description="页数"),
        keyword: str = Query(None, allow_inf_nan=True, description="模糊搜索文件名称"),
        create_time_begin: datetime = Query(None, allow_inf_nan=True, description="创建时间开始"),
        create_time_end: datetime = Query(None, allow_inf_nan=True, description="创建时间结束"),
) -> PageResponse:
    if not validate_kb_name(knowledge_base_name):
        return PageResponse(code=500, msg="Invalid knowledge base name", data=None)

    knowledge_base_name = urllib.parse.unquote(knowledge_base_name)
    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return PageResponse(code=500, msg=Message_I18N.API_KB_NOT_EXIST.value.format(kb_name=knowledge_base_name),
                            data=None)
    else:
        data, total = kb.list_files(page_size=min(abs(page_size), 1000), page_num=page_num, keyword=keyword,
                                    create_time_begin=create_time_begin, create_time_end=create_time_end,
                                    only_name=False)
        return PageResponse(data=Page(records=data, total=total))


def _save_files_in_thread(files: List[UploadFile],
                          knowledge_base_name: str,
                          override: bool):
    """
    通过多线程将上传的文件保存到对应知识库目录内。
    生成器返回保存结果：{"code":200, "msg": "xxx", "data": {"knowledge_base_name":"xxx", "file_name": "xxx"}}
    """

    def save_file(file: UploadFile, knowledge_base_name: str, override: bool) -> dict:
        '''
        保存单个文件。
        '''
        filename = file.filename
        data = {"knowledge_base_name": knowledge_base_name, "file_name": filename}
        try:
            oss_api = default_oss()
            if oss_api.object_exist(knowledge_base_name, filename) and not override:
                file_status = f"文件 {filename} 已存在。"
                logger.warn(file_status)
                return dict(code=404, msg=file_status, data=data)

            oss_api.put_object(data=file.file, bucket_name=knowledge_base_name, object_name=filename, override=override)
            return dict(code=200, msg=f"成功上传文件 {filename}", data=data)
        except Exception as e:
            msg = f"{filename} 文件上传失败，报错信息为: {e}"
            logger.error(f'{e.__class__.__name__}: {msg}',
                         exc_info=e if log_verbose else None)
            return dict(code=500, msg=msg, data=data)

    params = [{"file": file, "knowledge_base_name": knowledge_base_name, "override": override} for file in files]
    for result in run_in_thread_pool(save_file, params=params):
        yield result


# def files2docs(files: List[UploadFile] = File(..., description="上传文件，支持多文件"),
#                 knowledge_base_name: str = Form(..., description="知识库名称", examples=["samples"]),
#                 override: bool = Form(False, description="覆盖已有文件"),
#                 save: bool = Form(True, description="是否将文件保存到知识库目录")):
#     def save_files(files, knowledge_base_name, override):
#         for result in _save_files_in_thread(files, knowledge_base_name=knowledge_base_name, override=override):
#             yield json.dumps(result, ensure_ascii=False)

#     def files_to_docs(files):
#         for result in files2docs_in_thread(files):
#             yield json.dumps(result, ensure_ascii=False)


def upload_docs(
        files: List[UploadFile] = File(..., max_size=MAX_KNOWLEDGE_FILE_SIZE, description="上传文件，支持多文件"),
        knowledge_base_name: str = Form(..., description="知识库名称", examples=["samples"]),
        override: bool = Form(True, description="覆盖已有文件"),
        to_vector_store: bool = Form(True, description="上传文件后是否进行向量化"),
        chunk_size: int = Form(CHUNK_SIZE, description="知识库中单段文本最大长度"),
        chunk_overlap: int = Form(OVERLAP_SIZE, description="知识库中相邻文本重合长度"),
        zh_title_enhance: bool = Form(ZH_TITLE_ENHANCE, description="是否开启中文标题加强"),
        separators: List[str] = Form([], description="文本切分符号"),
        docs: Json = Form({}, description="自定义的docs，需要转为json字符串",
                          examples=[{"test.txt": [Document(page_content="custom doc")]}]),
        not_refresh_vs_cache: bool = Form(False, description="暂不保存向量库（用于FAISS）"),
) -> BaseResponse:
    """
    API接口：上传文件，并/或向量化
    """
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=500, msg="Invalid knowledge base name")

    for file in files:
        if 0 < MAX_KNOWLEDGE_FILE_SIZE < file.size:
            return BaseResponse(code=413,
                                msg=f"File({file.filename}) is too large, max size is {MAX_KNOWLEDGE_FILE_SIZE} bytes")

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return BaseResponse(code=500, msg=Message_I18N.API_KB_NOT_EXIST.value.format(kb_name=knowledge_base_name))

    failed_files = {}
    file_names = list(docs.keys())

    # 先将上传的文件保存到磁盘
    for result in _save_files_in_thread(files, knowledge_base_name=knowledge_base_name, override=override):
        filename = result["data"]["file_name"]
        if result["code"] != 200:
            failed_files[filename] = result["msg"]

        if filename not in file_names:
            file_names.append(filename)

    # 对保存的文件进行向量化
    if to_vector_store:
        result = update_docs(
            knowledge_base_name=knowledge_base_name,
            file_names=file_names,
            override_custom_docs=True,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            zh_title_enhance=zh_title_enhance,
            separators=separators,
            docs=docs,
            not_refresh_vs_cache=True,
        )
        failed_files.update(result.data["failed_files"])
        if not not_refresh_vs_cache:
            kb.save_vector_store()

    return BaseResponse(code=200, msg=Message_I18N.COMMON_CALL_SUCCESS.value, data={"failed_files": failed_files})


def delete_docs(
        knowledge_base_name: str = Body(..., examples=["samples"]),
        file_names: List[str] = Body(..., examples=[["file_name.md", "test.txt"]]),
        delete_content: bool = Body(False),
        not_refresh_vs_cache: bool = Body(False, description="暂不保存向量库（用于FAISS）"),
) -> BaseResponse:
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=500, msg="Invalid knowledge base name")

    knowledge_base_name = urllib.parse.unquote(knowledge_base_name)
    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return BaseResponse(code=500, msg=Message_I18N.API_KB_NOT_EXIST.value.format(kb_name=knowledge_base_name))

    failed_files = {}
    for file_name in file_names:
        if not kb.exist_doc(file_name):
            failed_files[file_name] = f"未找到文件 {file_name}"

        try:
            kb_file = KnowledgeFile(filename=file_name,
                                    knowledge_base_name=knowledge_base_name)
            kb.delete_doc(kb_file, delete_content, not_refresh_vs_cache=True)
        except Exception as e:
            msg = f"{file_name} 文件删除失败，错误信息：{e}"
            logger.error(f'{e.__class__.__name__}: {msg}',
                         exc_info=e if log_verbose else None)
            failed_files[file_name] = msg

    if not not_refresh_vs_cache:
        kb.save_vector_store()

    return BaseResponse(code=200, msg=Message_I18N.COMMON_CALL_SUCCESS.value, data={"failed_files": failed_files})


def update_info(
        knowledge_base_name: str = Body(max_length=50, examples=["samples"], description="不允许修改"),
        knowledge_base_name_cn: str = Body(max_length=50, examples=["samples知识库"]),
        kb_info: str = Body(..., description="知识库介绍", examples=["这是一个知识库"]),
):
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=500, msg="Invalid Knowledge Base Name")

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return BaseResponse(code=500, msg=Message_I18N.API_KB_NOT_EXIST.value.format(kb_name=knowledge_base_name))
    try:
        kb.update_info(knowledge_base_name_cn, kb_info)
    except ChatBusinessException as e:
        logger.error(f"{e}")
        return BaseResponse(code=500, msg=f"{e}")
    except Exception as e:
        msg = f"修改知识库出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_UPDATE_ERROR.value)
    return BaseResponse(code=200, msg=Message_I18N.COMMON_CALL_SUCCESS.value,
                        data={"knowledge_base_name_cn": knowledge_base_name_cn, "kb_info": kb_info})


def update_docs(
        knowledge_base_name: str = Body(..., description="知识库名称", examples=["samples"]),
        file_names: List[str] = Body(..., description="文件名称，支持多文件", examples=[["file_name1", "text.txt"]]),
        chunk_size: int = Body(CHUNK_SIZE, description="知识库中单段文本最大长度"),
        chunk_overlap: int = Body(OVERLAP_SIZE, description="知识库中相邻文本重合长度"),
        zh_title_enhance: bool = Body(ZH_TITLE_ENHANCE, description="是否开启中文标题加强"),
        separators: List[str] = Body([], description="文本切分符号"),
        override_custom_docs: bool = Body(False, description="是否覆盖之前自定义的docs"),
        docs: Json = Body({}, description="自定义的docs，需要转为json字符串",
                          examples=[{"test.txt": [Document(page_content="custom doc")]}]),
        not_refresh_vs_cache: bool = Body(False, description="暂不保存向量库（用于FAISS）"),
) -> BaseResponse:
    """
    更新知识库文档
    """
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=500, msg="Invalid knowledge base name")

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return BaseResponse(code=500, msg=Message_I18N.API_KB_NOT_EXIST.value.format(kb_name=knowledge_base_name))

    failed_files = {}
    kb_files = []

    # 生成需要加载docs的文件列表
    for file_name in file_names:
        file_detail = get_file_detail(kb_name=knowledge_base_name, filename=file_name)
        # 如果该文件之前使用了自定义docs，则根据参数决定略过或覆盖
        if file_detail.get("custom_docs") and not override_custom_docs:
            continue
        if file_name not in docs:
            try:
                kb_files.append(
                    KnowledgeFile(filename=file_name, knowledge_base_name=knowledge_base_name, separators=separators))
            except Exception as e:
                msg = f"加载文档 {file_name} 时出错：{e}"
                logger.error(f'{e.__class__.__name__}: {msg}',
                             exc_info=e if log_verbose else None)
                failed_files[file_name] = msg

    # 从文件生成docs，并进行向量化。
    # 这里利用了KnowledgeFile的缓存功能，在多线程中加载Document，然后传给KnowledgeFile
    for status, result in files2docs_in_thread(kb_files,
                                               chunk_size=chunk_size,
                                               chunk_overlap=chunk_overlap,
                                               zh_title_enhance=zh_title_enhance,
                                               separators=separators):
        if status:
            kb_name, file_name, new_docs = result
            kb_file = KnowledgeFile(filename=file_name,
                                    knowledge_base_name=knowledge_base_name, separators=separators)
            kb_file.splited_docs = new_docs
            kb.update_doc(kb_file, not_refresh_vs_cache=True)
        else:
            kb_name, file_name, error = result
            failed_files[file_name] = error

    # 将自定义的docs进行向量化
    for file_name, v in docs.items():
        try:
            v = [x if isinstance(x, Document) else Document(**x) for x in v]
            kb_file = KnowledgeFile(filename=file_name, knowledge_base_name=knowledge_base_name, separators=separators)
            kb.update_doc(kb_file, docs=v, not_refresh_vs_cache=True)
        except Exception as e:
            msg = f"为 {file_name} 添加自定义docs时出错：{e}"
            logger.error(f'{e.__class__.__name__}: {msg}',
                         exc_info=e if log_verbose else None)
            failed_files[file_name] = msg

    if not not_refresh_vs_cache:
        kb.save_vector_store()

    return BaseResponse(code=200, msg=Message_I18N.COMMON_CALL_SUCCESS.value, data={"failed_files": failed_files})


def download_doc(
        knowledge_base_name: str = Query(..., description="知识库名称", examples=["samples"]),
        filename: str = Query(..., description="文件名称", examples=["test.txt"]),
        path: str = Query("", description="路径"),
        preview: bool = Query(False, description="是：浏览器内预览；否：下载"),
):
    """
    下载知识库文档
    """
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=500, msg="Invalid knowledge base name")

    if knowledge_base_name != 'temp':
        kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
        if kb is None:
            return BaseResponse(code=500, msg=Message_I18N.API_KB_NOT_EXIST.value.format(kb_name=knowledge_base_name))

    if preview:
        content_disposition_type = "inline"
    else:
        content_disposition_type = "attachment"

    try:
        if path is not None and path.strip() != '':
            data = default_oss().get_object(knowledge_base_name, object_name=f"{path}/{filename}")
        else:
            data = default_oss().get_object(knowledge_base_name, filename)
        media_types = mimetypes.guess_type(filename)
        return StreamingResponse(content=data, media_type=media_types[0] if media_types else "application/octet-stream",
                                 headers={'Content-Disposition': "{}; filename*=utf-8''{}".format(
                                     content_disposition_type, quote(filename)
                                 )})
    except Exception as e:
        msg = f"{filename} 读取文件失败，错误信息是：{e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)


def recreate_vector_store(
        knowledge_base_name: str = Body(..., examples=["samples"]),
        allow_empty_kb: bool = Body(True),
        vs_type: str = Body(DEFAULT_VS_TYPE),
        embed_model: str = Body(EMBEDDING_MODEL),
        chunk_size: int = Body(CHUNK_SIZE, description="知识库中单段文本最大长度"),
        chunk_overlap: int = Body(OVERLAP_SIZE, description="知识库中相邻文本重合长度"),
        zh_title_enhance: bool = Body(ZH_TITLE_ENHANCE, description="是否开启中文标题加强"),
        separators: List[str] = Body([], description="文本切分符号"),
        not_refresh_vs_cache: bool = Body(False, description="暂不保存向量库（用于FAISS）"),
):
    """
    recreate vector store from the content.
    this is usefull when user can copy files to content folder directly instead of upload through network.
    by default, get_service_by_name only return knowledge base in the info.db and having document files in it.
    set allow_empty_kb to True make it applied on empty knowledge base which it not in the info.db or having no documents.
    """

    def output():
        kb = KBServiceFactory.get_service(knowledge_base_name, vs_type, embed_model)
        if not kb.exists() and not allow_empty_kb:
            yield {"code": 500, "msg": Message_I18N.API_KB_NOT_EXIST.value.format(kb_name=knowledge_base_name)}
        else:
            if kb.exists():
                kb.clear_vs()
            kb.create_kb()
            files = list_files_from_folder(knowledge_base_name)
            kb_files = [(file, knowledge_base_name) for file in files]
            i = 0
            for status, result in files2docs_in_thread(kb_files,
                                                       chunk_size=chunk_size,
                                                       chunk_overlap=chunk_overlap,
                                                       zh_title_enhance=zh_title_enhance,
                                                       separators=separators):
                if status:
                    kb_name, file_name, docs = result
                    kb_file = KnowledgeFile(filename=file_name, knowledge_base_name=kb_name, separators=separators)
                    kb_file.splited_docs = docs
                    yield json.dumps({
                        "code": 200,
                        "msg": f"({i + 1} / {len(kb_files)}): {file_name}",
                        "total": len(kb_files),
                        "finished": i + 1,
                        "doc": file_name,
                    }, ensure_ascii=False)
                    kb.add_doc(kb_file, not_refresh_vs_cache=True)
                else:
                    kb_name, file_name, error = result
                    msg = f"添加文件‘{file_name}’到知识库‘{knowledge_base_name}’时出错：{error}。已跳过。"
                    logger.error(msg)
                    yield json.dumps({
                        "code": 500,
                        "msg": msg,
                    })
                i += 1
            if not not_refresh_vs_cache:
                kb.save_vector_store()

    return EventSourceResponse(output())
