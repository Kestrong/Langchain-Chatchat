import os
import sys
from typing import Literal

from fastapi.security import APIKeyHeader

from common.custom_gzip_middleware import CustomGZipMiddleware
from common.local_variable_middleware import LocaleVariableMiddleware

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from configs import VERSION
from configs.server_config import OPEN_CROSS_DOMAIN
import argparse
import uvicorn
from fastapi import Depends, Security, APIRouter, Body
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from server.utils import (BaseResponse, FastAPI, MakeFastAPIOffline)


def create_app(run_mode: str = None):
    async def verify_authorization(authorization: str = Security(APIKeyHeader(name='Authorization', auto_error=False))):
        # 服务会通过网关认证后再转发 此处无需认证 只作为swagger开发环境时方便调试
        return authorization

    from configs import ENV
    prod = ENV == "prod"
    app = FastAPI(
        title="Langchain-Chatchat API Server",
        version=VERSION, root_path="/flm", docs_url=None if prod else "/docs", redoc_url=None if prod else "/redoc",
        openapi_url=None if prod else "/openapi.json",
        dependencies=[Depends(verify_authorization)]
    )
    MakeFastAPIOffline(app)
    add_middleware(app)
    mount_app_routes(app, run_mode=run_mode)
    return app


def add_cors_middleware(app: FastAPI):
    # Add CORS middleware to allow specified origins
    # 在config.py中设置OPEN_DOMAIN=True，允许跨域 默认False
    # 生产会通过补丁环境变量配置文件 严格配置允许的域名、方法、头
    if OPEN_CROSS_DOMAIN:
        # CORSMiddleware底层会自动处理*通配符
        ALLOWED_ORIGINS = [origin for origin in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if origin]
        ALLOWED_METHODS = [method for method in os.environ.get("ALLOWED_METHODS", "*").split(",") if method]
        ALLOWED_HEADERS = [header for header in os.environ.get("ALLOWED_HEADERS", "*").split(",") if header]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=ALLOWED_METHODS,
            allow_headers=ALLOWED_HEADERS,
        )

def add_middleware(app: FastAPI):
    add_cors_middleware(app)
    app.add_middleware(CustomGZipMiddleware, minimum_size=1024)
    app.add_middleware(LocaleVariableMiddleware)


def mount_app_routes(app: FastAPI, run_mode: str = None):
    from server.chat.completion import completion
    from server.embeddings_api import embed_texts_endpoint

    @app.get("/", response_model=BaseResponse, summary="swagger 文档")
    async def document():
        return RedirectResponse(url="/docs")

    mount_chat_routes(app=app)
    mount_knowledge_routes(app=app)
    mount_model_routes(app=app)
    mount_server_routes(app=app)
    mount_tool_routes(app=app)
    mount_workflow_routes(app=app)
    mount_openapi_routes(app=app)

    # 其它接口
    app.post("/other/completion", tags=["Other"], summary="要求llm模型补全(通过LLMChain)", )(completion)
    app.post("/other/embeddings", tags=["Other"], summary="将文本向量化，支持本地模型和在线模型", )(embed_texts_endpoint)


def mount_chat_routes(app: FastAPI):
    from server.chat.chat_router import chat_router as chats
    from server.chat.chat import chat, recommend_question
    from server.chat.search_engine_chat import search_engine_chat
    from server.chat.knowledge_base_chat import knowledge_base_chat
    from server.chat.agent_chat import agent_chat
    from server.chat.workflow_chat import workflow_chat
    from server.chat.feedback import chat_feedback
    from server.chat.conversation import create_conversation, delete_conversation, update_conversation, filter_message, \
        filter_conversation, delete_message, delete_user_conversation, get_conversation_detail, list_feedback, \
        export_feedback_to_excel, metrics, get_hot_query, delete_performance_metrics, create_message
    from server.chat.task_manager import stop
    from server.chat.assistant import create_assistant, update_assistant, delete_assistant, get_assistants, \
        get_assistant_detail, get_dicts_by_type
    from server.chat.menu import create_menu, update_menu, delete_menu, get_menus, get_menu_detail

    chat_router = APIRouter(prefix="/chat", tags=["Chat"])

    # Tag Chat
    chat_router.post("/chat", summary="各种对话的总入口", )(chats)
    chat_router.post("/llm_chat", summary="与llm模型对话(通过LLMChain)", )(chat)
    chat_router.post("/search_engine_chat", summary="与搜索引擎对话", )(search_engine_chat)
    chat_router.post("/knowledge_base_chat", summary="与知识库对话")(knowledge_base_chat)
    chat_router.post("/agent_chat", summary="与agent对话")(agent_chat)
    chat_router.post("/workflow_chat", summary="工作流对话", )(workflow_chat)
    chat_router.post("/recommend_question", summary="返回建议的问题列表", )(recommend_question)
    chat_router.post("/feedback", summary="返回llm模型对话评分", )(chat_feedback)
    chat_router.post("/stop", summary="停止llm模型对话", )(stop)
    chat_router.get("/conversations", summary="获取会话", )(filter_conversation)
    chat_router.get("/conversation", summary="获取会话详情", )(get_conversation_detail)
    chat_router.post("/conversation", summary="创建会话", )(create_conversation)
    chat_router.put("/conversation", summary="修改会话", )(update_conversation)
    chat_router.delete("/conversation", summary="删除会话", )(delete_conversation)
    chat_router.delete("/user/conversations", summary="删除用户的所有会话", )(delete_user_conversation)
    chat_router.get("/messages", summary="获取消息", )(filter_message)
    chat_router.post("/message", summary="创建消息", )(create_message)
    chat_router.delete("/message", summary="删除消息", )(delete_message)
    chat_router.get("/list_feedbacks", summary="获取会话详情", )(list_feedback)
    chat_router.get("/export_feedbacks", summary="获取会话详情", )(export_feedback_to_excel)
    chat_router.get("/metrics", summary="获取会话指标", )(metrics)
    chat_router.delete("/model_performance_metrics", summary="删除模型性能指标数据", )(delete_performance_metrics)
    chat_router.get("/hot_query", summary="获取热门问题", )(get_hot_query)
    chat_router.get("/assistants", summary="获取助手列表", )(get_assistants)
    chat_router.get("/assistant", summary="获取助手详情", )(get_assistant_detail)
    chat_router.post("/assistant", summary="创建助手", )(create_assistant)
    chat_router.put("/assistant", summary="修改助手", )(update_assistant)
    chat_router.delete("/assistant", summary="删除助手", )(delete_assistant)
    chat_router.get("/menus", summary="获取菜单列表", )(get_menus)
    chat_router.get("/menu", summary="获取菜单详情", )(get_menu_detail)
    chat_router.post("/menu", summary="创建菜单", )(create_menu)
    chat_router.put("/menu", summary="修改菜单", )(update_menu)
    chat_router.delete("/menu", summary="删除菜单", )(delete_menu)
    chat_router.get("/dict_by_type", summary="根据字典类型获取字典", )(get_dicts_by_type)

    app.include_router(chat_router)
    return chat_router


def mount_knowledge_routes(app: FastAPI):
    from server.knowledge_base.kb_doc_api import delete_temp_docs
    from server.knowledge_base.kb_doc_api import upload_temp_docs
    from server.knowledge_base.kb_api import list_kbs, create_kb, delete_kb, update_info, get_kb_detail
    from server.knowledge_base.kb_doc_api import (list_files, upload_docs, delete_docs, list_docs,
                                                  update_docs, download_doc, recreate_vector_store,
                                                  search_docs, update_docs_by_id, update_enabled, rerank_docs)
    from server.knowledge_base.kb_summary_api import (summary_file_to_vector_store, recreate_summary_vector_store,
                                                      summary_doc_ids_to_vector_store)

    knowledge_router = APIRouter(prefix="/knowledge_base", tags=["Knowledge Base Management"])

    # Tag: Knowledge Base Management
    knowledge_router.get("/list_knowledge_bases", summary="获取知识库列表")(list_kbs)
    knowledge_router.get("/get_knowledge_base", summary="获取知识库详情")(get_kb_detail)
    knowledge_router.post("/create_knowledge_base", summary="创建知识库")(create_kb)
    knowledge_router.post("/update_info", summary="更新知识库")(update_info)
    knowledge_router.delete("/delete_knowledge_base", summary="删除知识库")(delete_kb)
    knowledge_router.post("/search_docs", summary="搜索知识库")(search_docs)
    knowledge_router.post("/rerank_docs", summary="重排知识文档")(rerank_docs)
    knowledge_router.get("/list_files", summary="获取知识库内的文件列表")(list_files)
    knowledge_router.post("/list_docs", summary="获取知识库文档的分段内容")(list_docs)
    knowledge_router.post("/update_docs_by_id", summary="直接更新知识库文档")(update_docs_by_id)
    knowledge_router.post("/upload_docs", summary="上传文件到知识库，并/或进行向量化")(upload_docs)
    knowledge_router.post("/delete_docs", summary="删除知识库内指定文件")(delete_docs)
    knowledge_router.post("/update_docs", summary="更新现有文件到知识库")(update_docs)
    knowledge_router.put("/update_enabled", summary="更新文件状态")(update_enabled)
    knowledge_router.get("/download_doc", summary="下载对应的知识文件")(download_doc)
    knowledge_router.post("/recreate_vector_store", summary="根据content中文档重建向量库。")(recreate_vector_store)
    knowledge_router.post("/upload_temp_docs", summary="上传文件到临时目录，用于文件对话。")(upload_temp_docs)
    knowledge_router.post("/delete_temp_docs", summary="删除临时文件")(delete_temp_docs)
    knowledge_router.post("/kb_summary_api/summary_file_to_vector_store",
                          summary="单个知识库根据文件名称摘要"
                          )(summary_file_to_vector_store)
    knowledge_router.post("/kb_summary_api/summary_doc_ids_to_vector_store",
                          summary="单个知识库根据doc_ids摘要",
                          )(summary_doc_ids_to_vector_store)
    knowledge_router.post("/kb_summary_api/recreate_summary_vector_store",
                          summary="重建单个知识库文件摘要"
                          )(recreate_summary_vector_store)

    app.include_router(knowledge_router)
    return knowledge_router


def mount_model_routes(app: FastAPI):
    from server.llm_api import (list_running_models, list_config_models,
                                change_llm_model, stop_llm_model,
                                get_model_config)

    model_router = APIRouter(prefix="/llm_model", tags=["LLM Model Management"])
    # LLM模型相关接口
    model_router.post("/list_running_models", summary="列出当前已加载的模型", )(list_running_models)
    model_router.post("/list_config_models", summary="列出configs已配置的模型", )(list_config_models)
    model_router.post("/get_model_config", summary="获取模型配置（合并后）", )(get_model_config)
    model_router.post("/stop", summary="停止指定的LLM模型（Model Worker)", )(stop_llm_model)
    model_router.post("/change", summary="切换指定的LLM模型（Model Worker)", )(change_llm_model)

    app.include_router(model_router)
    return model_router


def mount_tool_routes(app: FastAPI):
    from server.chat.agent_chat import call_tool
    from server.agent.tools_select import built_in_tools, create_tool, update_tool, delete_tool, get_tools, \
        get_tool_detail, child_tools

    tool_router = APIRouter(prefix="/tools", tags=["Toolkits"])
    # 工具相关
    tool_router.post("/built_in", summary="内置工具信息")(built_in_tools)
    tool_router.post("/create", summary="创建工具")(create_tool)
    tool_router.put("/update", summary="更新工具")(update_tool)
    tool_router.delete("/delete", summary="删除工具")(delete_tool)
    tool_router.get("/list", summary="分页查询工具列表")(get_tools)
    tool_router.get("/detail", summary="获取工具详情")(get_tool_detail)
    tool_router.post("/child_tools", summary="子工具信息")(child_tools)
    tool_router.post("/call", summary="调用工具")(call_tool)

    app.include_router(tool_router)
    return tool_router


def mount_server_routes(app: FastAPI):
    from server.llm_api import list_search_engines
    from server.utils import get_server_configs, get_prompt_template

    server_router = APIRouter(prefix="/server", tags=["Server State"])
    # 服务器相关接口
    server_router.post("/configs", summary="获取服务器原始配置信息", )(get_server_configs)
    server_router.post("/list_search_engines", summary="获取服务器支持的搜索引擎", )(list_search_engines)

    @server_router.post("/get_prompt_template", summary="获取服务区配置的 prompt 模板")
    def get_server_prompt_template(
            type: Literal["llm_chat", "knowledge_base_chat", "search_engine_chat", "agent_chat"] = Body("llm_chat",
                                                                                                        description="模板类型，可选值：llm_chat，knowledge_base_chat，search_engine_chat，agent_chat"),
            name: str = Body("default", description="模板名称"),
    ) -> str:
        return get_prompt_template(type=type, name=name)

    app.include_router(server_router)
    return server_router


def mount_workflow_routes(app: FastAPI):
    from server.workflow.workflow_api import get_components, construct_component

    workflow_router = APIRouter(prefix="/workflow", tags=["Workflow"])

    workflow_router.get("/components", summary="工作流组件信息")(get_components)
    workflow_router.get("/construct_component", summary="生成一个组件")(construct_component)

    app.include_router(workflow_router)
    return workflow_router


def mount_openapi_routes(app: FastAPI):
    from server.knowledge_base.kb_doc_api import retrieval
    from server.chat.chat_router import chat_router as chats

    openapi_router = APIRouter(prefix="/openapi", tags=["Openapi"])
    openapi_router.post("/retrieval", summary="搜索知识库")(retrieval)
    openapi_router.post("/chat", summary="各种对话的总入口", )(chats)
    app.include_router(openapi_router)

    return openapi_router


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
