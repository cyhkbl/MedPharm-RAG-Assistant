from __future__ import annotations

import json
import re
import uuid
from typing import Any

from pydantic import ValidationError

from backend.core.llm.client import chat_completion
from backend.core.llm.prompts import KNOWLEDGE_EXTRACTION_PROMPT
from backend.models.schemas import KnowledgeNode
from backend.utils.text_utils import truncate_to_tokens


async def extract_knowledge_points(
    chapter_content: str,
    chapter_title: str,
    textbook_name: str,
) -> list[KnowledgeNode]:
    """Extract knowledge nodes from one chapter via LLM."""

    content = truncate_to_tokens(chapter_content, 2000)
    prompt = KNOWLEDGE_EXTRACTION_PROMPT.format(chapter_content=f"教材：{textbook_name}\n章节：{chapter_title}\n内容：\n{content}")
    try:
        raw = await chat_completion([{"role": "user", "content": prompt}], temperature=0.1, max_tokens=2000)
        payload = _extract_json(raw)
        nodes: list[KnowledgeNode] = []
        for index, item in enumerate(payload, 1):
            if not isinstance(item, dict):
                continue
            item.setdefault("id", _node_id(textbook_name, chapter_title, index, str(item.get("name", ""))))
            item.setdefault("chapter", chapter_title)
            if not item.get("page"):
                item["page"] = 1
            item["textbook_id"] = textbook_name
            try:
                nodes.append(KnowledgeNode.model_validate(item))
            except ValidationError:
                continue
        return nodes
    except Exception:
        return []


def _extract_json(text: str) -> list[Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.DOTALL)
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", stripped)
        payload = json.loads(match.group(0)) if match else []
    return payload if isinstance(payload, list) else []


def _node_id(textbook: str, chapter: str, index: int, name: str) -> str:
    seed = f"{textbook}:{chapter}:{index}:{name}"
    return f"kn_{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:16]}"
