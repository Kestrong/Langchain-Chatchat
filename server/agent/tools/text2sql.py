from langchain_community.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseSequentialChain
from pydantic import BaseModel, Field

from configs import logger, text2sql as text2sql_config, log_verbose
from server.agent import model_container
from server.agent.tools_select import register_tool
from server.db.base import create_engine_wrapper
from server.utils import get_ChatOpenAI


class Text2SqlInput(BaseModel):
    query: str = Field(description="Query to be converted into SQL")


@register_tool(title="文本转SQL",
               description="Use this tool to translate input question into SQL.",
               args_schema=Text2SqlInput)
def text2sql(query: str):
    origin_query = query
    model_name = model_container.MODEL.metadata.get("origin_model_name", model_container.MODEL.model_name)
    table_names = text2sql_config["table_names"]
    table_comments = text2sql_config["table_comments"]
    sqlalchemy_connect_str = text2sql_config["sqlalchemy_connect_str"]
    sqlalchemy_schema = text2sql_config["sqlalchemy_schema"]
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
            return_sql=True,
            use_query_checker=True
        )
        result = db_chain.run({"query": query})
        logger.debug(f"query:{origin_query},\nsql:{result}")
        return f"生成的SQL如下：{result}"
    except Exception as e:
        logger.error(f'{e.__class__.__name__}: {e}', exc_info=e if log_verbose else None)
        return "生成SQL失败，可能是数据库无法访问或者您描述的内容大模型无法理解。"
    finally:
        if engine:
            try:
                engine.clear_compiled_cache()
                engine.pool.dispose()
            except:
                pass
