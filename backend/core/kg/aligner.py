from __future__ import annotations

import json
import re
from itertools import combinations

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from backend.core.llm.client import chat_completion
from backend.core.llm.prompts import EQUIVALENCE_JUDGMENT_PROMPT
from backend.core.rag.embedder import get_embedder
from backend.models.schemas import KnowledgeNode


async def align_knowledge_points(all_nodes: list[KnowledgeNode]) -> list[tuple[KnowledgeNode, KnowledgeNode, float]]:
    """Align equivalent knowledge points with embeddings plus LLM verification."""

    if len(all_nodes) < 2:
        return []

    texts = [f"{node.name}\n{node.definition}\n{node.category}" for node in all_nodes]
    embeddings = np.array(get_embedder().embed_texts(texts), dtype=np.float32)
    similarity = cosine_similarity(embeddings)
    matches: list[tuple[KnowledgeNode, KnowledgeNode, float]] = []

    for i, j in combinations(range(len(all_nodes)), 2):
        score = float(similarity[i, j])
        if score < 0.85:
            continue
        if all_nodes[i].id == all_nodes[j].id:
            continue
        if await _verify_equivalence(all_nodes[i], all_nodes[j]):
            matches.append((all_nodes[i], all_nodes[j], score))
    return matches


async def _verify_equivalence(node_a: KnowledgeNode, node_b: KnowledgeNode) -> bool:
    if node_a.name == node_b.name:
        return True
    prompt = EQUIVALENCE_JUDGMENT_PROMPT.format(
        node_a=json.dumps(node_a.model_dump(mode="json"), ensure_ascii=False),
        node_b=json.dumps(node_b.model_dump(mode="json"), ensure_ascii=False),
    )
    try:
        raw = await chat_completion([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=500)
        data = _json_object(raw)
        return bool(data.get("is_equivalent"))
    except Exception:
        return False


def _json_object(text: str) -> dict:
    """Extract JSON object from LLM output with robust fallback parsing."""
    stripped = text.strip()
    # Remove markdown code fences
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.DOTALL)
        stripped = stripped.strip()

    # Attempt 1: direct parse
    try:
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    # Attempt 2: find outermost {...} using brace matching
    start = stripped.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(stripped)):
            if stripped[i] == "{":
                depth += 1
            elif stripped[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        payload = json.loads(stripped[start : i + 1])
                        if isinstance(payload, dict):
                            return payload
                    except json.JSONDecodeError:
                        pass
                    break

    # Attempt 3: fix trailing commas
    try:
        fixed = re.sub(r",\s*([}\]])", r"\1", stripped[start:] if start != -1 else stripped)
        payload = json.loads(fixed)
        if isinstance(payload, dict):
            return payload
    except (json.JSONDecodeError, UnboundLocalError):
        pass

    return {}
