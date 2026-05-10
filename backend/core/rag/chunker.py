from __future__ import annotations

from typing import Any

from backend.utils.text_utils import clean_text


def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100, **metadata: Any) -> list[dict]:
    """Split text with a sliding window and attach retrieval metadata."""

    cleaned = clean_text(text)
    if not cleaned:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")

    chunks: list[dict] = []
    start = 0
    index = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        content = cleaned[start:end]
        chunks.append(
            {
                "content": content,
                "metadata": {
                    "textbook": metadata.get("textbook", ""),
                    "chapter": metadata.get("chapter", ""),
                    "page": int(metadata.get("page", 1) or 1),
                    "chunk_index": index,
                    **{k: v for k, v in metadata.items() if k not in {"textbook", "chapter", "page"}},
                },
            }
        )
        if end == len(cleaned):
            break
        start = end - overlap
        index += 1
    return chunks
