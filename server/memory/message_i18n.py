import enum

from server.memory.token_info_memory import is_english

message_i18n_map = {
    "COMMON_CALL_SUCCESS": {
        "zh": "调用成功",
        "en": "SUCCESS"
    },
    "COMMON_CALL_FAILED": {
        "zh": "调用失败",
        "en": "ERROR"
    },
    "COMMON_PARSE_FAILED": {
        "zh": "解析失败",
        "en": "parse error"
    },

    "TOOL_CALCULATE_ERROR": {
        "zh": "```{query}```表达式无法被numexpr解析执行",
        "en": "The expression ```{query}``` cannot be parsed and executed by numuxpr"
    },
    "TOOL_SEARCH_KNOWLEDGEBASE_EMPTY": {
        "zh": "没有找到相关文档,请更换关键词或者知识库重试",
        "en": "No relevant documents found, please change keywords or knowledge base and try again"
    },
    "TOOL_SQL_NO_RECORD": {
        "zh": "对不起，没有查询到数据，请您换个问题或者修改问题的查询条件后重新提问，例如：提供完整的姓名、修改时间范围、使用业务上的省份区域命名方式、记录的唯一标识等。",
        "en": "Sorry, no data was found. Please change your question or modify the query conditions and ask again, for example: provide full name, modify the time range, use the provincial area naming conventions in business, unique identifiers of records, etc."
    },
    "TOOL_SQL_READ_ONLY": {
        "zh": "对不起，您只允许进行数据库查询，不允许进行增、删、改等操作。",
        "en": "I'm sorry, you are only allowed to perform database queries; data manipulation operations such as insert, delete, or update are not permitted."
    },
    "TOOL_SQL_TIMEOUT": {
        "zh": "对不起，执行查询时超时，可能是数据库繁忙、数据量太大或者网络波动。",
        "en": "Sorry, the query execution timed out, which may be due to a busy database, too much data, or network fluctuations."
    },
    "TOOL_SQL_ERROR_RETRY": {
        "zh": "执行出错，请重新调用工具，异常信息：{error}",
        "en": "Execution error, please rerun this tool, error info: {error}"
    },
    "TOOL_SQL_ERROR": {
        "zh": "对不起，执行过程出现异常，您可以换个问题或者重新提问，异常信息：{error}",
        "en": "Sorry, an exception occurred during the execution. You may try a different question or rephrase your query. Error info: {error}"
    },
    "TOOL_SQL_NOT_CLEAR": {
        "zh": "对不起我无法回答您的问题，我只能回答以下数据库范围内的问题:``` {database_comments} ```",
        "en": "I'm sorry, I can't answer your question. I can only respond to questions within the scope of the following database: ``` {database_comments} ```"
    },
    "TOOL_SQL_DETAIL_PRODUCE": {
        "zh": "生成的SQL如下：\n```sql\n{sql}\n```\n数据库查询结果如下：\n```json\n{records}\n```\n总结：\n{summarize}\n",
        "en": "The generated SQL is as follows:\n```sql\n{sql}\n```\nrecords:\n```json\n{records}\n```\nsummarize:\n{summarize}\n"
    },
    "TOOL_SQL_PRODUCE": {
        "zh": "生成的SQL如下：\n```sql\n{sql}\n```\n",
        "en": "The generated SQL is as follows:\n```sql\n{sql}\n```\n"
    },
    "TOOL_SEARCH_RESULT": {
        "zh": "查询结果：{result}",
        "en": "Search result:{result}"
    },
    "TOOL_SHELL_REJECT": {
        "zh": "请停止执行shell命令：<{query}>",
        "en": "Stop! You couldn't execute this command <{query}>."
    },
    "TOOL_AES_CYPHER_MODE_ERROR": {
        "zh": "不支持该加密模式：{cypher_mode}, 你只能从下面的列表中选择['encrypt', 'decrypt']",
        "en": "cypher_mode {cypher_mode} not supported, optional ['encrypt', 'decrypt']"
    },

    "WORKER_MAX_TOKENS_INPUT": {
        "zh": "当前限制输入不能超过{MAX_TOKENS_INPUT}个字符，您的输入长度为{token_num}(包含提示词、输入文档和历史对话内容)",
        "en": "The current limit on input cannot exceed {MAX_TOKENS_INPUT} characters. Your input length is {token_num} (including prompt words, input documents, and historical conversation content)"
    },
    "WORKER_CHAT_ERROR": {
        "zh": "当前对话出现异常",
        "en": "There is an exception occur"
    },
    "WORKER_CHAT_CANCELLED": {
        "zh": "当前对话已中断",
        "en": "Chat cancelled"
    },

    "API_AGENT_TOOL_ERROR_INFO": {
        "zh": "\n```\n工具名称: {tool_name}\n工具状态: 调用失败\n错误信息: {error}\n\n```\n",
        "en": "\n```\nTool name: {tool_name}\nTool status: Call failed\nError message: {error}\n```\n"
    },
    "API_AGENT_TOOL_SUCCESS_INFO": {
        "zh": "\n```\n工具名称: {tool_name}\n工具状态: 调用成功\n工具输入: {input_str}\n工具输出: {output_str}\n```\n",
        "en": "\n```\nTool name: {tool_name}\nTool status: Call success\nTool input: {input_str}\nTool output: {output_str}\n```\n"
    },
    "API_CREATE_ERROR": {
        "zh": "创建失败",
        "en": "Create failed"
    },
    "API_UPDATE_ERROR": {
        "zh": "修改失败",
        "en": "Update failed"
    },
    "API_DELETE_ERROR": {
        "zh": "删除失败",
        "en": "Delete failed"
    },
    "API_TASK_NOT_EXIST": {
        "zh": "任务({task_id})不存在",
        "en": "task[{task_id}] is not exist"
    },
    "API_FEEDBACK_SUCCESS": {
        "zh": "反馈成功",
        "en": "Feedback success"
    },
    "API_FEEDBACK_ERROR": {
        "zh": "反馈失败",
        "en": "Feedback error"
    },
    "API_CHAT_TYPE_NOT_SUPPORT": {
        "zh": "对不起，{chat_type}不支持该模型:{model_name}",
        "en": "Sorry, {chat_type} does not support this model:{model_name}"
    },
    "API_PARAM_NOT_PRESENT": {
        "zh": "参数:{name}不能为空",
        "en": "Parameter: {name} cannot be empty"
    },
    "API_FILE_NOT_EXIST": {
        "zh": "请先上传文件",
        "en": "Please upload file"
    },
    "API_KB_NOT_EXIST": {
        "zh": "知识库<{kb_name}>不存在",
        "en": "Knowledgebase <{kb_name}> not exist"
    },
    "API_KB_EXIST": {
        "zh": "知识库<{kb_name}>已存在",
        "en": "Knowledgebase <{kb_name}> already exist"
    },
    "API_SEARCHENGINE_NOT_SUPPORT": {
        "zh": "未支持搜索引擎:{search_engine_name}",
        "en": "Search engine not supported:{search_engine_name}"
    },
    "API_DOC_NOT_FOUND": {
        "zh": "未找到相关文档,该回答为大模型自身能力解答！",
        "en": "No relevant documents found, this answer is for the ability of the large model itself!"
    },
    "API_ARTICLE_NAME": {
        "zh": "文章名称",
        "en": "Article name"
    },
    "API_REFERENCE_NAME": {
        "zh": "参考文档",
        "en": "Reference paper"
    },
    "API_TOOL_NOT_FOUND": {
        "zh": "对不起，没有工具可以调用。",
        "en": "Sorry, there are no tools available for calling."
    },
}


def get_message_i18n(key: str):
    if is_english():
        return message_i18n_map[key]["en"]
    return message_i18n_map[key]["zh"]


class Message_I18N(enum.Enum):
    COMMON_CALL_SUCCESS = get_message_i18n("COMMON_CALL_SUCCESS")
    COMMON_CALL_FAILED = get_message_i18n("COMMON_CALL_FAILED")
    COMMON_PARSE_FAILED = get_message_i18n("COMMON_PARSE_FAILED")

    TOOL_CALCULATE_ERROR = get_message_i18n("TOOL_CALCULATE_ERROR")
    TOOL_SEARCH_KNOWLEDGEBASE_EMPTY = get_message_i18n("TOOL_SEARCH_KNOWLEDGEBASE_EMPTY")
    TOOL_SQL_NO_RECORD = get_message_i18n("TOOL_SQL_NO_RECORD")
    TOOL_SQL_READ_ONLY = get_message_i18n("TOOL_SQL_READ_ONLY")
    TOOL_SQL_TIMEOUT = get_message_i18n("TOOL_SQL_TIMEOUT")
    TOOL_SQL_ERROR_RETRY = get_message_i18n("TOOL_SQL_ERROR_RETRY")
    TOOL_SQL_ERROR = get_message_i18n("TOOL_SQL_ERROR")
    TOOL_SQL_NOT_CLEAR = get_message_i18n("TOOL_SQL_NOT_CLEAR")
    TOOL_SQL_PRODUCE = get_message_i18n("TOOL_SQL_PRODUCE")
    TOOL_SQL_DETAIL_PRODUCE = get_message_i18n("TOOL_SQL_DETAIL_PRODUCE")
    TOOL_SHELL_REJECT = get_message_i18n("TOOL_SHELL_REJECT")
    TOOL_SEARCH_RESULT = get_message_i18n("TOOL_SEARCH_RESULT")
    TOOL_AES_CYPHER_MODE_ERROR = get_message_i18n("TOOL_AES_CYPHER_MODE_ERROR")

    WORKER_MAX_TOKENS_INPUT = get_message_i18n("WORKER_MAX_TOKENS_INPUT")
    WORKER_CHAT_ERROR = get_message_i18n("WORKER_CHAT_ERROR")
    WORKER_CHAT_CANCELLED = get_message_i18n("WORKER_CHAT_CANCELLED")

    API_AGENT_TOOL_ERROR_INFO = get_message_i18n("API_AGENT_TOOL_ERROR_INFO")
    API_AGENT_TOOL_SUCCESS_INFO = get_message_i18n("API_AGENT_TOOL_SUCCESS_INFO")
    API_CREATE_ERROR = get_message_i18n("API_CREATE_ERROR")
    API_UPDATE_ERROR = get_message_i18n("API_UPDATE_ERROR")
    API_DELETE_ERROR = get_message_i18n("API_DELETE_ERROR")
    API_TASK_NOT_EXIST = get_message_i18n("API_TASK_NOT_EXIST")
    API_FEEDBACK_SUCCESS = get_message_i18n("API_FEEDBACK_SUCCESS")
    API_FEEDBACK_ERROR = get_message_i18n("API_FEEDBACK_ERROR")
    API_CHAT_TYPE_NOT_SUPPORT = get_message_i18n("API_CHAT_TYPE_NOT_SUPPORT")
    API_PARAM_NOT_PRESENT = get_message_i18n("API_PARAM_NOT_PRESENT")
    API_FILE_NOT_EXIST = get_message_i18n("API_FILE_NOT_EXIST")
    API_KB_NOT_EXIST = get_message_i18n("API_KB_NOT_EXIST")
    API_KB_EXIST = get_message_i18n("API_KB_EXIST")
    API_SEARCHENGINE_NOT_SUPPORT = get_message_i18n("API_SEARCHENGINE_NOT_SUPPORT")
    API_DOC_NOT_FOUND = get_message_i18n("API_DOC_NOT_FOUND")
    API_ARTICLE_NAME = get_message_i18n("API_ARTICLE_NAME")
    API_REFERENCE_NAME = get_message_i18n("API_REFERENCE_NAME")
    API_TOOL_NOT_FOUND = get_message_i18n("API_TOOL_NOT_FOUND")
