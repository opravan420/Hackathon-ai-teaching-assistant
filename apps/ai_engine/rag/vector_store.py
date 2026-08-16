import os
import json
import logging
import faiss
import numpy as np
from typing import List, Dict, Any
from django.conf import settings
from apps.ai_engine.models import Document
from apps.ai_engine.rag.chunking_service import ChunkingService
from apps.ai_engine.rag.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

class VectorStoreManager:
    """Manages isolated teacher FAISS vector indexes and metadata persistence."""

    def get_teacher_store_dir(self, teacher_id) -> str:
        base_dir = getattr(settings, 'MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'media'))
        store_dir = os.path.join(base_dir, 'vector_store', f'teacher_{str(teacher_id)}')
        os.makedirs(store_dir, exist_ok=True)
        return store_dir

    def get_index_path(self, teacher_id) -> str:
        return os.path.join(self.get_teacher_store_dir(teacher_id), 'index.faiss')

    def get_metadata_path(self, teacher_id) -> str:
        return os.path.join(self.get_teacher_store_dir(teacher_id), 'metadata.json')

    def has_index(self, teacher_id) -> bool:
        """Returns True if valid FAISS index and metadata files exist for teacher."""
        index_path = self.get_index_path(teacher_id)
        metadata_path = self.get_metadata_path(teacher_id)
        return os.path.exists(index_path) and os.path.exists(metadata_path)

    def build_teacher_index(self, teacher_id) -> Dict[str, Any]:
        """Rebuilds the FAISS index and metadata for all successful documents of a given teacher."""
        docs = Document.objects.filter(
            teacher_id=teacher_id,
            extraction_status=Document.SUCCESS
        )

        if not docs.exists():
            self._delete_teacher_files(teacher_id)
            return {'status': 'EMPTY', 'chunk_count': 0, 'document_count': 0}

        docs.update(indexing_status=Document.PROCESSING)

        chunker = ChunkingService()
        all_chunks = []

        try:
            for doc in docs:
                chunks = chunker.chunk_document(doc)
                all_chunks.extend(chunks)

            if not all_chunks:
                docs.update(indexing_status=Document.UNINDEXED)
                self._delete_teacher_files(teacher_id)
                return {'status': 'EMPTY', 'chunk_count': 0, 'document_count': docs.count()}

            # Ensure all metadata values are JSON serializable
            for chunk in all_chunks:
                chunk['teacher_id'] = str(chunk['teacher_id'])

            embedding_service = EmbeddingService()
            texts = [c['chunk_text'] for c in all_chunks]
            embeddings = embedding_service.generate_embeddings(texts)

            dimension = embedding_service.get_embedding_dimension()
            index = faiss.IndexFlatIP(dimension)
            index.add(embeddings)

            # Save FAISS index
            index_path = self.get_index_path(teacher_id)
            faiss.write_index(index, index_path)

            # Save Metadata mapping
            metadata_path = self.get_metadata_path(teacher_id)
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(all_chunks, f, ensure_ascii=False, indent=2)

            docs.update(indexing_status=Document.INDEXED)
            logger.info(f"Successfully built vector store for teacher {teacher_id}: {len(all_chunks)} chunks across {docs.count()} documents.")
            return {
                'status': 'SUCCESS',
                'chunk_count': len(all_chunks),
                'document_count': docs.count()
            }
        except Exception as e:
            docs.update(indexing_status=Document.INDEX_FAILED)
            logger.error(f"Failed to build vector index for teacher {teacher_id}: {str(e)}", exc_info=True)
            raise

    def search(self, teacher_id: int, query_vector: np.ndarray, top_k: int = 3) -> List[Dict[str, Any]]:
        index_path = self.get_index_path(teacher_id)
        metadata_path = self.get_metadata_path(teacher_id)

        if not os.path.exists(index_path) or not os.path.exists(metadata_path):
            return []

        try:
            index = faiss.read_index(index_path)
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            if index.ntotal == 0 or not metadata:
                return []

            k = min(top_k, index.ntotal)
            distances, indices = index.search(query_vector, k)

            results = []
            for sim_score, idx in zip(distances[0], indices[0]):
                if idx < 0 or idx >= len(metadata):
                    continue
                item = dict(metadata[idx])
                item['similarity_score'] = float(sim_score)
                results.append(item)

            return results
        except Exception as e:
            logger.error(f"Error during vector search for teacher {teacher_id}: {str(e)}", exc_info=True)
            return []

    def _delete_teacher_files(self, teacher_id: int):
        index_path = self.get_index_path(teacher_id)
        metadata_path = self.get_metadata_path(teacher_id)
        if os.path.exists(index_path):
            try:
                os.remove(index_path)
            except Exception:
                pass
        if os.path.exists(metadata_path):
            try:
                os.remove(metadata_path)
            except Exception:
                pass
