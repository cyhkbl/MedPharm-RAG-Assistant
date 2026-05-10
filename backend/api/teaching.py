"""教学创新功能 API：测验生成、教学大纲、覆盖率分析"""
from __future__ import annotations

from fastapi import APIRouter, Query

from backend.core.teaching import compute_coverage_matrix, generate_quiz, generate_teaching_outline
from backend.models.database import get_all_textbooks, get_kg_data

router = APIRouter()


@router.get("/api/teaching/quiz")
async def quiz(n: int = Query(default=10, ge=1, le=50)) -> dict:
    """基于整合知识点自动生成测验题"""
    nodes = []
    for tb in await get_all_textbooks():
        tb_nodes, _ = await get_kg_data(tb.id)
        nodes.extend(tb_nodes)

    questions = await generate_quiz(nodes, n=n)
    return {
        "total": len(questions),
        "by_difficulty": {
            "简单": sum(1 for q in questions if q.get("difficulty") == "简单"),
            "中等": sum(1 for q in questions if q.get("difficulty") == "中等"),
            "困难": sum(1 for q in questions if q.get("difficulty") == "困难"),
        },
        "questions": questions,
    }


@router.get("/api/teaching/outline")
async def outline() -> dict:
    """基于知识图谱自动生成教学大纲"""
    nodes = []
    edges = []
    for tb in await get_all_textbooks():
        tb_nodes, tb_edges = await get_kg_data(tb.id)
        nodes.extend(tb_nodes)
        edges.extend(tb_edges)

    return await generate_teaching_outline(nodes, edges)


@router.get("/api/teaching/coverage")
async def coverage() -> dict:
    """教材×知识点分类覆盖率矩阵"""
    nodes = []
    for tb in await get_all_textbooks():
        tb_nodes, _ = await get_kg_data(tb.id)
        nodes.extend(tb_nodes)

    return compute_coverage_matrix(nodes)
