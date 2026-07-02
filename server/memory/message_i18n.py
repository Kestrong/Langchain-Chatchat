from server.memory.token_info_memory import is_english

common = {
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
}

tool = {
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
        "zh": "生成的SQL如下：\n```sql\n{sql}\n```\n数据库查询结果如下：\n```json\n{records}\n```\n\n{summarize}\n",
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
}

worker = {
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
}

api = {
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
    "API_COMPONENT_NOT_FOUND": {
        "zh": "对不起，工作流组件{component_type}不存在。",
        "en": "Sorry, there is no component available of {component_type}."
    },
}

workflow = {
    # 标签
    "WORKFLOW_TAG_CONDITION": {
        "zh": "条件",
        "en": "Condition"
    },
    "WORKFLOW_TAG_INPUT": {
        "zh": "输入",
        "en": "Input"
    },
    "WORKFLOW_TAG_MODEL": {
        "zh": "模型",
        "en": "Model"
    },
    "WORKFLOW_TAG_OUTPUT": {
        "zh": "输出",
        "en": "Output"
    },
    "WORKFLOW_TAG_TOOL": {
        "zh": "工具",
        "en": "Tool"
    },
    # 组件名称
    "WORKFLOW_DISPLAYNAME_IFELSE": {
        "zh": "条件判断",
        "en": "If-Else"
    },
    "WORKFLOW_DISPLAYNAME_CHATINPUT": {
        "zh": "聊天输入",
        "en": "Chat Input"
    },
    "WORKFLOW_DISPLAYNAME_LOCALLLM": {
        "zh": "本地LLM",
        "en": "Local LLM"
    },
    "WORKFLOW_DISPLAYNAME_CHATOUTPUT": {
        "zh": "输出",
        "en": "Chat Output"
    },
    "WORKFLOW_DISPLAYNAME_PYTHONREPL": {
        "zh": "Python执行",
        "en": "Python REPL"
    },
    "WORKFLOW_DISPLAYNAME_DOCUMENTEXTRACTOR": {
        "zh": "文档提取器",
        "en": "Document Extractor"
    },
    "WORKFLOW_DISPLAYNAME_HTTPCALLER": {
        "zh": "HTTP请求",
        "en": "Http Caller"
    },
    "WORKFLOW_DISPLAYNAME_JSONFORMATTER": {
        "zh": "JSON格式化",
        "en": "Json Formatter"
    },
    "WORKFLOW_DISPLAYNAME_KNOWLEDGERETRIEVAL": {
        "zh": "知识检索",
        "en": "Knowledge Retrieval"
    },
    # 组件描述
    "WORKFLOW_DESCRIPTION_IFELSE": {
        "zh": "根据条件输入路由到不同的分支",
        "en": "Routes an input to a corresponding output."
    },
    "WORKFLOW_DESCRIPTION_CHATINPUT": {
        "zh": "获取聊天输入",
        "en": "Get chat inputs from the Playground."
    },
    "WORKFLOW_DESCRIPTION_LOCALLLM": {
        "zh": "使用本地LLM生成文本",
        "en": "Generate text using Local LLMs."
    },
    "WORKFLOW_DESCRIPTION_CHATOUTPUT": {
        "zh": "获取输出内容",
        "en": "Get chat outputs from the Playground."
    },
    "WORKFLOW_DESCRIPTION_PYTHONREPL": {
        "zh": "执行Python代码",
        "en": "execute python code."
    },
    "WORKFLOW_DESCRIPTION_DOCUMENTEXTRACTOR": {
        "zh": "从文档中提取内容",
        "en": "extract content form document."
    },
    "WORKFLOW_DESCRIPTION_HTTPCALLER": {
        "zh": "向服务器发送HTTP请求",
        "en": "send a http request to the server."
    },
    "WORKFLOW_DESCRIPTION_JSONFORMATTER": {
        "zh": "将字符串转换为JSON对象",
        "en": "convert string to json object."
    },
    "WORKFLOW_DESCRIPTION_KNOWLEDGERETRIEVAL": {
        "zh": "使用嵌入模型从向量存储中检索知识",
        "en": "retrieval knowledge form vectorstore using embedding model."
    },
    # 输入
    "WORKFLOW_INPUT_DISPLAYNAME_QUERY": {
        "zh": "查询内容",
        "en": "Query"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_HISTORY_LEN": {
        "zh": "历史对话轮次",
        "en": "History Length"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_CONVERSATION_ID": {
        "zh": "会话ID",
        "en": "Conversation ID"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_KNOWLEDGE_ID": {
        "zh": "知识ID",
        "en": "Knowledge ID"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_STORE_MESSAGE": {
        "zh": "是否存储对话",
        "en": "Store Message"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_EXTRA": {
        "zh": "额外信息",
        "en": "Extra"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_ASSISTANT_CODE": {
        "zh": "助手编码",
        "en": "Assistant Code"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_PROMPT": {
        "zh": "提示词",
        "en": "Prompt"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_MODEL_NAME": {
        "zh": "模型名称",
        "en": "Model Name"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_MAX_TOKENS": {
        "zh": "最大标记数",
        "en": "Max Tokens"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_TOP_K": {
        "zh": "Top K",
        "en": "Top K"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_SCORE_THRESHOLD": {
        "zh": "相似度阈值",
        "en": "Score Threshold"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_TEMPERATURE": {
        "zh": "温度",
        "en": "Temperature"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_KNOWLEDGE_BASE_NAMES": {
        "zh": "知识库名称",
        "en": "Knowledge Base Names"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_TOOL_NAMES": {
        "zh": "工具名称",
        "en": "Tool Names"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_API_NAMES": {
        "zh": "API名称",
        "en": "API Names"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_ARGS": {
        "zh": "参数",
        "en": "Args"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_PYTHON_CODE": {
        "zh": "Python代码",
        "en": "Python Code"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_URL": {
        "zh": "URL地址",
        "en": "URL"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_METHOD": {
        "zh": "方法",
        "en": "Method"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_TIMEOUT": {
        "zh": "超时时间",
        "en": "Timeout"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_COOKIES": {
        "zh": "Cookies",
        "en": "Cookies"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_HEADERS": {
        "zh": "请求头",
        "en": "Headers"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_BODY": {
        "zh": "请求体",
        "en": "Body"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_PARAMS": {
        "zh": "参数",
        "en": "Params"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_JSON_STR": {
        "zh": "JSON字符串",
        "en": "JSON String"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_CONDITIONS": {
        "zh": "条件",
        "en": "Conditions"
    },
    "WORKFLOW_INPUT_DISPLAYNAME_RELATION": {
        "zh": "逻辑关系",
        "en": "Relation"
    },
    "WORKFLOW_INPUT_INFO_QUERY": {
        "zh": "输入的问题内容",
        "en": "Message to be passed as input."
    },
    "WORKFLOW_INPUT_INFO_HISTORY_LEN": {
        "zh": "传递给LLM的历史消息的最大数量",
        "en": "The maximum number of history message to pass into llm."
    },
    "WORKFLOW_INPUT_INFO_CONVERSATION_ID": {
        "zh": "聊天的会话ID，如果为空将自动生成",
        "en": "The conversation id of the chat. If empty, will auto created."
    },
    "WORKFLOW_INPUT_INFO_KNOWLEDGE_ID": {
        "zh": "附件上传后返回的ID",
        "en": "The upload id of file"
    },
    "WORKFLOW_INPUT_INFO_STORE_MESSAGE": {
        "zh": "是否将对话存储到数据库中",
        "en": "Store the message in the history."
    },
    "WORKFLOW_INPUT_INFO_EXTRA": {
        "zh": "传递给聊天的额外输入",
        "en": "Extra inputs passed to the chat."
    },
    "WORKFLOW_INPUT_INFO_ASSISTANT_CODE": {
        "zh": "助手的唯一编码",
        "en": "The code of assistant."
    },
    "WORKFLOW_INPUT_INFO_PROMPT": {
        "zh": "聊天的提示词",
        "en": "Prompt for chat."
    },
    "WORKFLOW_INPUT_INFO_MODEL_NAME": {
        "zh": "LLM的模型名称",
        "en": "The name of LLM."
    },
    "WORKFLOW_INPUT_INFO_MAX_TOKENS": {
        "zh": "大模型要生成的最大标记数，如果不设置或设为0则无限制",
        "en": "The maximum number of tokens to generate. Unlimited tokens if no set or set 0."
    },
    "WORKFLOW_INPUT_INFO_TOP_K": {
        "zh": "知识库文档匹配的最大数量",
        "en": "The maximum number of knowledge base doc to match."
    },
    "WORKFLOW_INPUT_INFO_SCORE_THRESHOLD": {
        "zh": "知识库匹配相关性阈值，值范围在0到1之间，较小的分数表示更高的相关性",
        "en": "For the knowledge base match relevance threshold, the value range is between 0 and 1, where a smaller SCORE indicates higher relevance, and a SCORE of 1 is equivalent to no filtering. It is recommended to set this threshold around 0.5."
    },
    "WORKFLOW_INPUT_INFO_TEMPERATURE": {
        "zh": "控制生成文本的随机性",
        "en": "Controls the randomness of the generated text."
    },
    "WORKFLOW_INPUT_INFO_KNOWLEDGE_BASE_NAMES": {
        "zh": "可用于LLM的知识库名称",
        "en": "Available knowledgebase names to use for LLM."
    },
    "WORKFLOW_INPUT_INFO_TOOL_NAMES": {
        "zh": "可用于LLM的工具名称",
        "en": "Available tool names to use for LLM."
    },
    "WORKFLOW_INPUT_INFO_API_NAMES": {
        "zh": "可用于LLM的API名称",
        "en": "Available api names to use for LLM."
    },
    "WORKFLOW_INPUT_INFO_ARGS": {
        "zh": "Python函数的参数",
        "en": "The args for python function."
    },
    "WORKFLOW_INPUT_INFO_PYTHON_CODE": {
        "zh": "要执行的Python代码",
        "en": "python code."
    },
    "WORKFLOW_INPUT_INFO_URL": {
        "zh": "服务器URL",
        "en": "server url."
    },
    "WORKFLOW_INPUT_INFO_METHOD": {
        "zh": "HTTP方法（GET, POST, PATCH, PUT, DELETE）",
        "en": "The HTTP method to use (GET, POST, PATCH, PUT, DELETE)."
    },
    "WORKFLOW_INPUT_INFO_TIMEOUT": {
        "zh": "请求超时时间",
        "en": "The timeout to use for the request."
    },
    "WORKFLOW_INPUT_INFO_COOKIES": {
        "zh": "要随请求发送的Cookies",
        "en": "The cookies to send with the request as a dictionary."
    },
    "WORKFLOW_INPUT_INFO_HEADERS": {
        "zh": "要随请求发送的请求头",
        "en": "The headers to send with the request as a dictionary."
    },
    "WORKFLOW_INPUT_INFO_BODY": {
        "zh": "要随请求发送的请求体（用于POST, PATCH, PUT）",
        "en": "The body to send with the request as a dictionary(for POST, PATCH, PUT)."
    },
    "WORKFLOW_INPUT_INFO_PARAMS": {
        "zh": "要附加到URL的查询参数",
        "en": "The query parameters to append to the URL."
    },
    "WORKFLOW_INPUT_INFO_JSON_STR": {
        "zh": "要转换为JSON对象的字符串",
        "en": "string to be convert into json object."
    },
    "WORKFLOW_INPUT_INFO_CONDITIONS": {
        "zh": "条件输入用于匹配",
        "en": "Condition inputs for match."
    },
    "WORKFLOW_INPUT_INFO_RELATION": {
        "zh": "条件之间的关系（AND或OR）",
        "en": "`AND` or `OR` between conditions."
    },
    # 输出
    "WORKFLOW_OUTPUT_DISPLAYNAME_ANSWER": {
        "zh": "答案",
        "en": "Answer"
    },
    "WORKFLOW_OUTPUT_DISPLAYNAME_DOCS": {
        "zh": "文档",
        "en": "Docs"
    },
    "WORKFLOW_OUTPUT_DISPLAYNAME_THOUGHT": {
        "zh": "思考过程",
        "en": "Thought"
    },
    "WORKFLOW_OUTPUT_DISPLAYNAME_TOTAL_TOKENS": {
        "zh": "总token数量",
        "en": "Total tokens"
    },
    "WORKFLOW_OUTPUT_DISPLAYNAME_RESULT": {
        "zh": "结果",
        "en": "Result"
    },
    "WORKFLOW_OUTPUT_DISPLAYNAME_DATA": {
        "zh": "数据",
        "en": "Data"
    },
    "WORKFLOW_OUTPUT_DISPLAYNAME_CONDITION_RESULT": {
        "zh": "条件结果",
        "en": "Condition Result"
    },
    "WORKFLOW_OUTPUT_DISPLAYNAME_DOCUMENT": {
        "zh": "文档", "en": "Document"
    },
    "WORKFLOW_OUTPUT_INFO_ANSWER": {
        "zh": "生成的回答",
        "en": "Generated answer"
    },
    "WORKFLOW_OUTPUT_INFO_DOCS": {
        "zh": "检索到的文档",
        "en": "Retrieved documents"
    },
    "WORKFLOW_OUTPUT_INFO_THOUGHT": {
        "zh": "生成回答的思考过程",
        "en": "The thought process behind generating the answer"
    },
    "WORKFLOW_OUTPUT_INFO_RESULT": {
        "zh": "操作的结果",
        "en": "Result of the operation"
    },
    "WORKFLOW_OUTPUT_INFO_DATA": {
        "zh": "返回的数据",
        "en": "Data returned from the operation"
    },
    "WORKFLOW_OUTPUT_INFO_CONDITION_RESULT": {
        "zh": "条件评估的结果",
        "en": "Result of the condition evaluation"
    },
}

message_i18n_map = {
    "COMMON": common, "TOOL": tool, "WORKER": worker, "API": api, "WORKFLOW": workflow
}


def get_message_i18n(key: str):
    group = key.split("_")[0]
    if is_english():
        return message_i18n_map[group][key]["en"]
    return message_i18n_map[group][key]["zh"]


class I18NField:
    def __init__(self, key):
        self.key = key

    @property
    def name(self):
        return self.key

    @property
    def value(self):
        return i18n_property(self.key, prefix="", suffix="")


def i18n_property(key: str, prefix: str = "${", suffix: str = "}"):
    if not key:
        return key
    k = key
    if prefix:
        if k.startswith(prefix):
            k = k[len(prefix):]
        else:
            return key
    if suffix:
        if k.endswith(suffix):
            k = k[:-len(suffix)]
        else:
            return key
    return get_message_i18n(k)


class Message_I18N:
    COMMON_CALL_SUCCESS = I18NField("COMMON_CALL_SUCCESS")
    COMMON_CALL_FAILED = I18NField("COMMON_CALL_FAILED")
    COMMON_PARSE_FAILED = I18NField("COMMON_PARSE_FAILED")

    TOOL_CALCULATE_ERROR = I18NField("TOOL_CALCULATE_ERROR")
    TOOL_SEARCH_KNOWLEDGEBASE_EMPTY = I18NField("TOOL_SEARCH_KNOWLEDGEBASE_EMPTY")
    TOOL_SQL_NO_RECORD = I18NField("TOOL_SQL_NO_RECORD")
    TOOL_SQL_READ_ONLY = I18NField("TOOL_SQL_READ_ONLY")
    TOOL_SQL_TIMEOUT = I18NField("TOOL_SQL_TIMEOUT")
    TOOL_SQL_ERROR_RETRY = I18NField("TOOL_SQL_ERROR_RETRY")
    TOOL_SQL_ERROR = I18NField("TOOL_SQL_ERROR")
    TOOL_SQL_NOT_CLEAR = I18NField("TOOL_SQL_NOT_CLEAR")
    TOOL_SQL_PRODUCE = I18NField("TOOL_SQL_PRODUCE")
    TOOL_SQL_DETAIL_PRODUCE = I18NField("TOOL_SQL_DETAIL_PRODUCE")
    TOOL_SHELL_REJECT = I18NField("TOOL_SHELL_REJECT")
    TOOL_SEARCH_RESULT = I18NField("TOOL_SEARCH_RESULT")
    TOOL_AES_CYPHER_MODE_ERROR = I18NField("TOOL_AES_CYPHER_MODE_ERROR")

    WORKER_MAX_TOKENS_INPUT = I18NField("WORKER_MAX_TOKENS_INPUT")
    WORKER_CHAT_ERROR = I18NField("WORKER_CHAT_ERROR")
    WORKER_CHAT_CANCELLED = I18NField("WORKER_CHAT_CANCELLED")

    API_AGENT_TOOL_ERROR_INFO = I18NField("API_AGENT_TOOL_ERROR_INFO")
    API_AGENT_TOOL_SUCCESS_INFO = I18NField("API_AGENT_TOOL_SUCCESS_INFO")
    API_CREATE_ERROR = I18NField("API_CREATE_ERROR")
    API_UPDATE_ERROR = I18NField("API_UPDATE_ERROR")
    API_DELETE_ERROR = I18NField("API_DELETE_ERROR")
    API_TASK_NOT_EXIST = I18NField("API_TASK_NOT_EXIST")
    API_FEEDBACK_SUCCESS = I18NField("API_FEEDBACK_SUCCESS")
    API_FEEDBACK_ERROR = I18NField("API_FEEDBACK_ERROR")
    API_CHAT_TYPE_NOT_SUPPORT = I18NField("API_CHAT_TYPE_NOT_SUPPORT")
    API_PARAM_NOT_PRESENT = I18NField("API_PARAM_NOT_PRESENT")
    API_FILE_NOT_EXIST = I18NField("API_FILE_NOT_EXIST")
    API_KB_NOT_EXIST = I18NField("API_KB_NOT_EXIST")
    API_KB_EXIST = I18NField("API_KB_EXIST")
    API_SEARCHENGINE_NOT_SUPPORT = I18NField("API_SEARCHENGINE_NOT_SUPPORT")
    API_DOC_NOT_FOUND = I18NField("API_DOC_NOT_FOUND")
    API_ARTICLE_NAME = I18NField("API_ARTICLE_NAME")
    API_REFERENCE_NAME = I18NField("API_REFERENCE_NAME")
    API_TOOL_NOT_FOUND = I18NField("API_TOOL_NOT_FOUND")
    API_COMPONENT_NOT_FOUND = I18NField("API_COMPONENT_NOT_FOUND")
