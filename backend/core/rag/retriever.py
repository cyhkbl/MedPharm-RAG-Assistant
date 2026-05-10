from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from backend.core.rag.embedder import get_embedder
from backend.core.rag.vectorstore import ChromaVectorStore
from backend.models.database import get_data_paths


class HybridRetriever:
    """Vector + BM25 retrieval with Reciprocal Rank Fusion."""

    def __init__(self) -> None:
        self.vectorstore = ChromaVectorStore()
        self.vectorstore.create_collection("textbook_chunks")
        self.index_path = get_data_paths()["vectors"] / "bm25_chunks.json"

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        query_embedding = get_embedder().embed_texts([query])[0]
        vector_hits = self.vectorstore.query(query_embedding, n_results=10)
        bm25_hits = self._bm25_query(query, n_results=10)
        return self._rrf(vector_hits, bm25_hits)[:top_k]

    def _bm25_query(self, query: str, n_results: int) -> list[dict[str, Any]]:
        chunks = _load_chunks(self.index_path)
        if not chunks:
            return []
        corpus = [_tokenize(chunk["content"]) for chunk in chunks]
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(_tokenize(query))
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:n_results]
        return [{**chunks[i], "score": float(score)} for i, score in ranked if score > 0]

    def _rrf(self, vector_hits: list[dict[str, Any]], bm25_hits: list[dict[str, Any]], k: int = 60) -> list[dict[str, Any]]:
        fused: dict[str, dict[str, Any]] = {}
        for hits in (vector_hits, bm25_hits):
            for rank, hit in enumerate(hits, 1):
                hit_id = str(hit.get("id") or _stable_id(hit))
                entry = fused.setdefault(hit_id, {**hit, "score": 0.0})
                entry["score"] += 1.0 / (k + rank)
        return sorted(fused.values(), key=lambda item: item["score"], reverse=True)


def save_bm25_chunks(chunks: list[dict[str, Any]]) -> None:
    path = get_data_paths()["vectors"] / "bm25_chunks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_chunks(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+", text.lower())


def _stable_id(hit: dict[str, Any]) -> str:
    metadata = hit.get("metadata", {})
    return f"{metadata.get('textbook')}:{metadata.get('chapter')}:{metadata.get('chunk_index')}"
