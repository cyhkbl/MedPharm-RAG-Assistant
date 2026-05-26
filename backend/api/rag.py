from __future__ import annotations

import hashlib
import json
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
async def build_rag_index(force_rebuild: bool = False) -> dict:
    """Build or incrementally update the RAG index.

    Args:
        force_rebuild: If True, rebuild the entire index from scratch.
    """
    textbooks = await get_all_textbooks()

    # Load existing index manifest for incremental updates
    manifest = _load_index_manifest()
    indexed_hashes: dict[str, str] = manifest.get("chunk_hashes", {})

    all_chunks: list[dict[str, Any]] = []
    new_chunks: list[dict[str, Any]] = []
    chunk_hashes: dict[str, str] = {}

    for textbook in textbooks:
        for chapter in textbook.chapters:
            chunks = chunk_text(
                chapter.content,
                textbook=textbook.title,
                textbook_id=textbook.id,
                chapter=chapter.title,
                chapter_id=chapter.chapter_id,
                page=chapter.page_start,
            )
            for chunk in chunks:
                # Compute content hash for change detection
                content_hash = hashlib.md5(chunk["content"].encode()).hexdigest()
                chunk_key = f"{textbook.id}:{chapter.chapter_id}:{chunk['metadata']['chunk_index']}"
                chunk_hashes[chunk_key] = content_hash

                all_chunks.append(chunk)
                # Only index if content changed or force rebuild
                if force_rebuild or indexed_hashes.get(chunk_key) != content_hash:
                    new_chunks.append(chunk)

    if not new_chunks and not force_rebuild:
        _write_status(len(textbooks), len(all_chunks))
        return {
            "indexed_textbooks": len(textbooks),
            "total_chunks": len(all_chunks),
            "new_chunks": 0,
            "updated_at": datetime.utcnow().isoformat(),
            "message": "Index is up to date, no changes needed.",
        }

    # Generate IDs and embeddings for new chunks
    docs = [chunk["content"] for chunk in new_chunks]
    metadatas = [chunk["metadata"] for chunk in new_chunks]
    ids = [
        f"{metadata.get('textbook_id')}:{metadata.get('chapter_id')}:{metadata.get('chunk_index')}:{uuid4().hex[:8]}"
        for metadata in metadatas
    ]

    embeddings = get_embedder().embed_texts(docs)
    vectorstore = ChromaVectorStore()
    vectorstore.create_collection("textbook_chunks")

    if force_rebuild:
        # Delete and recreate the collection
        try:
            vectorstore.client.delete_collection("textbook_chunks")
        except Exception:
            pass
        vectorstore.create_collection("textbook_chunks")

    vectorstore.add_documents(docs, embeddings, metadatas, ids=ids)

    # Update BM25 index: merge new chunks with existing ones
    if force_rebuild:
        bm25_chunks = [
            {"id": ids[i], "content": docs[i], "metadata": metadatas[i], "score": 0.0}
            for i in range(len(docs))
        ]
    else:
        existing_bm25 = _load_existing_bm25_chunks()
        existing_ids = {c["id"] for c in existing_bm25}
        # Remove old chunks that were updated, add new ones
        updated_keys = {k for k, v in chunk_hashes.items() if indexed_hashes.get(k) != v}
        existing_bm25 = [c for c in existing_bm25 if not any(
            f"{c['metadata'].get('textbook_id')}:{c['metadata'].get('chapter_id')}:{c['metadata'].get('chunk_index')}" == k
            for k in updated_keys
        )]
        new_bm25 = [
            {"id": ids[i], "content": docs[i], "metadata": metadatas[i], "score": 0.0}
            for i in range(len(docs))
        ]
        bm25_chunks = existing_bm25 + new_bm25

    save_bm25_chunks(bm25_chunks)

    # Save updated manifest
    manifest["chunk_hashes"] = chunk_hashes
    manifest["updated_at"] = datetime.utcnow().isoformat()
    manifest["total_chunks"] = len(all_chunks)
    _save_index_manifest(manifest)

    _write_status(len(textbooks), len(all_chunks))
    return {
        "indexed_textbooks": len(textbooks),
        "total_chunks": len(all_chunks),
        "new_chunks": len(new_chunks),
        "updated_at": datetime.utcnow().isoformat(),
    }


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
    data = json.loads(path.read_text(encoding="utf-8"))
    data["ready"] = data.get("total_chunks", 0) > 0
    return data


def _write_status(textbook_count: int, chunk_count: int) -> None:
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


def _manifest_path() -> Path:
    return get_data_paths()["vectors"] / "index_manifest.json"


def _load_index_manifest() -> dict:
    path = _manifest_path()
    if not path.exists():
        return {"chunk_hashes": {}, "updated_at": None, "total_chunks": 0}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"chunk_hashes": {}, "updated_at": None, "total_chunks": 0}


def _save_index_manifest(manifest: dict) -> None:
    path = _manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_existing_bm25_chunks() -> list[dict[str, Any]]:
    path = get_data_paths()["vectors"] / "bm25_chunks.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
