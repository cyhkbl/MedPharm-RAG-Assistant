from __future__ import annotations

import json
import re
from typing import Any

from backend.core.llm.client import chat_completion
from backend.utils.text_utils import truncate_to_tokens


async def generate_test_questions(textbook_data: dict[str, Any], n: int = 20) -> list[dict]:
    """Generate benchmark questions from parsed textbook chapter content."""

    chapters = textbook_data.get("chapters", [])
    if not chapters:
        return []
    context_parts = []
    for chapter in chapters[: min(len(chapters), 8)]:
        context_parts.append(
            f"教材：{textbook_data.get('title', textbook_data.get('filename', ''))}\n"
            f"章节：{chapter.get('title', '')}\n"
            f"内容：{truncate_to_tokens(str(chapter.get('content', '')), 500)}"
        )
    prompt = (
        "请基于以下医学教材内容生成评测问题，严格输出 JSON 数组。"
        "题型包含 factual、comparative、cross-textbook。"
        "每项字段为 question, expected_answer, source_textbook, source_chapter, type。"
        f"生成 {n} 道。\n\n" + "\n\n".join(context_parts)
    )
    try:
        raw = await chat_completion([{"role": "user", "content": prompt}], temperature=0.4, max_tokens=3000)
        questions = _json_array(raw)
        if questions:
            return questions[:n]
    except Exception:
        return _fallback_questions(textbook_data, n)
    return _fallback_questions(textbook_data, n)


def _fallback_questions(textbook_data: dict[str, Any], n: int) -> list[dict]:
    questions: list[dict] = []
    for chapter in textbook_data.get("chapters", [])[:n]:
        content = str(chapter.get("content", ""))
        summary = content[:180]
        questions.append(
            {
                "question": f"{chapter.get('title', '本章')}的核心内容是什么？",
                "expected_answer": summary,
                "source_textbook": textbook_data.get("title", textbook_data.get("filename", "")),
                "source_chapter": chapter.get("title", ""),
                "type": "factual",
            }
        )
    return questions[:n]


def _json_array(text: str) -> list[dict]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.DOTALL)
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", stripped)
        payload = json.loads(match.group(0)) if match else []
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []
