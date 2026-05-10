"""学习路径与知识点难度评估 API"""
from __future__ import annotations

from fastapi import APIRouter, Query

from backend.core.learning_path import assess_difficulty, recommend_learning_path
from backend.models.database import get_all_textbooks, get_kg_data

router = APIRouter()


@router.get("/api/learning/difficulty")
async def difficulty_assessment(textbook_id: str | None = None) -> dict:
    """评估知识点难度（基于频次+前置依赖深度）"""
    nodes = []
    edges = []
    if textbook_id:
        n, e = await get_kg_data(textbook_id)
        nodes.extend(n)
        edges.extend(e)
    else:
        for tb in await get_all_textbooks():
            n, e = await get_kg_data(tb.id)
            nodes.extend(n)
            edges.extend(e)

    results = assess_difficulty(nodes, edges)
    return {
        "total": len(results),
        "by_level": {
            "入门": sum(1 for r in results if r["difficulty"] == 1),
            "中级": sum(1 for r in results if r["difficulty"] == 2),
            "高级": sum(1 for r in results if r["difficulty"] == 3),
        },
        "items": results[:100],  # 限制返回数量
    }


@router.get("/api/learning/path")
async def learning_path(target: str | None = None) -> dict:
    """推荐学习路径（基于 prerequisite 关系的拓扑排序）"""
    nodes = []
    edges = []
    for tb in await get_all_textbooks():
        n, e = await get_kg_data(tb.id)
        nodes.extend(n)
        edges.extend(e)

    return recommend_learning_path(nodes, edges, target)
