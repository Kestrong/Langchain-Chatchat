import base64
import datetime
import io
import json
import uuid
from typing import List, Tuple, Dict, Union, AsyncIterable

import requests
import tiktoken
from langchain.agents import LLMSingleActionAgent, AgentExecutor
from langchain.agents.structured_chat.output_parser import StructuredChatOutputParserWithRetries
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
from langchain_core.prompts.image import ImagePromptTemplate
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse
from starlette.requests import Request

from common.exceptions import ChatBusinessException, WorkerBusinessException
from configs import logger, log_verbose, MAX_TOKENS_INPUT
from server.db.repository import update_message
from server.memory.message_i18n import Message_I18N
from server.memory.token_info_memory import get_token_headers
from server.utils import get_model_worker_config, BaseResponse, run_in_thread_pool, get_mime_type, get_file_category, \
    get_chat_file_kb


def get_max_token_limit(model_name: str):
    from server.model_workers import ApiChatParams
    api_chat_params = ApiChatParams(messages=[]).load_config(worker_name=model_name)
    # 动态获取模型总的输入上限
    total_limit = api_chat_params.role_meta.get('max_model_len') or MAX_TOKENS_INPUT
    # 动态设定安全缓冲：模型窗口越大，缓冲可以适当加大；窗口小则缓冲减小
    # 比如设定为总窗口的 10%，且最小不低于 128，最高不超过 2000
    safety_margin = max(128, min(2000, int(total_limit * 0.1)))
    # 计算最终的输入限制 = 总输入 - 输出 - 缓冲，并确保至少留有 1 个 Token 的空间，防止负数报错
    max_token_limit = max(1, total_limit - safety_margin)
    return max_token_limit


def get_tiktoken_num(content):
    encoding = tiktoken.get_encoding("cl100k_base")
    try:
        return len(encoding.encode(str(content)))
    except:
        return int(len(str(content)) * 1.2)


def calculate_token_len(role: str, content):
    length = len(role) + 1
    if isinstance(content, list) and len(content) > 0 and isinstance(content[0], dict):
        for content in content:
            if content.get("type") == "text":
                length += get_tiktoken_num(content.get("text"))
            elif content.get("type") == "image_url":
                length += 1500
    else:
        length += get_tiktoken_num(content)
    return length


class History(BaseModel):
    """
    对话历史
    可从dict生成，如
    h = History(**{"role":"user","content":"你好"})
    也可转换为tuple，如
    h.to_msy_tuple = ("human", "你好")
    """
    role: str = Field(...)
    content: str = Field(...)
    chat_files: list = Field(default=None)

    def parse_chat_files(self, chat_files: List[dict]):
        from server.knowledge_base.oss import default_oss
        from server.knowledge_base.utils import KnowledgeFile, get_file_path

        def parse_file(cf: dict):
            filename = cf.get('filename')
            knowledge_id = cf.get('path')
            kb_name = cf.get('knowledge_base_name')
            ext = filename.rsplit('.', 1)[-1].strip().lower() if filename and '.' in filename else ''
            file_category = get_file_category(ext)
            file_path = f"{knowledge_id}/{filename}"
            try:
                if file_category == "document":
                    kb_file = KnowledgeFile(filename=filename, knowledge_base_name=kb_name)
                    kb_file.filepath = get_file_path(kb_file.kb_name, doc_name=file_path)
                    kb_file.filename = file_path
                    docs = kb_file.file2docs()
                    return {"file_category": file_category, "filename": filename,
                            "data": "\n".join([doc.page_content for doc in docs])}
                elif file_category == "image":
                    with default_oss().get_object(bucket_name=kb_name, object_name=file_path) as f:
                        if hasattr(f, 'read'):
                            file_bytes = f.read()
                        else:
                            file_bytes = f  # 已经是 bytes 数据的情况
                        encoding = base64.b64encode(file_bytes).decode("utf-8")
                        mime_type = get_mime_type(ext)
                        return {"file_category": file_category, "filename": filename,
                                "data": f"data:{mime_type};base64,{encoding}"}
                else:
                    return None
            except Exception as e:
                logger.error(e)
                return None

        params = [{"cf": file} for file in chat_files]
        for result in run_in_thread_pool(parse_file, params=params):
            yield result

    def get_content_tuple(self, format_openai: bool = True):
        if not format_openai:
            p_content = content = self.content
            image_urls = []
        else:
            documents = []
            images = []
            if self.chat_files and isinstance(self.chat_files, list):
                for file in self.parse_chat_files(chat_files=self.chat_files):
                    if not file:
                        continue
                    if file.get("file_category") == "image":
                        images.append(file)
                    elif file.get("file_category") == "document":
                        documents.append(file)
            document_contents = []
            image_urls = []
            if documents:
                part_documents = []
                for file in documents:
                    f_content = f"<input_file><filename>{file.get('filename')}</filename><file_content>{file.get('data')}</file_content></input_file>"
                    part_documents.append(f_content)
                f_document_contents = "\n".join(part_documents)
                document_contents.append(
                    f"<input_files>{f_document_contents}</input_files>\n<input_query>{self.content}</input_query>")
            else:
                document_contents.append(self.content)
            if images:
                for image in images:
                    image_urls.append(image.get("data"))
            p_content = "\n".join(document_contents)
            if image_urls:
                content = [{"type": "text", "text": p_content}]
                for image_url in image_urls:
                    content.append({"type": "image_url", "image_url": {"url": image_url}})
            else:
                content = p_content
        return p_content, image_urls, calculate_token_len(self.role, content), content

    def to_msg_tuple(self, format_openai: bool = True):
        _, _, _, parsed_content = self.get_content_tuple(format_openai=format_openai)
        return "ai" if self.role in ["assistant", "ai"] else "human", parsed_content

    def to_msg_template(self, image_urls: list = None, format_openai: bool = True) -> HumanMessagePromptTemplate:
        if format_openai and image_urls:
            prompt = [PromptTemplate.from_template(self.content, template_format="jinja2")]
            for image_url in image_urls:
                prompt.append(ImagePromptTemplate(template={"url": image_url}))
        else:
            prompt = PromptTemplate.from_template(self.content, template_format="jinja2")
        return HumanMessagePromptTemplate(prompt=prompt, )

    @classmethod
    def from_data(cls, h: Union[List, Tuple, Dict]) -> "History":
        if isinstance(h, (list, tuple)) and len(h) >= 3:
            h = cls(role=h[0], content=h[1], chat_files=h[2])
        elif isinstance(h, (list, tuple)) and len(h) >= 2:
            h = cls(role=h[0], content=h[1])
        elif isinstance(h, dict):
            h = cls(**h)

        return h


def parse_llm_token_inner_json(model_name: str, token: str, throw_error: bool = True):
    mark = f'###[{model_name}]###'
    answer, thought, error_info = '', '', ''
    extra = {}
    d = {}
    if mark in token:
        parts = token.split(mark)
        for part in parts:
            if part is not None and part.strip() != '':
                if part.startswith('{') and part.endswith('}'):
                    inner_json = json.loads(part)
                    answer += inner_json.get('answer', '')
                    thought += inner_json.get('thought', '')
                    if 'conversation_id' in inner_json:
                        extra['conversation_id'] = inner_json['conversation_id']
                    if 'message_id' in inner_json:
                        extra['message_id'] = inner_json['message_id']
                    if 'error_info' in inner_json:
                        error_info = inner_json['error_info']
                    if 'docs' in inner_json:
                        d["docs"] = inner_json['docs']
                else:
                    answer += part
    else:
        answer = token
    if throw_error and error_info:
        err = WorkerBusinessException(answer)
        err.__cause__ = WorkerBusinessException(error_info)
        raise err
    d["answer"] = answer
    d["thought"] = thought
    if len(extra) > 0:
        d["extra"] = extra
    return d


class MaxInputTokenException(BaseException):
    pass


async def wrap_event_response(event_response: AsyncIterable[str]) -> AsyncIterable[str]:
    d = {}
    try:
        first = True
        async for event in event_response:
            if first:
                try:
                    first = False
                    d.update(json.loads(event))
                except:
                    pass
            yield event
    except MaxInputTokenException as e:
        d["answer"] = f"{e}"
        d["error"] = True
        d["event"] = "error"
        if d.get("message_id"):
            update_message(message_id=d.get("message_id"), response=d["answer"], response_time=datetime.datetime.now())
        yield json.dumps(d, ensure_ascii=False)
    except BaseException as e:
        d["error"] = True
        d["event"] = "error"
        if isinstance(e, WorkerBusinessException):
            d["answer"] = str(e)
            e = e.__cause__
            d["error_info"] = str(e)
            logger.error(f'{e.__class__.__name__}: {e}', exc_info=e if log_verbose else None)
            if d.get("message_id"):
                update_message(message_id=d.get("message_id"), response=d["answer"], metadata={"error_info": str(e)},
                               append=True, response_time=datetime.datetime.now())
            yield json.dumps(d, ensure_ascii=False)
        elif isinstance(e, ChatBusinessException):
            d["answer"] = str(e)
            e = e.__cause__
            d["error_info"] = str(e)
            logger.error(f'{e.__class__.__name__}: {e}', exc_info=e if log_verbose else None)
            yield json.dumps(d, ensure_ascii=False)
        else:
            msg = f'{e.__class__.__name__}: {e}'
            logger.error(msg, exc_info=e if log_verbose else None)
            d["answer"] = Message_I18N.WORKER_CHAT_ERROR.value
            d["error_info"] = msg
            if d.get("message_id"):
                update_message(message_id=d.get("message_id"), response=d["answer"], metadata={"error_info": msg},
                               append=True, response_time=datetime.datetime.now())
            yield json.dumps(d, ensure_ascii=False)


async def choose_response(stream: bool, chat_iterator: AsyncIterable[str], request: Request = None):
    openapi = True if request and "/openapi/" in request.url.path else False
    if not openapi:
        return EventSourceResponse(wrap_event_response(chat_iterator))
    if stream:
        return EventSourceResponse(wrap_event_response(chat_iterator))
    else:
        last_response = None
        async for item in wrap_event_response(chat_iterator):
            last_response = item
        last_response = json.loads(last_response) if last_response else {}
        return BaseResponse(code=200, data=last_response)


EMPTY_LLM_CHAT_PROMPT = PromptTemplate.from_template("{{ input }}", template_format="jinja2")


# 特殊的在线大模型
def un_format_online_llm_model(model_name: str):
    config = get_model_worker_config(model_name)
    worker_class = config.get("worker_class")
    if worker_class:
        worker = worker_class()
        return not worker.format_online_llm()
    return False


def has_input_memory_key(input_variables: List[str], memory_variables: List[str]):
    if input_variables and memory_variables and all(item in input_variables for item in memory_variables):
        return True
    return False


def create_agent_executor(model, memory, available_tools: list, prompt_template: Union[str, HumanMessagePromptTemplate],
                          max_iterations: int = 5):
    if isinstance(prompt_template, str):
        prompt_template = HumanMessagePromptTemplate.from_template(prompt_template, template_format="jinja2")
    from server.agent import CustomPromptTemplate, CustomOutputParser
    prompt_template_agent = CustomPromptTemplate(
        template=prompt_template,
        tools=available_tools,
        template_format='jinja2',
        input_variables=["input", "intermediate_steps"] + memory.memory_variables
    )
    memory.return_messages = not has_input_memory_key(prompt_template.input_variables, memory.memory_variables)
    llm_chain = LLMChain(llm=model, prompt=ChatPromptTemplate.from_messages(
        memory.buffer_history(prompt_template.input_variables) + [prompt_template_agent]))
    origin_model_name = model.metadata.get("origin_model_name") or model.model_name
    custom_output_parser = CustomOutputParser(model_name=origin_model_name)
    output_parser = StructuredChatOutputParserWithRetries.from_llm(llm=model, base_parser=custom_output_parser)
    output_parser.output_fixing_parser.max_retries = 3
    agent = LLMSingleActionAgent(
        llm_chain=llm_chain,
        output_parser=output_parser,
        stop=["Observation:", "\nObservation", "<|endoftext|>", "<|im_start|>", "<|im_end|>"],
        allowed_tools=[t.name for t in available_tools],
    )
    agent_executor = AgentExecutor.from_agent_and_tools(agent=agent,
                                                        tools=available_tools,
                                                        verbose=True,
                                                        memory=memory,
                                                        max_iterations=max_iterations
                                                        )
    return agent_executor


def unify_chat_files(third_party_files: List[dict], knowledge_id: str = None, request: Request = None):
    from server.knowledge_base.oss import default_oss
    CHAT_FILE_KB = get_chat_file_kb()
    chat_files = []
    if knowledge_id:
        files = default_oss().list_objects(bucket_name=CHAT_FILE_KB, object_name=knowledge_id)
        for filename in files:
            chat_files.append({"filename": filename, "knowledge_base_name": CHAT_FILE_KB, "path": knowledge_id})

    if third_party_files:
        if not knowledge_id:
            knowledge_id = str(uuid.uuid4())
        headers = get_token_headers()
        for f in third_party_files:
            response = requests.get(f.get('url'), headers=headers, cookies=request.cookies if request else None,
                                    stream=True, verify=False)
            if not response.ok:
                logger.error(response.text)
                continue

            file_stream = io.BytesIO()
            try:
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        file_stream.write(chunk)
                file_stream.seek(0)
                file_path = f"{knowledge_id}/{f.get('name')}"
                default_oss().put_object(data=file_stream, bucket_name=CHAT_FILE_KB, object_name=file_path,
                                         override=True)
                chat_files.append(
                    {"filename": f.get('name'), "knowledge_base_name": CHAT_FILE_KB, "path": knowledge_id})
            except BaseException as e:
                logger.error(e)
                continue
    return chat_files
