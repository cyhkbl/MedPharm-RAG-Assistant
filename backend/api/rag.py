from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

from backend.core.rag.chunker import chunk_text
from backend.core.rag.embedder import get_embedder
from backend.core.rag.generator import generate_answer
from backend.core.rag.retriever import HybridRetriever, save_bm25_chunks
from backend.core.rag.vectorstore import ChromaVectorStore
from backend.models.database import get_all_textbooks, get_data_paths

router = APIRouter()


class RAGQuery(BaseModel):
    query: str


@router.post("/api/rag/index")
async def build_rag_index() -> dict:
    textbooks = await get_all_textbooks()
    chunks: list[dict[str, Any]] = []
    for textbook in textbooks:
        for chapter in textbook.chapters:
            chunks.extend(
                chunk_text(
                    chapter.content,
                    textbook=textbook.title,
                    textbook_id=textbook.id,
                    chapter=chapter.title,
                    chapter_id=chapter.chapter_id,
                    page=chapter.page_start,
                )
            )

    docs = [chunk["content"] for chunk in chunks]
    metadatas = [chunk["metadata"] for chunk in chunks]
    ids = [
        f"{metadata.get('textbook_id')}:{metadata.get('chapter_id')}:{metadata.get('chunk_index')}:{uuid4().hex[:8]}"
        for metadata in metadatas
    ]
    embeddings = get_embedder().embed_texts(docs)
    vectorstore = ChromaVectorStore()
    vectorstore.create_collection("textbook_chunks")
    vectorstore.add_documents(docs, embeddings, metadatas, ids=ids)
    bm25_chunks = [
        {"id": ids[index], "content": docs[index], "metadata": metadatas[index], "score": 0.0}
        for index in range(len(docs))
    ]
    save_bm25_chunks(bm25_chunks)
    _write_status(len(textbooks), len(chunks))
    return {"indexed_textbooks": len(textbooks), "total_chunks": len(chunks), "updated_at": datetime.utcnow().isoformat()}


@router.post("/api/rag/query")
async def rag_query(payload: RAGQuery) -> dict:
    contexts = HybridRetriever().retrieve(payload.query, top_k=5)
    response = await generate_answer(payload.query, contexts)
    return response.model_dump(mode="json")


@router.get("/api/rag/status")
async def rag_status() -> dict:
    path = _status_path()
    if not path.exists():
        return {"indexed_textbooks": 0, "total_chunks": 0, "ready": False}
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    data["ready"] = data.get("total_chunks", 0) > 0
    return data


def _write_status(textbook_count: int, chunk_count: int) -> None:
    import json

    payload = {
        "indexed_textbooks": textbook_count,
        "total_chunks": chunk_count,
        "updated_at": datetime.utcnow().isoformat(),
    }
    path = _status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _status_path() -> Path:
    return get_data_paths()["vectors"] / "status.json"
