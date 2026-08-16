import numpy as np
import logging
from typing import List, Optional
from django.conf import settings
from sentence_transformers import SentenceTransformer
import faiss

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating normalized BGE-M3 embeddings dynamically."""
    _instance: Optional['EmbeddingService'] = None
    _model: Optional[SentenceTransformer] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_model(self) -> SentenceTransformer:
        if EmbeddingService._model is None:
            model_name = getattr(settings, 'EMBEDDING_MODEL_NAME', 'BAAI/bge-m3')
            device = getattr(settings, 'EMBEDDING_DEVICE', 'cpu')
            logger.info(f"Loading embedding model '{model_name}' on device '{device}'...")
            EmbeddingService._model = SentenceTransformer(model_name, device=device)
            logger.info(f"Embedding model '{model_name}' successfully loaded.")
        return EmbeddingService._model

    def get_embedding_dimension(self) -> int:
        model = self._get_model()
        if hasattr(model, 'get_embedding_dimension'):
            return model.get_embedding_dimension()
        return model.get_sentence_embedding_dimension()

    def generate_embeddings(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        if not texts:
            dim = self.get_embedding_dimension()
            return np.empty((0, dim), dtype=np.float32)

        model = self._get_model()
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=False
        ).astype(np.float32)

        # L2 normalization for cosine similarity with IndexFlatIP
        faiss.normalize_L2(embeddings)
        return embeddings
