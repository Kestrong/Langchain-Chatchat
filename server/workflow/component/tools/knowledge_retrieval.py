from typing import Dict, Any, Union

from configs import VECTOR_SEARCH_TOP_K, SCORE_THRESHOLD
from server.db.repository import list_kbs_from_db
from server.knowledge_base.kb_doc_api import search_docs
from server.workflow.component.base.component import Component
from server.workflow.utils.inputs import TextInput, ListInput, IntegerInput, FloatInput
from server.workflow.utils.outputs import ListOutput


class KnowledgeRetrievalComponent(Component):
    display_name = "Knowledge Retrieval"
    description = "retrieval knowledge form vectorstore using embedding model."
    name = "knowledge_retrieval"
    tag = "Tool"
    icon: Union[str, None]

    inputs = [
        TextInput(
            name='query',
            display_name='Text',
            required=True,
            info='input question to search vectorstore',
        ),
        ListInput(
            name='knowledge_base_names',
            display_name='KnowledgeBase Names',
            info='Available knowledgebase names to use for LLM.',
            options=[k["kb_name"] for k in list_kbs_from_db(all_kbs=True)[0]]
        ),
        IntegerInput(
            name='top_k',
            display_name='TopK',
            info='The maximum number of knowledge base doc to match.',
            value=VECTOR_SEARCH_TOP_K
        ),
        FloatInput(
            name='score_threshold',
            display_name='Score Threshold',
            info='For the knowledge base match relevance threshold, the value range is between 0 and 1, where a smaller SCORE indicates higher relevance, and a SCORE of 1 is equivalent to no filtering. It is recommended to set this threshold around 0.5.',
            value=SCORE_THRESHOLD
        ),
    ]

    outputs = [
        ListOutput(
            name='document',
            display_name='Document',
        )
    ]

    async def _run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        inputs = self.get_context()[self.id]["inputs"]
        query = inputs.get("query") or state.get("query")
        knowledge_base_names = inputs.get("knowledge_base_names")
        top_k = inputs.get("top_k") or VECTOR_SEARCH_TOP_K
        score_threshold = inputs.get("score_threshold") or SCORE_THRESHOLD
        document = []
        if knowledge_base_names:
            for k in knowledge_base_names:
                docs = search_docs(
                    query=query,
                    knowledge_base_name=k,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    file_name="",
                    metadata={},
                )
                if docs:
                    document.extend(
                        [{"id": doc.id, "page_content": doc.page_content, "score": doc.score,
                          "source": doc.metadata.get("source"),
                          "kb_name": k} for doc in docs])
        return {"document": document}
