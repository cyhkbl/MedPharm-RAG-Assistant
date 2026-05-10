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


@router.post("/api/kg/build/{textbook_id}")
async def build_textbook_kg(textbook_id: str, quick: bool = True) -> dict:
    """构建知识图谱。quick=True 时只处理前5个有效章节，快速返回。"""
    textbook = await get_textbook(textbook_id)
    if textbook is None:
        raise HTTPException(status_code=404, detail="Textbook not found")

    # 筛选有效章节（内容 > 100 字）
    valid_chapters = [ch for ch in textbook.chapters if len(ch.content) > 100]

    if quick:
        # 快速模式：只处理前3个章节
        chapters_to_process = valid_chapters[:3]
    else:
        # 完整模式：处理所有章节（最多20个）
        chapters_to_process = valid_chapters[:20]

    nodes: list[KnowledgeNode] = []
    edges: list[KnowledgeEdge] = []

    for chapter in chapters_to_process:
        try:
            chapter_nodes = await extract_knowledge_points(
                chapter.content, chapter.title, textbook.id
            )
            nodes.extend(chapter_nodes)
            edges.extend(await _extract_relations(chapter_nodes))
        except Exception as e:
            logger.warning("Failed to process chapter %s: %s", chapter.title, e)
            continue

    await save_kg_data(textbook.id, nodes, edges)

    # 如果是快速模式，启动后台任务继续处理剩余章节
    if quick and len(valid_chapters) > 5:
        asyncio.create_task(_build_remaining(textbook.id, valid_chapters[5:30]))

    return build_graph(nodes, edges)


async def _build_remaining(textbook_id: str, remaining_chapters: list) -> None:
    """后台处理剩余章节"""
    if _building_tasks.get(textbook_id):
        return
    _building_tasks[textbook_id] = True

    try:
        # 加载已有的节点和边
        existing_nodes, existing_edges = await get_kg_data(textbook_id)
        nodes = list(existing_nodes)
        edges = list(existing_edges)

        for chapter in remaining_chapters:
            try:
                chapter_nodes = await extract_knowledge_points(
                    chapter.content, chapter.title, textbook_id
                )
                nodes.extend(chapter_nodes)
                edges.extend(await _extract_relations(chapter_nodes))
            except Exception as e:
                logger.warning("Background: failed chapter %s: %s", chapter.title, e)
                continue

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
