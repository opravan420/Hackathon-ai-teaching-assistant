import logging
from typing import List, Dict, Any
from apps.ai_engine.rag.embedding_service import EmbeddingService
from apps.ai_engine.rag.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)

class RetrievalService:
    """Service for semantic document retrieval using BGE-M3 and FAISS."""

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStoreManager()

    def retrieve_relevant_context(
        self,
        query: str,
        teacher_id: int,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        query_str = query.strip() if query else ""
        if not query_str:
            return []

        query_embeddings = self.embedding_service.generate_embeddings([query_str])

        results = self.vector_store.search(
            teacher_id=teacher_id,
            query_vector=query_embeddings,
            top_k=top_k
        )

        results.sort(key=lambda x: x.get('similarity_score', 0.0), reverse=True)
        return results

    def rebuild_index_for_teacher(self, teacher_id: int) -> Dict[str, Any]:
        return self.vector_store.build_teacher_index(teacher_id)
