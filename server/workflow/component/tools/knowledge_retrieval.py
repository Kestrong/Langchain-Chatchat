from typing import Dict, Any, Union

from configs import VECTOR_SEARCH_TOP_K, SCORE_THRESHOLD
from server.db.repository import list_kbs_from_db
from server.knowledge_base.kb_doc_api import search_docs
from server.workflow.component.base.component import Component
from server.workflow.utils.inputs import TextInput, ListInput, IntegerInput, FloatInput, BooleanInput
from server.workflow.utils.outputs import ListOutput


class KnowledgeRetrievalComponent(Component):
    display_name = "${WORKFLOW_DISPLAYNAME_KNOWLEDGERETRIEVAL}"
    description = "${WORKFLOW_DESCRIPTION_KNOWLEDGERETRIEVAL}"
    name = "knowledge_retrieval"
    tag = "${WORKFLOW_TAG_TOOL}"
    icon: Union[str, None]

    inputs = [
        TextInput(
            name='query',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_QUERY}",
            required=True,
            info="${WORKFLOW_INPUT_INFO_QUERY}",
        ),
        ListInput(
            name='knowledge_base_names',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_KNOWLEDGE_BASE_NAMES}",
            info="${WORKFLOW_INPUT_INFO_KNOWLEDGE_BASE_NAMES}",
            options=[k["kb_name"] for k in list_kbs_from_db(all_kbs=True)[0]]
        ),
        IntegerInput(
            name='top_k',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_TOP_K}",
            info="${WORKFLOW_INPUT_INFO_TOP_K}",
            value=VECTOR_SEARCH_TOP_K
        ),
        FloatInput(
            name='score_threshold',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_SCORE_THRESHOLD}",
            info="${WORKFLOW_INPUT_INFO_SCORE_THRESHOLD}",
            value=SCORE_THRESHOLD
        ),
        BooleanInput(
            name="only_content",
            display_name="Only Content",
            info="Only return page content or other info",
            value=False
        ),
    ]

    outputs = [
        ListOutput(
            name='document',
            display_name="${WORKFLOW_OUTPUT_DISPLAYNAME_DOCUMENT}",
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
                          "kb_name": k} if inputs.get("only_content") else doc.page_content for doc in docs])
        return {"document": document}
