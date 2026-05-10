from __future__ import annotations

from typing import Any

from backend.models.database import get_data_paths


class ChromaVectorStore:
    """Small ChromaDB persistent wrapper."""

    def __init__(self, persist_directory: str | None = None) -> None:
        import chromadb

        self.persist_directory = persist_directory or str(get_data_paths()["vectors"])
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        self.collection = None

    def create_collection(self, name: str):
        self.collection = self.client.get_or_create_collection(name=name)
        return self.collection

    def add_documents(
        self,
        docs: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        ids: list[str] | None = None,
    ) -> None:
        if self.collection is None:
            self.create_collection("textbook_chunks")
        if not docs:
            return
        document_ids = ids or [f"doc_{i}" for i in range(len(docs))]
        self.collection.upsert(
            ids=document_ids,
            documents=docs,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def query(self, embedding: list[float], n_results: int = 10) -> list[dict[str, Any]]:
        if self.collection is None:
            self.create_collection("textbook_chunks")
        result = self.collection.query(query_embeddings=[embedding], n_results=n_results)
        rows: list[dict[str, Any]] = []
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        for index, doc_id in enumerate(ids):
            distance = float(distances[index]) if index < len(distances) else 1.0
            rows.append(
                {
                    "id": doc_id,
                    "content": docs[index] if index < len(docs) else "",
                    "metadata": metas[index] if index < len(metas) else {},
                    "score": 1.0 / (1.0 + distance),
                }
            )
        return rows
