import os
import sys

import nltk
from fastapi.security import APIKeyHeader
from starlette.requests import Request

from server.agent.tools_select import get_tools_info
from server.chat.agent_chat import call_tool
from server.chat.chat_router import chat_router
from server.chat.conversation import create_conversation, delete_conversation, update_conversation, filter_message, \
    filter_conversation, delete_message, delete_user_conversation
from server.chat.task_manager import stop
from server.memory.token_info_memory import set_token, i18n_context

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from configs import VERSION
from configs.model_config import NLTK_DATA_PATH
from configs.server_config import OPEN_CROSS_DOMAIN, CIAM_TOKEN_COOKIE_NAME
import argparse
import uvicorn
from fastapi import Body, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from server.chat.chat import chat
from server.chat.search_engine_chat import search_engine_chat
from server.chat.completion import completion
from server.chat.feedback import chat_feedback
from server.embeddings_api import embed_texts_endpoint
from server.llm_api import (list_running_models, list_config_models,
                            change_llm_model, stop_llm_model,
                            get_model_config, list_search_engines)
from server.utils import (BaseResponse, FastAPI, MakeFastAPIOffline,
                          get_server_configs, get_prompt_template, PageResponse)
from typing import List, Literal

nltk.data.path = [NLTK_DATA_PATH] + nltk.data.path


async def document():
    return RedirectResponse(url="/docs")


def create_app(run_mode: str = None):
    async def verify_authorization(authorization: str = Security(APIKeyHeader(name='Authorization', auto_error=False))):
        return authorization

    app = FastAPI(
        title="Langchain-Chatchat API Server",
        version=VERSION, root_path="/flm",
        dependencies=[Depends(verify_authorization)]
    )
    MakeFastAPIOffline(app)
    # Add CORS middleware to allow all origins
    # 在config.py中设置OPEN_DOMAIN=True，允许跨域
    # set OPEN_DOMAIN=True in config.py to allow cross-domain
    if OPEN_CROSS_DOMAIN:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    mount_app_routes(app, run_mode=run_mode)
    return app


def mount_app_routes(app: FastAPI, run_mode: str = None):
    @app.middleware("http")
    async def set_thread_local_variable(request: Request, call_next):
        token = request.headers.get("Authorization")
        if token is None or token.strip() == '':
            token = request.cookies.get(CIAM_TOKEN_COOKIE_NAME)
        set_token(token)
        locale = request.cookies.get('LOCALE')
        if locale:
            i18n_context.set(locale)
        response = await call_next(request)
        return response

    app.get("/",
            response_model=BaseResponse,
            summary="swagger 文档")(document)

    # Tag: Chat
    app.post("/chat/chat",
             tags=["Chat"],
             summary="各种对话的总入口",
             )(chat_router)

    app.post("/chat/llm_chat",
             tags=["Chat"],
             summary="与llm模型对话(通过LLMChain)",
             )(chat)

    app.post("/chat/search_engine_chat",
             tags=["Chat"],
             summary="与搜索引擎对话",
             )(search_engine_chat)

    app.post("/chat/feedback",
             tags=["Chat"],
             summary="返回llm模型对话评分",
             )(chat_feedback)

    app.post("/chat/stop",
             tags=["Chat"],
             summary="停止llm模型对话",
             )(stop)

    app.get("/chat/conversations",
            tags=["Chat"],
            summary="获取会话",
            )(filter_conversation)

    app.post("/chat/conversation",
             tags=["Chat"],
             summary="创建会话",
             )(create_conversation)

    app.put("/chat/conversation",
            tags=["Chat"],
            summary="修改会话",
            )(update_conversation)

    app.delete("/chat/conversation",
               tags=["Chat"],
               summary="删除会话",
               )(delete_conversation)

    app.delete("/chat/user/conversations",
               tags=["Chat"],
               summary="删除用户的所有会话",
               )(delete_user_conversation)

    app.get("/chat/messages",
            tags=["Chat"],
            summary="获取消息",
            )(filter_message)

    app.delete("/chat/message",
               tags=["Chat"],
               summary="删除消息",
               )(delete_message)

    # 知识库相关接口
    mount_knowledge_routes(app)
    # 摘要相关接口
    mount_filename_summary_routes(app)
    # 助手相关接口
    mount_assistant_routes(app)
    # 菜单相关接口
    mount_menu_routes(app)

    # LLM模型相关接口
    app.post("/llm_model/list_running_models",
             tags=["LLM Model Management"],
             summary="列出当前已加载的模型",
             )(list_running_models)

    app.post("/llm_model/list_config_models",
             tags=["LLM Model Management"],
             summary="列出configs已配置的模型",
             )(list_config_models)

    app.post("/llm_model/get_model_config",
             tags=["LLM Model Management"],
             summary="获取模型配置（合并后）",
             )(get_model_config)

    app.post("/llm_model/stop",
             tags=["LLM Model Management"],
             summary="停止指定的LLM模型（Model Worker)",
             )(stop_llm_model)

    app.post("/llm_model/change",
             tags=["LLM Model Management"],
             summary="切换指定的LLM模型（Model Worker)",
             )(change_llm_model)

    # 工具相关
    app.post("/tools/tools_info", tags=["Toolkits"], summary="工具信息")(get_tools_info)
    app.post("/tools/call", tags=["Toolkits"], summary="调用工具")(call_tool)

    # 服务器相关接口
    app.post("/server/configs",
             tags=["Server State"],
             summary="获取服务器原始配置信息",
             )(get_server_configs)

    app.post("/server/list_search_engines",
             tags=["Server State"],
             summary="获取服务器支持的搜索引擎",
             )(list_search_engines)

    @app.post("/server/get_prompt_template",
              tags=["Server State"],
              summary="获取服务区配置的 prompt 模板")
    def get_server_prompt_template(
            type: Literal["llm_chat", "knowledge_base_chat", "search_engine_chat", "agent_chat"] = Body("llm_chat",
                                                                                                        description="模板类型，可选值：llm_chat，knowledge_base_chat，search_engine_chat，agent_chat"),
            name: str = Body("default", description="模板名称"),
    ) -> str:
        return get_prompt_template(type=type, name=name)

    # 其它接口
    app.post("/other/completion",
             tags=["Other"],
             summary="要求llm模型补全(通过LLMChain)",
             )(completion)

    app.post("/other/embed_texts",
             tags=["Other"],
             summary="将文本向量化，支持本地模型和在线模型",
             )(embed_texts_endpoint)


def mount_assistant_routes(app: FastAPI):
    from server.chat.assistant import create_assistant, update_assistant, delete_assistant, get_assistants, \
        get_assistant_detail

    app.get("/chat/assistants",
            tags=["Chat"],
            summary="获取助手列表",
            )(get_assistants)

    app.get("/chat/assistant",
            tags=["Chat"],
            summary="获取助手详情",
            )(get_assistant_detail)

    app.post("/chat/assistant",
             tags=["Chat"],
             summary="创建助手",
             )(create_assistant)

    app.put("/chat/assistant",
            tags=["Chat"],
            summary="修改助手",
            )(update_assistant)

    app.delete("/chat/assistant",
               tags=["Chat"],
               summary="删除助手",
               )(delete_assistant)


def mount_menu_routes(app: FastAPI):
    from server.chat.menu import create_menu, update_menu, delete_menu, get_menus, get_menu_detail

    app.get("/chat/menus",
            tags=["Menu"],
            summary="获取菜单列表",
            )(get_menus)

    app.get("/chat/menu",
            tags=["Menu"],
            summary="获取菜单详情",
            )(get_menu_detail)

    app.post("/chat/menu",
             tags=["Menu"],
             summary="创建菜单",
             )(create_menu)

    app.put("/chat/menu",
            tags=["Menu"],
            summary="修改菜单",
            )(update_menu)

    app.delete("/chat/menu",
               tags=["Menu"],
               summary="删除菜单",
               )(delete_menu)


def mount_knowledge_routes(app: FastAPI):
    from server.chat.knowledge_base_chat import knowledge_base_chat
    from server.chat.file_chat import upload_temp_docs, file_chat
    from server.chat.agent_chat import agent_chat
    from server.knowledge_base.kb_api import list_kbs, create_kb, delete_kb
    from server.knowledge_base.kb_doc_api import (list_files, upload_docs, delete_docs,
                                                  update_docs, download_doc, recreate_vector_store,
                                                  search_docs, DocumentWithVSId, update_info,
                                                  update_docs_by_id, )

    app.post("/chat/knowledge_base_chat",
             tags=["Chat"],
             summary="与知识库对话")(knowledge_base_chat)

    app.post("/chat/file_chat",
             tags=["Chat"],
             summary="文件对话"
             )(file_chat)

    app.post("/chat/agent_chat",
             tags=["Chat"],
             summary="与agent对话")(agent_chat)

    # Tag: Knowledge Base Management
    app.get("/knowledge_base/list_knowledge_bases",
            tags=["Knowledge Base Management"],
            response_model=PageResponse,
            summary="获取知识库列表")(list_kbs)

    app.post("/knowledge_base/create_knowledge_base",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="创建知识库"
             )(create_kb)

    app.post("/knowledge_base/delete_knowledge_base",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="删除知识库"
             )(delete_kb)

    app.get("/knowledge_base/list_files",
            tags=["Knowledge Base Management"],
            response_model=PageResponse,
            summary="获取知识库内的文件列表"
            )(list_files)

    app.post("/knowledge_base/search_docs",
             tags=["Knowledge Base Management"],
             response_model=List[DocumentWithVSId],
             summary="搜索知识库"
             )(search_docs)

    app.post("/knowledge_base/update_docs_by_id",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="直接更新知识库文档"
             )(update_docs_by_id)

    app.post("/knowledge_base/upload_docs",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="上传文件到知识库，并/或进行向量化"
             )(upload_docs)

    app.post("/knowledge_base/delete_docs",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="删除知识库内指定文件"
             )(delete_docs)

    app.post("/knowledge_base/update_info",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="更新知识库介绍"
             )(update_info)
    app.post("/knowledge_base/update_docs",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="更新现有文件到知识库"
             )(update_docs)

    app.get("/knowledge_base/download_doc",
            tags=["Knowledge Base Management"],
            summary="下载对应的知识文件")(download_doc)

    app.post("/knowledge_base/recreate_vector_store",
             tags=["Knowledge Base Management"],
             summary="根据content中文档重建向量库，流式输出处理进度。"
             )(recreate_vector_store)

    app.post("/knowledge_base/upload_temp_docs",
             tags=["Knowledge Base Management"],
             summary="上传文件到临时目录，用于文件对话。"
             )(upload_temp_docs)


def mount_filename_summary_routes(app: FastAPI):
    from server.knowledge_base.kb_summary_api import (summary_file_to_vector_store, recreate_summary_vector_store,
                                                      summary_doc_ids_to_vector_store)

    app.post("/knowledge_base/kb_summary_api/summary_file_to_vector_store",
             tags=["Knowledge kb_summary_api Management"],
             summary="单个知识库根据文件名称摘要"
             )(summary_file_to_vector_store)
    app.post("/knowledge_base/kb_summary_api/summary_doc_ids_to_vector_store",
             tags=["Knowledge kb_summary_api Management"],
             summary="单个知识库根据doc_ids摘要",
             response_model=BaseResponse,
             )(summary_doc_ids_to_vector_store)
    app.post("/knowledge_base/kb_summary_api/recreate_summary_vector_store",
             tags=["Knowledge kb_summary_api Management"],
             summary="重建单个知识库文件摘要"
             )(recreate_summary_vector_store)


def run_api(host, port, **kwargs):
    if kwargs.get("ssl_keyfile") and kwargs.get("ssl_certfile"):
        uvicorn.run(app,
                    host=host,
                    port=port,
                    ssl_keyfile=kwargs.get("ssl_keyfile"),
                    ssl_certfile=kwargs.get("ssl_certfile"),
                    )
    else:
        uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='langchain-ChatGLM',
                                     description='About langchain-ChatGLM, local knowledge based ChatGLM with langchain'
                                                 ' ｜ 基于本地知识库的 ChatGLM 问答')
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7861)
    parser.add_argument("--ssl_keyfile", type=str)
    parser.add_argument("--ssl_certfile", type=str)
    # 初始化消息
    args = parser.parse_args()
    args_dict = vars(args)

    app = create_app()

    run_api(host=args.host,
            port=args.port,
            ssl_keyfile=args.ssl_keyfile,
            ssl_certfile=args.ssl_certfile,
            )
