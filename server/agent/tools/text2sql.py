from langchain_community.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseSequentialChain
from pydantic import BaseModel, Field
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from configs import logger, log_verbose
from server.agent import get_model_container
from server.agent.tools.aes import decrypt_placeholder
from server.agent.tools_select import register_tool
from server.db.base import create_engine_wrapper
from server.memory.message_i18n import Message_I18N
from server.utils import get_ChatOpenAI, get_tool_config


# 定义一个拦截器函数来检查SQL语句，以支持read-only,可修改下面的write_operations，以匹配你使用的数据库写操作关键字
def intercept_sql(conn, cursor, statement, parameters, context, executemany):
    # List of SQL keywords that indicate a write operation
    write_operations = (
        "insert",
        "update",
        "delete",
        "create",
        "drop",
        "alter",
        "truncate",
        "rename",
    )
    # Check if the statement starts with any of the write operation keywords
    if any(statement.strip().lower().startswith(op) for op in write_operations):
        raise OperationalError(
            "Database is read-only. Write operations are not allowed.",
            params=None,
            orig=None,
        )


class Text2SqlInput(BaseModel):
    query: str = Field(description="user input")


@register_tool(title="文本转SQL",
               description="Use this tool to chat with database,Input natural language, then it will convert it into SQL(remind to clean up ```sql```) and execute it in the database, then return the execution result.",
               args_schema=Text2SqlInput)
def text2sql(query: str):
    origin_query = query
    model_container = get_model_container()

    text2sql_config_bak = get_tool_config().TOOL_CONFIG.get("text2sql", {})
    text2sql_config: dict = model_container.TOOL_CONFIG.get('text2sql', {})
    model_name = model_container.MODEL.metadata.get("origin_model_name", model_container.MODEL.model_name)
    table_names = text2sql_config.get('table_names', text2sql_config_bak.get('table_names'))
    table_comments = text2sql_config.get('table_comments', text2sql_config_bak.get('table_names'))

    sqlalchemy_connect_str = decrypt_placeholder(text2sql_config.get('sqlalchemy_connect_str',
                                                 text2sql_config_bak.get('sqlalchemy_connect_str')))
    sqlalchemy_schema = text2sql_config.get('sqlalchemy_schema', text2sql_config_bak.get('sqlalchemy_schema'))
    read_only = text2sql_config_bak.get('read_only', True)
    return_sql = text2sql_config.get('return_sql', text2sql_config_bak.get('return_sql', False))
    return_intermediate_steps = text2sql_config.get('return_intermediate_steps',
                                                    text2sql_config_bak.get('return_intermediate_steps', True))
    top_k = min(text2sql_config.get("top_k", text2sql_config_bak.get("top_k", 3)), 10)
    engine = None

    try:
        engine = create_engine_wrapper(uri=sqlalchemy_connect_str, pool_size=1)
        db = SQLDatabase(engine=engine, schema=sqlalchemy_schema, sample_rows_in_table_info=1, max_string_length=500,
                         include_tables=table_names)

        if table_comments:
            TABLE_COMMENT_PROMPT = (
                "\n\nI will provide some special notes for a few tables:\n\n"
            )
            table_comments_str = "\n".join([f"{k}:{v}" for k, v in table_comments.items()])
            query = query + TABLE_COMMENT_PROMPT + table_comments_str + "\n\n"

        if read_only:
            event.listen(engine, "before_cursor_execute", intercept_sql)

        llm = get_ChatOpenAI(
            model_name=model_name,
            temperature=0.1,
            streaming=True,
            verbose=True,
        )

        db_chain = SQLDatabaseSequentialChain.from_llm(
            llm,
            db,
            verbose=True,
            top_k=top_k,
            return_sql=return_sql,
            use_query_checker=True,
            return_intermediate_steps=return_intermediate_steps
        )
        result = db_chain.invoke({"query": query})
        context = result['result'] + "\n\n"
        if return_sql:
            logger.debug(f"query:{origin_query},\nsql:{context}")
            return Message_I18N.TOOL_SQL_PRODUCE.value.format(result=context)
        intermediate_steps = result["intermediate_steps"]
        # 如果存在intermediate_steps，且这个数组的长度大于2，则保留最后两个元素，因为前面几个步骤存在示例数据，容易引起误解
        if intermediate_steps:
            if len(intermediate_steps) > 2:
                sql_detail = intermediate_steps[-2:-1][0]["input"]
                # sql_detail截取从SQLQuery到Answer:之间的内容
                sql_detail = sql_detail[
                             sql_detail.find("SQLQuery:") + 9: sql_detail.find("Answer:")
                             ]
                logger.debug(f"query:{origin_query},\nsql:{sql_detail}")
                context = context + sql_detail + "\n\n"
        return context

    except Exception as e:
        logger.error(f'{e.__class__.__name__}: {e}', exc_info=e if log_verbose else None)
        return f'{e}'
    finally:
        if engine:
            try:
                engine.clear_compiled_cache()
                engine.pool.dispose()
            except:
                pass
