from __future__ import annotations

from backend.config import get_settings


class Embedder:
    """Lazy sentence-transformers embedder for BGE-small-zh-v1.5."""

    def __init__(self, model_name: str | None = None, batch_size: int = 32) -> None:
        self.model_name = model_name or get_settings().EMBEDDING_MODEL
        self.batch_size = batch_size
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder
