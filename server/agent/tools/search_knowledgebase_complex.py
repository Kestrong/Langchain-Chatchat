from typing import List

from pydantic import Field, BaseModel

from configs import VECTOR_SEARCH_TOP_K, SCORE_THRESHOLD
from server.agent.tools_select import register_tool
from server.knowledge_base.kb_doc_api import search_docs
from server.memory.message_i18n import Message_I18N


def search_knowledgebase(query: str, knowledgebase: List[str]):
    result = {}
    for kb in knowledgebase:
        docs = search_docs(
            query=query,
            knowledge_base_name=kb,
            top_k=VECTOR_SEARCH_TOP_K,
            score_threshold=SCORE_THRESHOLD,
            file_name="",
            metadata={},
        )
        result[kb] = docs
    return result


class KnowledgeSearchInput(BaseModel):
    query: str = Field(description="The query to be searched")


@register_tool(title='知识库搜索',
               description='Use this tool to search knowledgebase.',
               args_schema=KnowledgeSearchInput, )
def search_knowledgebase_complex(tool_config: dict, query: str):
    knowledgebase = tool_config.get("knowledgebase", [])
    ret = search_knowledgebase(query=query, knowledgebase=knowledgebase)
    context = ""

    if not ret:
        context = Message_I18N.TOOL_SEARCH_KNOWLEDGEBASE_EMPTY.value
    else:
        for kb, docs in ret.items():
            context += f"knowledgebase name: {kb}\n\n"
            for doc in docs:
                filename = doc.metadata.get("source")
                context += f"""{filename}\n\n{doc.page_content}\n\n"""

    return context
