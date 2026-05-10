from __future__ import annotations

import asyncio
import json
import logging
import re

from fastapi import APIRouter, HTTPException

from backend.core.kg.extractor import extract_knowledge_points
from backend.core.kg.graph_builder import build_graph
from backend.core.llm.client import chat_completion
from backend.core.llm.prompts import RELATION_EXTRACTION_PROMPT
from backend.models.database import get_all_textbooks, get_kg_data, get_textbook, save_kg_data
from backend.models.schemas import KnowledgeEdge, KnowledgeNode

router = APIRouter()
logger = logging.getLogger(__name__)

# 后台任务队列：记录正在构建的教材
_building_tasks: dict[str, bool] = {}


async def _process_chapter(chapter, textbook_id: str) -> tuple[list[KnowledgeNode], list[KnowledgeEdge]]:
    """处理单个章节（提取知识点+关系）"""
    chapter_nodes = await extract_knowledge_points(chapter.content, chapter.title, textbook_id)
    chapter_edges = await _extract_relations(chapter_nodes)
    return chapter_nodes, chapter_edges


@router.post("/api/kg/build/{textbook_id}")
async def build_textbook_kg(textbook_id: str, quick: bool = True) -> dict:
    """构建知识图谱。quick=True 时只处理前3个有效章节，快速返回。"""
    textbook = await get_textbook(textbook_id)
    if textbook is None:
        raise HTTPException(status_code=404, detail="Textbook not found")

    # 筛选有效章节（内容 > 100 字）
    valid_chapters = [ch for ch in textbook.chapters if len(ch.content) > 100]

    if quick:
        chapters_to_process = valid_chapters[:3]
    else:
        chapters_to_process = valid_chapters[:20]

    # 并发处理所有章节（大幅提速！）
    results = await asyncio.gather(
        *[_process_chapter(ch, textbook.id) for ch in chapters_to_process],
        return_exceptions=True,
    )

    nodes: list[KnowledgeNode] = []
    edges: list[KnowledgeEdge] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Chapter processing failed: %s", result)
            continue
        chapter_nodes, chapter_edges = result
        nodes.extend(chapter_nodes)
        edges.extend(chapter_edges)

    await save_kg_data(textbook.id, nodes, edges)

    # 如果是快速模式，启动后台任务继续处理剩余章节
    if quick and len(valid_chapters) > 3:
        asyncio.create_task(_build_remaining(textbook.id, valid_chapters[3:20]))

    return build_graph(nodes, edges)


async def _build_remaining(textbook_id: str, remaining_chapters: list) -> None:
    """后台处理剩余章节"""
    if _building_tasks.get(textbook_id):
        return
    _building_tasks[textbook_id] = True

    try:
        existing_nodes, existing_edges = await get_kg_data(textbook_id)
        nodes = list(existing_nodes)
        edges = list(existing_edges)

        # 并发处理
        results = await asyncio.gather(
            *[_process_chapter(ch, textbook_id) for ch in remaining_chapters],
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                continue
            chapter_nodes, chapter_edges = result
            nodes.extend(chapter_nodes)
            edges.extend(chapter_edges)

        await save_kg_data(textbook_id, nodes, edges)
        logger.info("Background KG build completed for %s: %d nodes", textbook_id, len(nodes))
    finally:
        _building_tasks.pop(textbook_id, None)


@router.get("/api/kg/build-status/{textbook_id}")
async def build_status(textbook_id: str) -> dict:
    """查询知识图谱构建状态"""
    is_building = _building_tasks.get(textbook_id, False)
    nodes, edges = await get_kg_data(textbook_id)
    return {
        "is_building": is_building,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


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
        raw = await chat_completion([{"role": "user", "content": prompt}], temperature=0.1, max_tokens=2000)
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
