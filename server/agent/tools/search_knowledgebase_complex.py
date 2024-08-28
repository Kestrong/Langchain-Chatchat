from __future__ import annotations

from pydantic import Field, BaseModel

from configs import VECTOR_SEARCH_TOP_K, SCORE_THRESHOLD
from server.agent.tools_select import register_tool
from server.db.repository import list_kbs_from_db
from server.knowledge_base.kb_doc_api import search_docs
from server.knowledge_base.model.kb_document_model import DocumentWithVSId


def search_knowledgebase(query: str, knowledgebase: str):
    docs = search_docs(
        query=query,
        knowledge_base_name=knowledgebase,
        top_k=VECTOR_SEARCH_TOP_K,
        score_threshold=SCORE_THRESHOLD,
        file_name="",
        metadata={},
    )
    return {"knowledge_base": knowledgebase, "docs": docs}


class KnowledgeSearchInput(BaseModel):
    query: str = Field(description="The query to be searched")
    knowledgebase: str = Field(
        description="Knowledgebase for knowledge search"
    )


template = (
    "Use local knowledgebase from one or more of these:\n{KB_info}\n to get information, Only local data on "
    "this knowledge use this tool. The 'knowledgebase' param must be one of the above key."
).format(KB_info="\n".join([kb["kb_name"] + ":" + kb["kb_info"] for kb in list_kbs_from_db(all_kbs=True)[0]]))


@register_tool(title='知识库搜索',
               description=template,
               args_schema=KnowledgeSearchInput, )
def search_knowledgebase_complex(query: str, knowledgebase: str):
    ret = search_knowledgebase(query=query, knowledgebase=knowledgebase)
    context = ""
    docs = ret["docs"]

    if len(docs) == 0:
        context = "没有找到相关文档,请更换关键词或者知识库重试"
    else:
        for inum, doc in enumerate(docs):
            doc = DocumentWithVSId.parse_obj(doc)
            context += doc.page_content + "\n\n"

    return context
