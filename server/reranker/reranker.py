import os
import sys

import requests

from common.exceptions import ChatBusinessException
from server.utils import get_model_worker_config

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from typing import Any, List
from typing import Optional, Sequence
from langchain_core.documents import Document
from langchain.callbacks.manager import Callbacks
from llama_index.bridge.pydantic import PrivateAttr
from configs import RERANKER_MODEL, logger, USE_RERANKER, VECTOR_SEARCH_TOP_K


class LangchainReranker:
    """Document compressor that uses `Cohere Rerank API`."""
    model: Any = PrivateAttr()

    def __init__(self,
                 model: str = RERANKER_MODEL
                 ):
        self.model = model

    def _do_rerank(self,
                   documents: List[str],
                   query: str,
                   top_n: int = VECTOR_SEARCH_TOP_K,
                   return_documents: bool = False, ) -> List[dict]:
        if not documents:
            return []
        if USE_RERANKER != "True":
            if USE_RERANKER is not True:
                raise ChatBusinessException("Reranker is not enabled")
        if not self.model:
            raise ChatBusinessException("Reranker model is not given")
        if not top_n or top_n <= 0 or top_n > len(documents):
            top_n = len(documents)
        config = get_model_worker_config(self.model)
        api_proxy = config.get("api_proxy") + "/rerank"
        api_key = config.get("api_key")
        reranker_model = config.get("reranker_model")
        extra_headers = config.get("role_meta", {}).get("extra_headers", {})
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", **extra_headers}
        data = {
            "query": query,
            "documents": documents,
            "return_documents": return_documents if return_documents is not None else False,
            "top_n": top_n,
            "model": reranker_model
        }
        with requests.post(api_proxy, headers=headers, json=data) as response:
            if not response.ok:
                logger.error(response.text)
                response.raise_for_status()
            results = response.json().get("results", [])
            return results

    def rerank(self,
               documents: List[str],
               query: str,
               top_n: int = VECTOR_SEARCH_TOP_K,
               return_documents: bool = False,
               ) -> List[Document]:
        results = self._do_rerank(documents, query, top_n, return_documents)
        final_result = []
        for r in results:
            doc = Document(page_content=documents[r["index"]] if return_documents else "",
                           metadata={"index": r["index"], "relevance_score": r["relevance_score"]})
            final_result.append(doc)
        return final_result

    def compress_documents(
            self,
            documents: Sequence[Document],
            query: str,
            top_n: int = VECTOR_SEARCH_TOP_K,
            callbacks: Optional[Callbacks] = None,
    ) -> Sequence[Document]:
        try:
            doc_list = list(documents)
            _docs = [d.page_content for d in doc_list]
            results = self._do_rerank(_docs, query, top_n, return_documents=False)
            final_result = []
            for r in results:
                doc = doc_list[r["index"]]
                doc.metadata["relevance_score"] = r["relevance_score"]
                final_result.append(doc)
            return final_result[:top_n]
        except Exception as e:
            logger.error(e)
            return documents[:top_n]


if __name__ == "__main__":
    reranker = LangchainReranker(model=RERANKER_MODEL)
    result = reranker.compress_documents(
        documents=[Document(page_content="hello world"), Document(page_content="I'm fine."),
                   Document(page_content="Nice to meet you."), Document(page_content="Hi")],
        query="hello",
        top_n=VECTOR_SEARCH_TOP_K, )
    print(result)

    result = reranker.rerank(documents=["hello world", "I'm fine.", "Nice to meet you.", "Hi"], query="hello",
                             top_n=VECTOR_SEARCH_TOP_K, return_documents=False)
    print(result)
