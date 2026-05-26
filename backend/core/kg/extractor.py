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
    """Extract JSON array from LLM output with robust fallback parsing."""
    stripped = text.strip()
    # Remove markdown code fences
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.DOTALL)
        stripped = stripped.strip()

    # Attempt 1: direct parse
    try:
        payload = json.loads(stripped)
        if isinstance(payload, list):
            return payload
    except json.JSONDecodeError:
        pass

    # Attempt 2: find the outermost [...] using bracket matching
    start = stripped.find("[")
    if start != -1:
        depth = 0
        for i in range(start, len(stripped)):
            if stripped[i] == "[":
                depth += 1
            elif stripped[i] == "]":
                depth -= 1
                if depth == 0:
                    try:
                        payload = json.loads(stripped[start : i + 1])
                        if isinstance(payload, list):
                            return payload
                    except json.JSONDecodeError:
                        pass
                    break

    # Attempt 3: try fixing common LLM JSON mistakes (trailing commas, single quotes)
    try:
        fixed = re.sub(r",\s*([}\]])", r"\1", stripped[start:] if start != -1 else stripped)
        fixed = fixed.replace("'", '"')
        payload = json.loads(fixed)
        if isinstance(payload, list):
            return payload
    except (json.JSONDecodeError, UnboundLocalError):
        pass

    return []


def _node_id(textbook: str, chapter: str, index: int, name: str) -> str:
    seed = f"{textbook}:{chapter}:{index}:{name}"
    return f"kn_{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:16]}"
