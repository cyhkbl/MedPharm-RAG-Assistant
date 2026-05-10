from __future__ import annotations

import json
import re

from fastapi import APIRouter, HTTPException

from backend.core.kg.extractor import extract_knowledge_points
from backend.core.kg.graph_builder import build_graph
from backend.core.llm.client import chat_completion
from backend.core.llm.prompts import RELATION_EXTRACTION_PROMPT
from backend.models.database import get_all_textbooks, get_kg_data, get_textbook, save_kg_data
from backend.models.schemas import KnowledgeEdge, KnowledgeNode

router = APIRouter()


@router.post("/api/kg/build/{textbook_id}")
async def build_textbook_kg(textbook_id: str) -> dict:
    textbook = await get_textbook(textbook_id)
    if textbook is None:
        raise HTTPException(status_code=404, detail="Textbook not found")

    nodes: list[KnowledgeNode] = []
    edges: list[KnowledgeEdge] = []
    for chapter in textbook.chapters:
        chapter_nodes = await extract_knowledge_points(chapter.content, chapter.title, textbook.id)
        nodes.extend(chapter_nodes)
        edges.extend(await _extract_relations(chapter_nodes))
    await save_kg_data(textbook.id, nodes, edges)
    return build_graph(nodes, edges)


@router.get("/api/kg/all")
async def all_kg() -> dict:
    nodes: list[KnowledgeNode] = []
    edges: list[KnowledgeEdge] = []
    for textbook in await get_all_textbooks():
        kg_nodes, kg_edges = await get_kg_data(textbook.id)
        nodes.extend(kg_nodes)
        edges.extend(kg_edges)
    return build_graph(nodes, edges)


@router.get("/api/kg/{textbook_id}")
async def textbook_kg(textbook_id: str) -> dict:
    nodes, edges = await get_kg_data(textbook_id)
    return build_graph(nodes, edges)


async def _extract_relations(nodes: list[KnowledgeNode]) -> list[KnowledgeEdge]:
    if len(nodes) < 2:
        return []
    prompt = RELATION_EXTRACTION_PROMPT.format(
        knowledge_points=json.dumps([node.model_dump(mode="json") for node in nodes], ensure_ascii=False)
    )
    try:
        raw = await chat_completion([{"role": "user", "content": prompt}], temperature=0.1, max_tokens=1800)
        payload = _json_array(raw)
        edges: list[KnowledgeEdge] = []
        for item in payload:
            if isinstance(item, dict):
                try:
                    edges.append(KnowledgeEdge.model_validate(item))
                except Exception:
                    continue
        return edges
    except Exception:
        return []


def _json_array(text: str) -> list:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.DOTALL)
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", stripped)
        payload = json.loads(match.group(0)) if match else []
    return payload if isinstance(payload, list) else []
