import enum

from server.memory.token_info_memory import is_english

message_i18n_map = {
    "zh": {
        "COMMON_CALL_SUCCESS": "调用成功",
        "COMMON_CALL_FAILED": "调用失败",
        "COMMON_PARSE_FAILED": "解析失败",

        "TOOL_CALCULATE_ERROR": "```{query}```表达式无法被numexpr解析执行",
        "TOOL_SEARCH_KNOWLEDGEBASE_EMPTY": "没有找到相关文档,请更换关键词或者知识库重试",
        "TOOL_SQL_ERROR": "生成SQL失败，可能是数据库无法访问或者您描述的内容大模型无法理解。",
        "TOOL_SQL_PRODUCE": "生成的SQL如下：{result}",
        "TOOL_SEARCH_RESULT": "查询结果：{result}",
        "TOOL_SHELL_REJECT": "请停止执行shell命令：<{query}>",
        "TOOL_AES_CYPHER_MODE_ERROR": "不支持该加密模式：{cypher_mode}, 你只能从下面的列表中选择['encrypt', 'decrypt']",

        "WORKER_MAX_TOKENS_INPUT": "当前限制输入不能超过{MAX_TOKENS_INPUT}个字符，您的输入长度为{token_num}(包含提示词、输入文档和历史对话内容)",
        "WORKER_CHAT_ERROR": "当前对话出现异常",

        "API_AGENT_TOOL_ERROR_INFO": "\n```\n工具名称: {tool_name}\n工具状态: 调用失败\n错误信息: {error}\n\n```\n",
        "API_AGENT_TOOL_SUCCESS_INFO": "\n```\n工具名称: {tool_name}\n工具状态: 调用成功\n工具输入: {input_str}\n工具输出: {output_str}\n```\n",
        "API_CREATE_ERROR": "创建失败",
        "API_UPDATE_ERROR": "修改失败",
        "API_DELETE_ERROR": "删除失败",
        "API_TASK_NOT_EXIST": "任务({task_id})不存在",
        "API_FEEDBACK_SUCCESS": "反馈成功",
        "API_FEEDBACK_ERROR": "反馈失败",
        "API_CHAT_TYPE_NOT_SUPPORT": "对不起，{chat_type}不支持该模型:{model_name}",
        "API_PARAM_NOT_PRESENT": "参数:{name}不能为空",
        "API_FILE_NOT_EXIST": "请先上传文件",
        "API_KB_NOT_EXIST": "知识库<{kb_name}>不存在",
        "API_KB_EXIST": "知识库<{kb_name}>已存在",
        "API_SEARCHENGINE_NOT_SUPPORT": "未支持搜索引擎:{search_engine_name}",
        "API_DOC_NOT_FOUND": "未找到相关文档,该回答为大模型自身能力解答！",
        "API_ARTICLE_NAME": "文章名称",
        "API_TOOL_NOT_FOUND": "对不起，没有工具可以调用。",
    },
    "en": {
        "COMMON_CALL_SUCCESS": "SUCCESS",
        "COMMON_CALL_FAILED": "ERROR",
        "COMMON_PARSE_FAILED": "parse error",

        "TOOL_CALCULATE_ERROR": "The expression ```{query}``` cannot be parsed and executed by numuxpr",
        "TOOL_SEARCH_KNOWLEDGEBASE_EMPTY": "No relevant documents found, please change keywords or knowledge base and try again",
        "TOOL_SQL_ERROR": "Failed to generate SQL, possibly due to database unavailability or inability of the large model to understand the content you described.",
        "TOOL_SQL_PRODUCE": "The generated SQL is as follows:{result}",
        "TOOL_SEARCH_RESULT": "Search result:{result}",
        "TOOL_SHELL_REJECT": "Stop! You couldn't execute this command <{query}>.",
        "TOOL_AES_CYPHER_MODE_ERROR": "cypher_mode {cypher_mode} not supported, optional ['encrypt', 'decrypt']",

        "WORKER_MAX_TOKENS_INPUT": "The current limit on input cannot exceed {MAX_TOKENS_INPUT} characters. Your input length is {token_num} (including prompt words, input documents, and historical conversation content)",
        "WORKER_CHAT_ERROR": "There is an exception occur",

        "API_AGENT_TOOL_SUCCESS_INFO": "\n```\nTool name: {tool_name}\nTool status: Call failed\nError message: {error}\n```\n",
        "API_AGENT_TOOL_ERROR_INFO": "\n```\nTool name: {tool_name}\nTool status: Call success\nTool input: {input_str}\nTool output: {output_str}\n```\n",
        "API_CREATE_ERROR": "Create failed",
        "API_UPDATE_ERROR": "Update failed",
        "API_DELETE_ERROR": "Delete failed",
        "API_TASK_NOT_EXIST": "task[{task_id}] is not exist",
        "API_FEEDBACK_SUCCESS": "Feedback success",
        "API_FEEDBACK_ERROR": "Feedback error",
        "API_CHAT_TYPE_NOT_SUPPORT": "Sorry, {chat_type} does not support this model:{model_name}",
        "API_PARAM_NOT_PRESENT": "Parameter: {name} cannot be empty",
        "API_FILE_NOT_EXIST": "Please upload file",
        "API_KB_NOT_EXIST": "Knowledgebase <{kb_name}> not exist",
        "API_KB_EXIST": "Knowledgebase <{kb_name}> already exist",
        "API_SEARCHENGINE_NOT_SUPPORT": "Search engine not supported:{search_engine_name}",
        "API_DOC_NOT_FOUND": "No relevant documents found, this answer is for the ability of the large model itself!",
        "API_ARTICLE_NAME": "Article name",
        "API_TOOL_NOT_FOUND": "Sorry, there are no tools available for calling.",
    }
}


def get_message_i18n(key: str):
    if is_english():
        return message_i18n_map["en"][key]
    return message_i18n_map["zh"][key]


class Message_I18N(enum.Enum):
    COMMON_CALL_SUCCESS = get_message_i18n("COMMON_CALL_SUCCESS")
    COMMON_CALL_FAILED = get_message_i18n("COMMON_CALL_FAILED")
    COMMON_PARSE_FAILED = get_message_i18n("COMMON_PARSE_FAILED")

    TOOL_CALCULATE_ERROR = get_message_i18n("TOOL_CALCULATE_ERROR")
    TOOL_SEARCH_KNOWLEDGEBASE_EMPTY = get_message_i18n("TOOL_SEARCH_KNOWLEDGEBASE_EMPTY")
    TOOL_SQL_ERROR = get_message_i18n("TOOL_SQL_ERROR")
    TOOL_SQL_PRODUCE = get_message_i18n("TOOL_SQL_PRODUCE")
    TOOL_SHELL_REJECT = get_message_i18n("TOOL_SHELL_REJECT")
    TOOL_SEARCH_RESULT = get_message_i18n("TOOL_SEARCH_RESULT")
    TOOL_AES_CYPHER_MODE_ERROR = get_message_i18n("TOOL_AES_CYPHER_MODE_ERROR")

    WORKER_MAX_TOKENS_INPUT = get_message_i18n("WORKER_MAX_TOKENS_INPUT")
    WORKER_CHAT_ERROR = get_message_i18n("WORKER_CHAT_ERROR")

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
    API_TOOL_NOT_FOUND = get_message_i18n("API_TOOL_NOT_FOUND")
