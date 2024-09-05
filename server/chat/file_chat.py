import asyncio
import json
import uuid
from typing import AsyncIterable, List, Optional, Tuple, Any, Union, Iterable

from fastapi import Body, File, UploadFile, Form
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.chains import LLMChain
from langchain.prompts.chat import ChatPromptTemplate
from sse_starlette.sse import EventSourceResponse

from configs import (LLM_MODELS, TEMPERATURE)
from server.chat.utils import History, UN_FORMAT_ONLINE_LLM_MODELS
from server.knowledge_base.oss import default_oss, OssType, oss_factory
from server.knowledge_base.utils import KnowledgeFile, get_file_path
from server.utils import (wrap_done, get_ChatOpenAI,
                          BaseResponse, get_prompt_template, run_in_thread_pool)


def _parse_files_in_thread(
        files: Union[List[UploadFile], Iterable[str]],
        dir: str,
        doc: bool
):
    """
    通过多线程将上传的文件保存到对应目录内。
    生成器返回保存结果：[success or error, filename, msg, docs]
    """

    def parse_file(file: Union[UploadFile, str]) -> Tuple[bool, Optional[str], str, Any]:
        '''
        保存单个文件。
        '''
        filename = file.filename if not doc else file
        file_path = f"{dir}/{filename}"
        try:
            docs = None
            if doc:
                kb_file = KnowledgeFile(filename=filename, knowledge_base_name="temp")
                kb_file.filepath = get_file_path(kb_file.kb_name, file_path)
                kb_file.filename = file_path
                docs = kb_file.file2docs()
            else:
                default_oss().put_object(data=file.file, bucket_name="temp", object_name=file_path, override=True)
            return True, filename, f"成功上传文件 {filename}", docs
        except Exception as e:
            msg = f"{filename} 文件上传失败，报错信息为: {e}"
            return False, filename, msg, None

    params = [{"file": file} for file in files]
    for result in run_in_thread_pool(parse_file, params=params):
        yield result


def upload_temp_docs(
        files: List[UploadFile] = File([], description="上传文件，支持多文件"),
        prev_id: str = Form("", description="前知识库ID"),
        delete: bool = Form(False, description="如果目录存在是否删除"),
) -> BaseResponse:
    '''
    将文件保存到临时目录，并返回切片文档。
    '''
    if prev_id and delete:
        default_oss().delete_object(bucket_name="temp", object_name=prev_id)

    if not files:
        return BaseResponse(data={"id": None, "failed_files": []})

    failed_files = []
    id = prev_id or str(uuid.uuid4())
    for success, file, msg, _ in _parse_files_in_thread(files=files, dir=id, doc=False):
        if not success:
            failed_files.append({file: msg})

    return BaseResponse(data={"id": id, "failed_files": failed_files})


async def file_chat(query: str = Body(..., description="用户输入", examples=["你好"]),
                    knowledge_id: str = Body("", description="临时知识库ID"),
                    history: List[History] = Body([],
                                                  description="历史对话",
                                                  examples=[[
                                                      {"role": "user",
                                                       "content": "我们来玩成语接龙，我先来，生龙活虎"},
                                                      {"role": "assistant",
                                                       "content": "虎头虎脑"}]]
                                                  ),
                    stream: bool = Body(False, description="流式输出"),
                    model_name: str = Body(LLM_MODELS[0], description="LLM 模型名称。"),
                    temperature: float = Body(TEMPERATURE, description="LLM 采样温度", ge=0.0, le=1.0),
                    max_tokens: Optional[int] = Body(None, description="限制LLM生成Token数量，默认None代表模型最大值"),
                    prompt_name: str = Body("default",
                                            description="使用的prompt模板名称(在configs/prompt_config.py中配置)"),
                    ):
    if model_name in UN_FORMAT_ONLINE_LLM_MODELS:
        return BaseResponse(code=500, msg=f"对不起，文件对话不支持该模型:{model_name}")
    if knowledge_id is None or knowledge_id.strip() == "":
        return BaseResponse(code=500, msg=f"临时知识库{knowledge_id}不允许为空")
    if not (files := default_oss().list_objects(bucket_name="temp", object_name=knowledge_id)):
        return BaseResponse(code=500, msg=f"未找到临时知识库 {knowledge_id}，请先上传文件")

    history = [History.from_data(h) for h in history]

    async def knowledge_base_chat_iterator() -> AsyncIterable[str]:
        nonlocal max_tokens
        callback = AsyncIteratorCallbackHandler()
        if isinstance(max_tokens, int) and max_tokens <= 0:
            max_tokens = None

        callbacks = [callback]
        # Enable langchain-chatchat to support langfuse
        import os
        langfuse_secret_key = os.environ.get('LANGFUSE_SECRET_KEY')
        langfuse_public_key = os.environ.get('LANGFUSE_PUBLIC_KEY')
        langfuse_host = os.environ.get('LANGFUSE_HOST')
        if langfuse_secret_key and langfuse_public_key and langfuse_host:
            from langfuse.callback import CallbackHandler
            langfuse_handler = CallbackHandler()
            callbacks.append(langfuse_handler)

        model = get_ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            callbacks=callbacks,
        )
        docs = []
        source_documents = []
        inum = 0
        context = ""
        try:
            for success, file, msg, part_docs in _parse_files_in_thread(files=files, dir=knowledge_id, doc=True):
                inum += 1
                if success:
                    text = f"""[{inum}] {file} \n"""
                    docs.extend(part_docs)
                    context += f"文章名称：{file}\n"
                    context += "\n".join([doc.page_content for doc in part_docs])
                else:
                    text = f"""[{inum}] {file}(解析失败) \n"""
                source_documents.append(text)
        finally:
            if default_oss().type() != OssType.FILESYSTEM.value:
                oss_factory[OssType.FILESYSTEM.value].delete_object("temp", knowledge_id)

        if len(docs) == 0:  ## 如果没有找到相关文档，使用Empty模板
            prompt_template = get_prompt_template("knowledge_base_chat", "empty")
        else:
            prompt_template = get_prompt_template("knowledge_base_chat", prompt_name)
        input_msg = History(role="user", content=prompt_template).to_msg_template(False)
        chat_prompt = ChatPromptTemplate.from_messages(
            [i.to_msg_template() for i in history] + [input_msg])

        chain = LLMChain(prompt=chat_prompt, llm=model)

        # Begin a task that runs in the background.
        task = asyncio.create_task(wrap_done(
            chain.acall({"context": context, "question": query}),
            callback.done),
        )

        if stream:
            async for token in callback.aiter():
                # Use server-sent-events to stream the response
                yield json.dumps({"answer": token}, ensure_ascii=False)
            yield json.dumps({"docs": source_documents}, ensure_ascii=False)
        else:
            answer = ""
            async for token in callback.aiter():
                answer += str(token)
            yield json.dumps({"answer": answer,
                              "docs": source_documents},
                             ensure_ascii=False)
        await task

    return EventSourceResponse(knowledge_base_chat_iterator())
