import json
import re
from concurrent.futures import ThreadPoolExecutor, Future
from copy import copy
from datetime import date, datetime, time
from typing import Dict, Any, Optional, Union, Literal, Sequence, List

from fastapi.encoders import jsonable_encoder
from langchain.chains import LLMChain
from langchain.chains.sql_database.prompt import PROMPT
from langchain_community.chat_models import ChatOpenAI
from langchain_community.tools.sql_database.prompt import QUERY_CHECKER
from langchain_community.utilities import SQLDatabase
from langchain_community.utilities.sql_database import _format_index
from langchain_core.callbacks import CallbackManagerForChainRun
from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import PromptTemplate, BasePromptTemplate
from langchain_experimental.sql import SQLDatabaseSequentialChain, SQLDatabaseChain
from langchain_experimental.sql.base import SQL_QUERY, INTERMEDIATE_STEPS_KEY
from pydantic import BaseModel, Field
from sqlalchemy import event, Executable, Result, Table, select, quoted_name
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.sql.ddl import CreateTable
from sqlalchemy.sql.sqltypes import NullType

from common.exceptions import ChatBusinessException
from configs import logger, log_verbose, MAX_TOKENS_INPUT
from server.agent import get_model_container, ModelContainer
from server.agent.tools_select import register_tool
from server.db.base import create_engine_wrapper
from server.knowledge_base.kb_doc_api import search_docs
from server.memory.message_i18n import Message_I18N
from server.utils import get_ChatOpenAI, get_tool_config, parse_json_md, parse_sql_md

_DECIDER_TEMPLATE = """Given a question and a JSON map below where the key is the table name and the value is the table description. 
Table Map: {table_names}
Question: {query}
Let's think step by step. 
1. Deeply understand the description of each table, determine which tables are most relevant to the question.
2. If you want to convert the question into SQL query which tables you should choose. 
3. There must be a clear logical connection between the question and the chosen table, every table maybe has same relevant tables, make sure you don't miss them. 
Please only output a json list of the table names that may be necessary to answer this question directly. If no table is relevant according to the question, output an empty list []. 
You are not allowed to output anything else outside of this specification. Only a list of table name in map or [] can return.
Output:your answer here
"""

DECIDER_PROMPT = PromptTemplate(input_variables=["query", "table_names"], template=_DECIDER_TEMPLATE, )

_DECIDER_DB_TEMPLATE = """
你是一个专业的数据库管理员，给定下面的数据库信息和自然语言描述的问题，判断哪个数据库与问题最相关？
数据库信息: {database_names}，其中key是数据库名称value是数据库描述。
问题: {query}
请你深吸一口气，让我们一步一步来思考。
1. 请详细阅读和理解每个数据库的描述，确定哪个数据库与问题最相关。
2. 明确问题想要查询的数据主体，如果要把问题转换成SQL查询，你会选择哪个数据库。
3. 如果找到了相关的数据库，直接输出它的名称。如果没有找到相关的数据库，则输出空字符串""。
在给出最终答案前认真分析，你只能返回数据库的名称或""，不允许输出其他内容。\n答案：
"""

DECIDER_DB_PROMPT = PromptTemplate(input_variables=["query", "database_names"], template=_DECIDER_DB_TEMPLATE, )

_mysql_prompt = """
You are a data science expert. Below, you are provided with a database schema and a natural language question. Your task is to understand the schema and generate a valid SQL query to answer the question.

Database Engine:
{dialect}

Database Schema:
{table_info}
This schema describes the database's structure, including tables, columns, primary keys, foreign keys, and any relevant relationships or constraints.

Question:
{input}\n忽略问题里面提到的返回记录数，以下面的指示为准。

Instructions:
1. Only return {top_k} results using the LIMIT clause as per SQL. You can order the results to return the most informative data in the database.
2. Generate an unique alias for each table and use it to prefix each column in the table to avoid ambiguity.
3. Only select columns necessary to answer the question; do not use `SELECT *`. Make sure at least one column from each involved table is queried.
4. Pay attention to use only the column names from which table you have use in SQL. Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.
5. For questions involving "today", utilize the `CURRENT_DATE` function to get the current date. 
6. Not allowed to use LIKE in JOIN conditions. Use the IN clause instead of multiple OR conditions for better readability and performance.
7. If no time column specify in this question, and create time column exist in SQL prefer to use create time.
8. Complete in one SQL, do not allow to use SET statements.

Follow this format strictly:
Question: Your question here
SQLQuery: Your SQL query here

Before generating the final SQL query, please think through the steps of how to write the query. Take a deep breath and think step by step to find the correct SQL query.
"""

MYSQL_PROMPT = PromptTemplate(
    input_variables=["input", "table_info", "top_k"],
    template=_mysql_prompt,
)

_postgres_prompt = _mysql_prompt

POSTGRES_PROMPT = PromptTemplate(
    input_variables=["input", "table_info", "top_k"],
    template=_postgres_prompt,
)

SQL_PROMPTS = {
    "mysql": MYSQL_PROMPT,
    "postgresql": POSTGRES_PROMPT,
}

SQL_WRAPPER = {"mysql": "`"}


class CustomSQLDatabaseChain(SQLDatabaseChain):

    def execute_with_retry(self, sql_cmd, inputs, max_retries=3):
        attempt = 0
        origin_error = None
        table_info = inputs.get("table_info")
        dialect = inputs.get("dialect")
        prompt = """You are a database administrator, given the information below,
        
                    Database Engine: 
                    {dialect}
                    
                    Database Schema:
                    {table_info}
                    This schema describes the database's structure, including tables, columns, primary keys, foreign keys, and any relevant relationships or constraints.
                    
                    SQL: {sql}
                    
                    Error info: {error_info}
                    
                    Instructions:
                    
                    1. Deeply understand the table info.
                    2. According to the error info try to fix the SQL problems.
                    3. Just output the sql directly without other words.
                    
                    Output Format:
                    In your answer, please enclose the generated SQL query in a code block:
                    ```
                    -- Your SQL query
                    ```
                    
                    Before generating the final SQL query, please think through the steps of how to write the query. Take a deep breath and think step by step to find the correct SQL query.
                    """
        template = PromptTemplate(input_variables=["error_info", "table_info", "dialect", "sql"],
                                  template=prompt)
        chain = LLMChain(llm=self.llm_chain.llm, prompt=template)
        while attempt <= max_retries:
            try:
                result = self.database.run(command=sql_cmd, include_columns=True)
                return sql_cmd, result
            except Exception as e:
                if attempt == 0:
                    origin_error = e
                if attempt >= max_retries:
                    raise origin_error
                else:
                    # 调用大模型服务以获得修改建议
                    attempt += 1
                    modified_sql_cmd = chain.predict(
                        sql=sql_cmd,
                        error_info=str(e).split('\n')[0],
                        table_info=table_info,
                        dialect=dialect,
                    )
                    sql_cmd = parse_sql_md(modified_sql_cmd)

    def _call(
            self,
            inputs: Dict[str, Any],
            run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, Any]:
        _run_manager = run_manager or CallbackManagerForChainRun.get_noop_manager()
        input_text = f"{inputs[self.input_key]}\n{SQL_QUERY}"
        _run_manager.on_text(input_text, verbose=self.verbose)
        # If not present, then defaults to None which is all tables.
        table_names_to_use = inputs.get("table_names_to_use")
        intermediate_steps: List = []
        if not table_names_to_use and not inputs.get("sql_cmd"):
            return {self.output_key: None, INTERMEDIATE_STEPS_KEY: None}
        table_info = self.database.get_table_info(table_names=table_names_to_use)
        llm_inputs = {
            "input": input_text,
            "top_k": str(self.top_k),
            "dialect": self.database.dialect,
            "table_info": table_info,
            "stop": ["\nSQLResult:"],
        }
        if self.memory is not None:
            for k in self.memory.memory_variables:
                llm_inputs[k] = inputs[k]
        try:
            intermediate_steps.append(llm_inputs.copy())  # input: sql generation
            sql_cmd = inputs["sql_cmd"] if inputs["sql_cmd"] else self.llm_chain.predict(
                callbacks=_run_manager.get_child(),
                **llm_inputs,
            ).strip()
            if self.return_sql:
                return {self.output_key: sql_cmd, INTERMEDIATE_STEPS_KEY: None}
            if inputs["sql_cmd"]:
                _run_manager.on_text(sql_cmd, color="green", verbose=self.verbose)
                intermediate_steps.append(
                    sql_cmd
                )  # output: sql generation (no checker)
                if SQL_QUERY in sql_cmd:
                    sql_cmd = sql_cmd.split(SQL_QUERY)[1].strip()
                result = self.database.run(command=sql_cmd, include_columns=True)
                intermediate_steps.append(result)  # output: sql exec
            else:
                if self.use_query_checker:
                    query_checker_prompt = self.query_checker_prompt or PromptTemplate(
                        template=QUERY_CHECKER, input_variables=["query", "dialect"]
                    )
                    query_checker_chain = LLMChain(
                        llm=self.llm_chain.llm, prompt=query_checker_prompt
                    )
                    query_checker_inputs = {
                        "query": sql_cmd,
                        "dialect": self.database.dialect,
                    }
                    checked_sql_command: str = query_checker_chain.predict(
                        callbacks=_run_manager.get_child(), **query_checker_inputs
                    ).strip()
                    _run_manager.on_text(
                        checked_sql_command, color="green", verbose=self.verbose
                    )
                else:
                    checked_sql_command = sql_cmd
                checked_sql_command = parse_sql_md(checked_sql_command)
                if SQL_QUERY in checked_sql_command:
                    checked_sql_command = checked_sql_command.split(SQL_QUERY)[1].strip()
                checked_sql_command, result = self.execute_with_retry(checked_sql_command, llm_inputs)
                intermediate_steps.append(
                    checked_sql_command
                )  # output: sql generation (checker)
                intermediate_steps.append(result)  # output: sql exec
                sql_cmd = checked_sql_command

            _run_manager.on_text("\nSQLResult: ", verbose=self.verbose)
            _run_manager.on_text(result, color="yellow", verbose=self.verbose)
            # If return direct, we just set the final result equal to
            # the result of the sql query result, otherwise try to get a human readable
            # final answer
            if self.return_direct:
                final_result = result
            else:
                _run_manager.on_text("\nAnswer:", verbose=self.verbose)
                input_text += f"{sql_cmd}\nSQLResult: {result}\nAnswer:"
                llm_inputs["input"] = input_text
                intermediate_steps.append(llm_inputs.copy())  # input: final answer
                final_result = self.llm_chain.predict(
                    callbacks=_run_manager.get_child(),
                    **llm_inputs,
                ).strip()
                intermediate_steps.append(final_result)  # output: final answer
                _run_manager.on_text(final_result, color="green", verbose=self.verbose)
            chain_result: Dict[str, Any] = {self.output_key: final_result}
            if self.return_intermediate_steps:
                chain_result[INTERMEDIATE_STEPS_KEY] = intermediate_steps
            return chain_result
        except Exception as exc:
            # Append intermediate steps to exception, to aid in logging and later
            # improvement of few shot prompt seeds
            exc.intermediate_steps = intermediate_steps  # type: ignore
            raise exc


class CustomSQLDatabaseSequentialChain(SQLDatabaseSequentialChain):
    fill_table_in_prompt: bool = True

    @classmethod
    def from_llm(
            cls,
            llm: BaseLanguageModel,
            db: SQLDatabase,
            query_prompt: BasePromptTemplate = PROMPT,
            decider_prompt: BasePromptTemplate = DECIDER_PROMPT,
            **kwargs: Any,
    ) -> SQLDatabaseSequentialChain:
        """Load the necessary chains."""
        sql_chain = CustomSQLDatabaseChain.from_llm(llm, db, prompt=query_prompt, **kwargs)
        decider_chain = LLMChain(
            llm=llm, prompt=decider_prompt, output_key="table_names"
        )
        return cls(sql_chain=sql_chain, decider_chain=decider_chain, **kwargs)

    def _call(
            self,
            inputs: Dict[str, Any],
            run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, Any]:
        _run_manager = run_manager or CallbackManagerForChainRun.get_noop_manager()
        _table_names = self.sql_chain.database.get_usable_table_names()
        llm_inputs = {
            "query": inputs[self.input_key],
            "table_names": "{}",
        }
        if self.fill_table_in_prompt:
            _table_comments = {}
            table_comments = self.sql_chain.database.__getattribute__('table_comments')
            for a in self.sql_chain.database._metadata.sorted_tables:
                if table_comments and table_comments.get(a.name):
                    a.comment = table_comments.get(a.name)
                _table_comments[a.name] = a.comment
            table_names_comment_map = {t: _table_comments.get(t) or "" for t in _table_names}
            llm_inputs["table_names"] = f"{table_names_comment_map}"
        table_names_predict_ = self.decider_chain.predict(**llm_inputs)
        _run_manager.on_text(f"Table names predict:{table_names_predict_}", end="\n", verbose=self.verbose)
        table_names_predict = []
        for t in json.loads(parse_json_md(table_names_predict_).replace("'", '"')):
            if isinstance(t, str):
                table_names_predict.append(t.lower())
            elif isinstance(t, dict):
                if len(t) > 0:
                    table_names_predict.append(next(iter(t)).lower())

        table_names_to_use = []
        for name_predict in table_names_predict:
            for _table_name in _table_names:
                lower_table_name = _table_name.lower()
                if name_predict == lower_table_name:
                    table_names_to_use.append(_table_name)
                    break
                if name_predict.replace(SQL_WRAPPER.get(self.sql_chain.database.dialect),
                                        '') == lower_table_name.replace(
                    SQL_WRAPPER.get(self.sql_chain.database.dialect), ''):
                    table_names_to_use.append(_table_name)
                    break
                parts = lower_table_name.split(".")
                if len(parts) > 1 and name_predict == parts[1]:
                    table_names_to_use.append(_table_name)
                    break
        _run_manager.on_text("Table names to use:", end="\n", verbose=self.verbose)
        _run_manager.on_text(
            str(table_names_to_use), color="yellow", verbose=self.verbose
        )
        new_inputs = {
            self.sql_chain.input_key: inputs[self.input_key],
            "table_names_to_use": table_names_to_use,
            "sql_cmd": inputs["sql_cmd"]
        }
        return self.sql_chain(
            new_inputs, callbacks=_run_manager.get_child(), return_only_outputs=True
        )


class CustomSQLDatabase(SQLDatabase):
    table_comments: dict = {}

    def _get_sample_rows(self, table: Table) -> str:
        # build the select command
        name_parts = table.name.split(".")
        if len(name_parts) == 2:
            copy_table = copy(table)
            copy_table.name = quoted_name.construct(name_parts[1].replace(SQL_WRAPPER.get(self.dialect, ""), ""),
                                                    True)
            copy_table.schema = quoted_name.construct(name_parts[0].replace(SQL_WRAPPER.get(self.dialect, ""), ""),
                                                      True)
            for a in copy_table.c:
                a.table.name = copy_table.name
                a.table.schema = copy_table.schema
        else:
            copy_table = table
        command = select(copy_table).limit(self._sample_rows_in_table_info)
        # save the columns in string format
        columns_str = "\t".join([col.name for col in table.columns])

        try:
            # get the sample rows
            with self._engine.connect() as connection:
                sample_rows_result = connection.execute(command)  # type: ignore
                # shorten values in the sample rows
                sample_rows = list(
                    map(lambda ls: [str(i)[:100] for i in ls], sample_rows_result)
                )
            if not sample_rows:
                return ""
            # save the sample rows in string format
            sample_rows_str = "\n".join(["\t".join(row) for row in sample_rows])

        # in some dialects when there are no rows in the table a
        # 'ProgrammingError' is returned
        except ProgrammingError as e:
            return ""

        return (
            f"{self._sample_rows_in_table_info} rows from {table.name} table:\n"
            f"{columns_str}\n"
            f"{sample_rows_str}"
        )

    def get_table_info(self, table_names: Optional[List[str]] = None) -> str:
        table_names = [a.lower() for a in table_names]
        all_table_names = [a.lower() for a in self.get_usable_table_names()]
        if table_names is not None:
            missing_tables = set(table_names).difference(all_table_names)
            if missing_tables:
                raise ValueError(f"table_names {missing_tables} not found in database")
            all_table_names = table_names

        meta_tables = [
            tbl
            for tbl in self._metadata.sorted_tables
            if tbl.name.lower() in set(all_table_names)
               and not (self.dialect == "sqlite" and tbl.name.startswith("sqlite_"))
        ]

        tables = []
        for table in meta_tables:
            if self._custom_table_info and table.name in self._custom_table_info:
                tables.append(self._custom_table_info[table.name])
                continue

            # Ignore JSON datatyped columns
            for k, v in table.columns.items():
                if type(v.type) is NullType:
                    table._columns.remove(v)

            # add create table command
            name_parts = table.name.split(".")
            if len(name_parts) == 2:
                copy_table = copy(table)
                copy_table.name = name_parts[1]
                copy_table.schema = quoted_name.construct(name_parts[0].replace(SQL_WRAPPER.get(self.dialect, ""), ""),
                                                          True)
                create_table = str(CreateTable(copy_table).compile(self._engine))
            else:
                create_table = str(CreateTable(table).compile(self._engine))
            comment_stmt = ""
            if self.dialect == 'postgresql':
                if table.comment:
                    comment_stmt += f"COMMENT ON TABLE {table.name} IS '{table.comment}';\n"
                for column in table.columns:
                    if column.comment:
                        comment_stmt += f"COMMENT ON COLUMN {table.name}.{column.name} IS '{column.comment}';\n"
            table_info = f"{create_table.rstrip()};{comment_stmt}"
            has_extra_info = (
                    self._indexes_in_table_info or self._sample_rows_in_table_info
            )
            extra_info = ""
            if self._indexes_in_table_info:
                index_info = self._get_table_indexes(table)
                if index_info:
                    extra_info += f"\n{index_info}\n"
            if self._sample_rows_in_table_info:
                sample_rows_info = self._get_sample_rows(table)
                if sample_rows_info:
                    extra_info += f"\n{sample_rows_info}\n"
            if has_extra_info and extra_info:
                table_info += f"\n\n/*{extra_info}*/"
            tables.append(table_info)
        tables.sort()
        final_str = "\n\n".join(tables)
        return final_str

    def _get_table_indexes(self, table: Table) -> str:
        indexes = [{"unique": i.unique, "name": i.name, "column_names": [a.name for a in i.columns]} for i in
                   table.indexes]
        indexes_formatted = "\n".join(map(_format_index, indexes))
        return f"Table Indexes:\n{indexes_formatted}"

    def truncate_word(self, content: Any, *, length: int, suffix: str = "...") -> str:
        """
        Truncate a string to a certain number of words, based on the max string
        length.
        """

        if not isinstance(content, str) or length <= 0:
            return content

        if len(content) <= length:
            return content

        return content[: length - len(suffix)] + suffix

    def run(
            self,
            command: Union[str, Executable],
            fetch: Literal["all", "one", "cursor"] = "all",
            include_columns: bool = False,
            *,
            parameters: Optional[Dict[str, Any]] = None,
            execution_options: Optional[Dict[str, Any]] = None,
    ) -> Union[str, Sequence[Dict[str, Any]], Result[Any]]:
        """Execute a SQL command and return a string representing the results.

        If the statement returns rows, a string of the results is returned.
        If the statement returns no rows, an empty string is returned.
        """
        result = self._execute(
            command, fetch, parameters=parameters, execution_options=execution_options
        )

        if fetch == "cursor":
            return result

        res = [
            {
                column: self.truncate_word(value, length=self._max_string_length)
                for column, value in r.items()
            }
            for r in result
        ]

        if not include_columns:
            res = [tuple(row.values()) for row in res]  # type: ignore[misc]

        if not res:
            return []
        else:
            return res

    def _execute(
            self,
            command: Union[str, Executable],
            fetch: Literal["all", "one", "cursor"] = "all",
            *,
            parameters: Optional[Dict[str, Any]] = None,
            execution_options: Optional[Dict[str, Any]] = None,
    ) -> Union[Sequence[Dict[str, Any]], Result]:
        if isinstance(command, str):
            command = parse_sql_md(command)
        return super()._execute(
            command,
            fetch=fetch,
            parameters=parameters,
            execution_options=execution_options,
        )


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
        raise ChatBusinessException(
            Message_I18N.TOOL_SQL_READ_ONLY.value,
        )


def json_dumps(obj, indent=None):
    _custom_encoder = {datetime: lambda o: o.strftime("%Y-%m-%d %H:%M:%S"),
                       time: lambda o: o.strftime("%Y-%m-%d %H:%M:%S"),
                       date: lambda o: o.strftime("%Y-%m-%d %H:%M:%S"), }
    return json.dumps(jsonable_encoder(obj, custom_encoder=_custom_encoder), ensure_ascii=False, indent=indent)


def judge_chart_type(query: str, records: list, llm: ChatOpenAI):
    chart_types = {"line": "折线图", "pie": "饼图", "bar": "柱状图", "table": "表格"}
    chart_json_example = {
        "line": """
        {
            "title": {
                "text": "折线图示例"
            },
            "tooltip": {
                "trigger": "axis"
            },
            "legend": {
                "data": ["邮件营销", "联盟广告"]
            },
            "grid": {
                "left": "3%",
                "right": "4%",
                "bottom": "3%",
                "containLabel": true
            },
            "xAxis": {
                "type": "category",
                "boundaryGap": false,
                "data": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            },
            "yAxis": {
                "type": "value"
            },
            "series": [{
                "name": "邮件营销",
                "type": "line",
                "stack": "总量",
                "data": [120, 132, 101, 134, 90, 230, 210]
            },
            {
                "name": "联盟广告",
                "type": "line",
                "stack": "总量",
                "data": [220, 182, 191, 234, 290, 330, 310]
            }]
        }
        """,
        "pie": """
        {
            "title": {
                "text": "饼图示例"
            },
            "tooltip": {
                "trigger": "item"
            },
            "legend": {
                "orient": "vertical",
                "left": "left"
            },
            "series": [{
                "name": "访问来源",
                "type": "pie",
                "radius": "50%",
                "data": [{
                    "value": 1048,
                    "name": "搜索引擎"
                },
                {
                    "value": 735,
                    "name": "直接访问"
                }],
                "emphasis": {
                    "itemStyle": {
                        "shadowBlur": 10,
                        "shadowOffsetX": 0,
                        "shadowColor": "rgba(0, 0, 0, 0.5)"
                    }
                }
            }]
        }
        """,
        "bar": """
       {
            "title": {
                "text": "柱状图示例"
            },
            "tooltip": {},
            "xAxis": {
                "data": ["衬衫", "羊毛衫"]
            },
            "yAxis": {},
            "series": [{
                "name": "销量",
                "type": "bar",
                "data": [5, 20]
            },
            {
                "name": "价格",
                "type": "bar",
                "data": [5, 20]
            }]
        }
        """
    }
    result_types = set()

    # 更智能的图表类型识别，支持多种表达方式
    line_keywords = ["折线图", "线图", "趋势图", "曲线图", "line graph", "line chart", "trend chart", "curve chart"]
    pie_keywords = ["饼图", "饼状图", "圆饼图", "扇形图", "pie chart", "circle chart", "sector chart"]
    bar_keywords = ["柱状图", "柱图", "条形图", "直方图", "bar graph", "bar chart", "column chart", "histogram"]
    table_keywords = ["表格", "列表", "table", "grid"]

    query_lower = query.lower()

    if any(keyword in query_lower for keyword in line_keywords):
        chart_type = "line"
    elif any(keyword in query_lower for keyword in pie_keywords):
        chart_type = "pie"
    elif any(keyword in query_lower for keyword in bar_keywords):
        chart_type = "bar"
    else:
        chart_type = "table"
    result_types.add(chart_type)

    if any(keyword in query_lower for keyword in table_keywords):
        result_types.add("table")
    chart_json = {}
    if records and chart_type in chart_json_example:
        prompt = """
        你是一个专业的数据可视化工程师，给定以下数据:
        标题(请简化)：{{ query }}
        数据集: {{ records }}
        图表类型: {{chart_type }}
        请你深呼吸，然后让我们一步一步来思考。 
        1. 请充分理解给定的数据集的每一个字段和数值的含义，每个统计数值类型的字段对应一个维度。
        2. 必须使用数据集里面所有的维度并在echart图表里面展示出来，即使为0或者空值也允许展示。
        3. 请直接输出一个符合echart图表规范的json对象，不允许包含其他文字内容。
        4. 输出前检查一遍json的格式是否正确，包裹key和value的双引号必须成对存在，value为对象或数组时不要使用双引号包裹。
        你可以参考以下例子的格式: {{ chart_json_example }}
        """
        try:
            template = PromptTemplate(input_variables=["query", "records", "chart_type", "chart_json_example"],
                                      template=prompt, template_format="jinja2")
            chain = LLMChain(llm=llm, prompt=template)
            chart_json = chain.run(query=query,
                                   records=json_dumps(records),
                                   chart_type=chart_types[chart_type],
                                   chart_json_example=chart_json_example[chart_type])
            chart_json = json.loads(parse_json_md(chart_json))
            # 设置鼠标悬浮提示
            if 'tooltip' not in chart_json:
                chart_json['tooltip'] = {}
            if chart_type == 'pie':
                chart_json['tooltip'] = {"trigger": "item"}
                for s in chart_json['series']:
                    s['label'] = {"show": True, "formatter": "{b}: {c}"}
            else:
                chart_json['tooltip'] = {"trigger": "axis"}
                for s in chart_json['series']:
                    s['label'] = {"show": True, "position": "top"}
            # 坐标太多时旋转标签角度 并设置显示间隔为0
            if 'xAxis' in chart_json:
                xAxis = chart_json['xAxis']
                if 'data' in xAxis:
                    if len(xAxis['data']) > 10:
                        xAxis['axisLabel'] = {"interval": 0, "rotate": 60, "fontSize": 10}
                    else:
                        xAxis['axisLabel'] = {"interval": 0}
        except Exception as e:
            logger.error(f"generate echart json error, error:{e}, json:{chart_json}")
            chart_json = {}
    return list(result_types), chart_json


def get_clean_translate_column(column: str, separator="_"):
    parts = column.split(separator)
    for part in parts:
        if not (part.isascii() and part.isalpha()):
            return part
    return column


class Text2SqlInput(BaseModel):
    natural_language_question: str = Field(description="The user's question in natural language.")


@register_tool(title="文本转SQL",
               description="Use this tool to answer questions about the database by natural language. This tool will convert the natural language question into SQL, execute it, and return the result.",
               args_schema=Text2SqlInput)
def text2sql(natural_language_question: str):
    model_container = get_model_container() or ModelContainer()
    model_container.TOOL_RERUN = False
    query = natural_language_question
    origin_query = query

    text2sql_config_bak = get_tool_config().TOOL_CONFIG.get("text2sql", {})
    text2sql_config: dict = model_container.TOOL_CONFIG.get('text2sql', {})
    model_name = text2sql_config.get('model_name', text2sql_config_bak.get('model_name'))
    db_infos = text2sql_config.get('db_infos', text2sql_config_bak.get('db_infos', {}))
    read_only = text2sql_config_bak.get('read_only', True)
    return_sql = text2sql_config.get('return_sql', text2sql_config_bak.get('return_sql', False))
    return_format = text2sql_config.get('return_format', text2sql_config_bak.get('return_format', 'str'))
    top_k = text2sql_config.get("top_k", text2sql_config_bak.get("top_k", 3))
    use_query_checker = text2sql_config.get("use_query_checker", text2sql_config_bak.get("use_query_checker", False))
    max_string_length = text2sql_config.get("max_string_length", text2sql_config_bak.get("max_string_length", 100))
    sample_rows_in_table_info = text2sql_config.get("sample_rows_in_table_info",
                                                    text2sql_config_bak.get("sample_rows_in_table_info", 0))
    indexes_in_table_info = text2sql_config.get("indexes_in_table_info",
                                                text2sql_config_bak.get("indexes_in_table_info", False))
    use_vector_sample = text2sql_config.get('use_vector_sample', text2sql_config_bak.get('use_vector_sample', False))
    vector_score_threshold = text2sql_config.get('vector_score_threshold',
                                                 text2sql_config_bak.get('vector_score_threshold'))
    vector_search_top_k = text2sql_config.get('vector_search_top_k', text2sql_config_bak.get('vector_search_top_k'))
    engine = None

    try:
        llm = get_ChatOpenAI(
            model_name=model_name,
            temperature=0,
            streaming=True,
            verbose=True,
        )
        sql_cmd = model_container.TOOL_ARGS.get("sql_cmd")
        if not sql_cmd:
            db_infos = {k: v for k, v in db_infos.items() if v.get("generation", True) is True}
        database_comments = {k: v.get("description") for k, v in db_infos.items()}
        if len(db_infos) > 1:
            db_name_from_chain = model_container.TOOL_ARGS.get("db_name")
            if db_name_from_chain not in db_infos:
                decider_db_chain = LLMChain(llm=llm, prompt=DECIDER_DB_PROMPT)
                db_name_from_chain = decider_db_chain.predict(
                    **{"query": query, "database_names": f"{database_comments}"})
                if db_name_from_chain:
                    db_name_from_chain = db_name_from_chain.replace("'", "").replace('"', "").replace("\n", "")
            if db_name_from_chain not in db_infos:
                for k, v in db_infos.items():
                    if v.get("default", False):
                        db_name_from_chain = k
                        break
            if db_name_from_chain not in db_infos:
                logger.error(
                    f"query: {query}, database {db_name_from_chain} not found, available dbs:{list(db_infos.keys())}.")
                return Message_I18N.TOOL_SQL_NOT_CLEAR.value.format(database_comments=list(database_comments.values()))
            db_info = db_infos.get(db_name_from_chain)
            db_name = db_name_from_chain
            knowledgebase = db_name
        else:
            db_info = next(iter(db_infos.values()))
            db_name = next(iter(db_infos.keys()))
            knowledgebase = db_name
        engine = create_engine_wrapper(uri=db_info.get("sqlalchemy_connect_str"), pool_size=1,
                                       connect_args=db_info.get('connect_args') or {})
        db = CustomSQLDatabase(engine=engine, schema=db_info.get("sqlalchemy_schema"),
                               sample_rows_in_table_info=0 if sql_cmd else sample_rows_in_table_info,
                               indexes_in_table_info=indexes_in_table_info,
                               max_string_length=max_string_length, view_support=db_info.get("view_support", False),
                               include_tables=db_info.get("table_names"))
        # 对于mysql等数据库可以使用{{ 库名.表名 }}的形式实现跨库sql查询，所以这边做了个hack
        if db_info.get("ref_dbs"):
            sql_wrapper = SQL_WRAPPER.get(db.dialect, "")
            rename_func = lambda a, b: f"{sql_wrapper}{a}{sql_wrapper}.{b}"
            db._all_tables = [rename_func(db_name, a) for a in db._all_tables]
            db._include_tables = [rename_func(db_name, a) for a in db._include_tables]
            db._ignore_tables = [rename_func(db_name, a) for a in db._ignore_tables]
            db._usable_tables = [rename_func(db_name, a) for a in db._usable_tables]
            if db._custom_table_info:
                db._custom_table_info = {rename_func(db_name, k): v for k, v in db._custom_table_info}
            tables = copy(db._metadata.tables)
            for a, b in tables.items():
                db._metadata._remove_table(name=b.name, schema=b.schema)
                b.name = rename_func(db_name, b.name)
                db._metadata._add_table(name=b.name, table=b, schema=b.schema)
            table_comments = {}
            for table_name, table_comment in db_info.get("table_comments", {}).items():
                table_comments[rename_func(db_name, table_name)] = table_comment
            ref_dbs: dict = db_info.get("ref_dbs")
            for k, v in ref_dbs.items():
                ref_engine = create_engine_wrapper(uri=v.get("sqlalchemy_connect_str"), pool_size=1)
                try:
                    ref_db = CustomSQLDatabase(engine=ref_engine, schema=v.get("sqlalchemy_schema"),
                                               sample_rows_in_table_info=1,
                                               max_string_length=max_string_length,
                                               view_support=v.get("view_support", False),
                                               include_tables=v.get("table_names"))
                    db._all_tables += [rename_func(k, a) for a in ref_db._all_tables]
                    db._include_tables += [rename_func(k, a) for a in ref_db._include_tables]
                    db._ignore_tables += [rename_func(k, a) for a in ref_db._ignore_tables]
                    db._usable_tables += [rename_func(k, a) for a in ref_db._usable_tables]
                    if ref_db._custom_table_info:
                        for kk, vv in ref_db._custom_table_info:
                            db._custom_table_info[rename_func(k, kk)] = vv
                    for a, b in ref_db._metadata.tables.items():
                        b.name = rename_func(k, b.name)
                        db._metadata._add_table(name=b.name, table=b, schema=b.schema)
                    ref_db_table_comments = v.get("table_comments", {})
                    for table_name, table_comment in ref_db_table_comments.items():
                        table_comments[rename_func(k, table_name)] = table_comment
                finally:
                    if ref_engine:
                        try:
                            ref_engine.clear_compiled_cache()
                            ref_engine.pool.dispose()
                        except:
                            pass
        else:
            table_comments = db_info.get("table_comments", {})
        db.table_comments = table_comments

        if read_only:
            event.listen(engine, "before_cursor_execute", intercept_sql)

        db_chain = CustomSQLDatabaseSequentialChain.from_llm(
            llm,
            db,
            decider_prompt=DECIDER_PROMPT,
            query_prompt=SQL_PROMPTS.get(db.dialect),
            verbose=True,
            top_k=top_k,
            return_sql=return_sql,
            return_direct=True,
            use_query_checker=use_query_checker,
            return_intermediate_steps=True,
        )

        report_prompt = model_container.TOOL_ARGS.get("report_prompt")
        if not report_prompt:
            report_prompt = text2sql_config.get('report_prompt', text2sql_config_bak.get('report_prompt'))

        if sql_cmd:
            db_chain.fill_table_in_prompt = False
            sql_few_shot_prompt = f"\n\nYou must use this SQL directly for the question:{sql_cmd}\n\n"
            query += sql_few_shot_prompt
        elif use_vector_sample:
            docs = search_docs(
                query=re.sub(r'[，。;；？?!！]', ' ', origin_query),
                knowledge_base_name=knowledgebase,
                top_k=vector_search_top_k,
                score_threshold=vector_score_threshold,
                file_name="",
                metadata={},
            )
            if docs:
                sql_few_shot_prompt = "\n".join([d.page_content for d in docs])
                query = f"\n你可以参考以下问题及对应的SQL，注意学习查询条件跟问题之间的关系以及如何调整参数值和选择合适的函数:\n{sql_few_shot_prompt}\n好了，现在让我们来解决这个问题：{query}"
        query = f'{query}，当前时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        result = db_chain.invoke({"query": query, "sql_cmd": sql_cmd})
        if not result or result.get('result') is None:
            logger.error(f"SQL generate can not accomplish, query:{origin_query}, database:{db_name}")
            return Message_I18N.TOOL_SQL_NOT_CLEAR.value.format(database_comments=list(database_comments.values()))
        if return_sql:
            sql = result['result']
            logger.info(f"knowledgebase:{knowledgebase},\n query:{origin_query},\n sql:{sql}")
            if return_format == "json":
                return json.dumps({"sql": parse_sql_md(sql)}, ensure_ascii=False)
            return Message_I18N.TOOL_SQL_PRODUCE.value.format(sql=parse_sql_md(sql))
        # 0:输入参数 1:sql 2:execute_result
        intermediate_steps = result["intermediate_steps"]
        sql = intermediate_steps[1]
        records = intermediate_steps[2]
        table_info = intermediate_steps[0]['table_info']
        logger.info(f"knowledgebase:{knowledgebase},\n query:{origin_query},\n sql:{sql}")
        if not records and not sql_cmd:
            summarize = "很抱歉，本次查询没有返回数据。请检查您提供的查询条件是否准确，例如：\n1. 姓名的拼写是否正确和完整；\n2. 区域的命名是否跟业务上一致；\n3. 查询时间是否明确上周、本月或者完整的年月日；\n4. 其他可能影响查询的条件或语法上造成的歧义等；\n5. 数据库确实存在此类数据。\n\n如果您已经检查过以上几点并确认无误，可以重新提问一次或者换个问题尝试。"
        else:
            records = records[:top_k]
            summarize_template = PromptTemplate(input_variables=["query", "records", "report_prompt"],
                                                template=report_prompt, template_format="jinja2")
            summarize_chain = LLMChain(llm=llm, prompt=summarize_template)
            used_token_count = len(origin_query) + len(report_prompt) + 1500
            with ThreadPoolExecutor() as executor:
                summarize = executor.submit(summarize_chain.predict,
                                            **{"query": origin_query,
                                               "records": f"{shorter_records(records, used_token_count)}",
                                               "report_prompt": report_prompt})
        column_map = {}
        if isinstance(records, list) and len(records) > 0:
            translate_prompt = """你是一个翻译专家。你可以参考以下给定的SQL和表信息：
                    SQL: {{ sql }},
                    表信息: {{ table_info }},
                    现在深吸一口气，让我们一步一步来思考，请将这些列名翻译成中文：{{ columns }}。
                    1. 如果某个列名已经是中文，则直接使用列名作为翻译后的内容；
                    2. 确保翻译后的内容仅包含中文字符但是括号内的单位要保留，忽略下划线后无实际意义的字符，并且尽可能简短；
                    3. 如果某个列名无法直接翻译则通过sql和表信息推断其实际含义，推断不出时直接使用列名作为翻译。
                    现在，请根据以上要求直接输出一个JSON对象，其中key是列名，value是翻译后的内容。
                    """
            translate_template = PromptTemplate(input_variables=["sql", "table_info", "columns"],
                                                template=translate_prompt, template_format="jinja2")
            translate_chain = LLMChain(llm=llm, prompt=translate_template)
            try:
                p = translate_chain.predict(
                    **{"sql": sql, "table_info": table_info, "columns": records[0].keys()})
                column_map = {column: get_clean_translate_column(chinese) for column, chinese in
                              json.loads(parse_json_md(p).replace("'", '"')).items()}
            except Exception as e:
                logger.error(f'translate column error:{e}')
        translate_records = [{column_map.get(k, k): v for k, v in rec.items()} for rec in records]
        chart_type, chart_json = judge_chart_type(origin_query, translate_records, llm)
        if isinstance(summarize, Future):
            summarize = summarize.result()
        if return_format == "json":
            return json_dumps(
                {"column_map": column_map, "records": records,
                 "chart_type": chart_type,
                 "chart_json": chart_json,
                 "summarize": summarize,
                 "metadata": {"sql": parse_sql_md(sql), "table_info": table_info, "db_name": db_name,
                              "fix_sql": True if sql_cmd else False}})
        return Message_I18N.TOOL_SQL_DETAIL_PRODUCE.value.format(sql=parse_sql_md(sql),
                                                                 records=json_dumps(
                                                                     {"chart_type": chart_type,
                                                                      "chart_json": chart_json,
                                                                      "column_map": column_map,
                                                                      "records": records, }, indent=4),
                                                                 summarize=summarize)
    except Exception as e:
        error_info = str(e)
        logger.error(f'{e.__class__.__name__}: {e}', exc_info=e if log_verbose else None)
        if isinstance(e, ChatBusinessException):
            return error_info
        if 'timeout' in error_info or 'time out' in error_info or 'timed out' in error_info:
            return Message_I18N.TOOL_SQL_TIMEOUT.value
        return Message_I18N.TOOL_SQL_ERROR.value.format(error=error_info.split("\n")[0])
    finally:
        if engine:
            try:
                engine.clear_compiled_cache()
                engine.pool.dispose()
            except:
                pass


def shorter_records(records: list, used_count: int = 0):
    result = []
    length = 0
    for rr in records:
        r_str = json_dumps(rr)
        length += len(r_str)
        if length > MAX_TOKENS_INPUT - used_count:
            break
        result.append(r_str)
    return result


if __name__ == '__main__':
    for i in range(10):
        r = text2sql("查看海涛和程丽上个月的告警明细")
        print(r)
