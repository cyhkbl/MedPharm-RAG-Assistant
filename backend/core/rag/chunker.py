from __future__ import annotations

import re
from typing import Any

from backend.utils.text_utils import clean_text


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 150,
    **metadata: Any,
) -> list[dict]:
    """Split text semantically with chapter-title prefix injection.

    Strategy:
    1. Split by paragraphs (double newline).
    2. Merge consecutive short paragraphs up to chunk_size.
    3. For each chunk, prepend chapter/title metadata as context prefix.
    """

    cleaned = clean_text(text)
    if not cleaned:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")

    # Build a context prefix from metadata (e.g. "教材: 病理学 | 章节: 第一章 绪论")
    prefix = _build_prefix(metadata)

    # Step 1: split by paragraphs
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", cleaned) if p.strip()]

    # Step 2: merge paragraphs into chunks
    raw_chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for para in paragraphs:
        # If a single paragraph exceeds chunk_size, split it with sliding window
        if len(para) > chunk_size:
            if current_parts:
                raw_chunks.append("\n\n".join(current_parts))
                current_parts = []
                current_len = 0
            raw_chunks.extend(_sliding_window(para, chunk_size, overlap))
            continue

        if current_len + len(para) + 2 > chunk_size and current_parts:
            raw_chunks.append("\n\n".join(current_parts))
            # Keep overlap: retain the last paragraph if it fits in overlap
            overlap_parts: list[str] = []
            overlap_len = 0
            for p in reversed(current_parts):
                if overlap_len + len(p) > overlap:
                    break
                overlap_parts.insert(0, p)
                overlap_len += len(p) + 2
            current_parts = overlap_parts
            current_len = overlap_len

        current_parts.append(para)
        current_len += len(para) + 2

    if current_parts:
        raw_chunks.append("\n\n".join(current_parts))

    # Step 3: attach metadata with prefix
    chunks: list[dict] = []
    for index, content in enumerate(raw_chunks):
        full_content = f"{prefix}\n{content}" if prefix else content
        chunks.append(
            {
                "content": full_content,
                "metadata": {
                    "textbook": metadata.get("textbook", ""),
                    "chapter": metadata.get("chapter", ""),
                    "page": int(metadata.get("page", 1) or 1),
                    "chunk_index": index,
                    **{k: v for k, v in metadata.items() if k not in {"textbook", "chapter", "page"}},
                },
            }
        )
    return chunks


def _build_prefix(metadata: dict[str, Any]) -> str:
    """Build a short context prefix from chunk metadata."""
    parts: list[str] = []
    textbook = metadata.get("textbook", "")
    if textbook:
        parts.append(f"教材: {textbook}")
    chapter = metadata.get("chapter", "")
    if chapter:
        parts.append(f"章节: {chapter}")
    return " | ".join(parts)


def _sliding_window(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Fallback sliding-window split for oversized paragraphs."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks
