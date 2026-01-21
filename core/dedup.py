import logging
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer, util
from .config import BASE_DIR

logger = logging.getLogger(__name__)

class Deduplicator:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def compute_embedding(self, text: str):
        return self.model.encode(text, convert_to_tensor=True)

    def is_duplicate(self, new_text: str, history_texts: List[str], threshold: float = 0.92) -> bool:
        if not history_texts:
            return False

        new_emb = self.compute_embedding(new_text)
        history_embs = self.model.encode(history_texts, convert_to_tensor=True)
        
        cosine_scores = util.cos_sim(new_emb, history_embs)[0]
        max_score = float(np.max(cosine_scores.cpu().numpy()))
        
        logger.info(f"Dedup check: max_score={max_score:.4f} vs threshold={threshold}")
        
        return max_score > threshold

# Global instance
deduplicator = Deduplicator()
