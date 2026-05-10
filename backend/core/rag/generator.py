from __future__ import annotations

import re
from typing import Any

from backend.core.llm.client import chat_completion
from backend.core.llm.prompts import RAG_ANSWER_PROMPT
from backend.models.schemas import Citation, RAGResponse


async def generate_answer(query: str, contexts: list[dict[str, Any]]) -> RAGResponse:
    """Generate a grounded answer from retrieved contexts."""

    context_text = "\n\n".join(_format_context(item, i + 1) for i, item in enumerate(contexts))
    prompt = RAG_ANSWER_PROMPT.format(context=context_text, question=query)
    answer = await chat_completion(
        [{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=1800,
    )
    citations = _build_citations(contexts, answer)
    return RAGResponse(answer=answer.strip(), citations=citations)


def _format_context(item: dict[str, Any], index: int) -> str:
    metadata = item.get("metadata", {})
    return (
        f"[{index}] 来源: {metadata.get('textbook', '')}, {metadata.get('chapter', '')}, "
        f"第{metadata.get('page', 1)}页\n{item.get('content', '')}"
    )


def _build_citations(contexts: list[dict[str, Any]], answer: str) -> list[Citation]:
    citations: list[Citation] = []
    for item in contexts:
        metadata = item.get("metadata", {})
        textbook = str(metadata.get("textbook", ""))
        chapter = str(metadata.get("chapter", ""))
        page = int(metadata.get("page", 1) or 1)
        if textbook and (textbook in answer or chapter in answer or re.search(rf"第{page}页", answer)):
            citations.append(
                Citation(
                    textbook=textbook,
                    chapter=chapter,
                    page=page,
                    relevance_score=float(item.get("score", 0.0)),
                    source_chunks=[str(item.get("content", ""))],
                )
            )
    if not citations:
        for item in contexts[:3]:
            metadata = item.get("metadata", {})
            citations.append(
                Citation(
                    textbook=str(metadata.get("textbook", "")),
                    chapter=str(metadata.get("chapter", "")),
                    page=int(metadata.get("page", 1) or 1),
                    relevance_score=float(item.get("score", 0.0)),
                    source_chunks=[str(item.get("content", ""))],
                )
            )
    return citations
