"""教学创新功能：测验生成、教学大纲、覆盖率分析"""
from __future__ import annotations

import json
import re
from typing import Any

from backend.core.llm.client import chat_completion
from backend.models.database import get_all_textbooks, get_kg_data
from backend.models.schemas import KnowledgeNode


async def generate_quiz(
    nodes: list[KnowledgeNode],
    n: int = 10,
    difficulty: str = "mixed",
) -> list[dict]:
    """基于知识点自动生成测验题。

    Args:
        nodes: 知识点列表
        n: 题目数量
        difficulty: easy/medium/hard/mixed
    """
    # 按分类组织知识点
    by_category: dict[str, list[str]] = {}
    for node in nodes[:50]:  # 限制输入长度
        cat = node.category or "其他"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(f"{node.name}: {node.definition[:80]}")

    context_parts = []
    for cat, items in by_category.items():
        context_parts.append(f"【{cat}】\n" + "\n".join(items[:8]))
    context = "\n\n".join(context_parts[:6])

    prompt = f"""你是医学教育专家。基于以下知识点，生成 {n} 道测验题。

知识点：
{context}

要求：
- 难度分布：简单30%、中等50%、困难20%
- 题型：选择题60%、简答题40%
- 每题包含：题目、选项（选择题）、正确答案、解析、难度、涉及知识点
- 输出严格 JSON 数组

输出格式：
[
  {{
    "type": "选择题",
    "difficulty": "简单",
    "question": "...",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "answer": "A",
    "explanation": "...",
    "knowledge_points": ["知识点1"]
  }}
]
"""
    try:
        raw = await chat_completion([{"role": "user", "content": prompt}], temperature=0.3, max_tokens=4000)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL)
        match = re.search(r"\[[\s\S]*\]", raw)
        return json.loads(match.group(0)) if match else []
    except Exception:
        return _fallback_quiz(nodes, n)


def _fallback_quiz(nodes: list[KnowledgeNode], n: int) -> list[dict]:
    """LLM 失败时的兜底测验"""
    quiz = []
    for node in nodes[:n]:
        quiz.append({
            "type": "简答题",
            "difficulty": "中等",
            "question": f"请简述{node.name}的定义。",
            "options": [],
            "answer": node.definition[:200] if node.definition else "见教材原文",
            "explanation": f"来源：{node.chapter}",
            "knowledge_points": [node.name],
        })
    return quiz


async def generate_teaching_outline(
    nodes: list[KnowledgeNode],
    edges: list[dict] | None = None,
) -> dict:
    """基于知识图谱自动生成教学大纲。

    Returns:
        {
            "course_name": "...",
            "total_hours": N,
            "chapters": [
                {
                    "title": "...",
                    "hours": N,
                    "objectives": ["..."],
                    "key_points": ["..."],
                    "prerequisites": ["..."]
                }
            ]
        }
    """
    # 按分类组织
    by_category: dict[str, list[str]] = {}
    for node in nodes:
        cat = node.category or "其他"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(node.name)

    categories_summary = "\n".join(
        f"- {cat}: {', '.join(items[:10])}" for cat, items in by_category.items()
    )

    prompt = f"""你是医学教育课程设计专家。基于以下知识点分类，生成一份完整的教学大纲。

知识点分类：
{categories_summary}

要求：
1. 设计 10-15 个教学单元
2. 每个单元包含：标题、学时、教学目标、重点知识点、前置要求
3. 总学时控制在 48-72 学时
4. 按照从基础到临床的逻辑顺序排列
5. 输出严格 JSON

输出格式：
{
  "course_name": "医学整合课程",
  "total_hours": 64,
  "chapters": [
    {
      "title": "第一章 ...",
      "hours": 4,
      "objectives": ["掌握...", "理解..."],
      "key_points": ["知识点1", "知识点2"],
      "prerequisites": []
    }
  ]
}
"""
    try:
        raw = await chat_completion([{"role": "user", "content": prompt}], temperature=0.3, max_tokens=4000)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL)
        match = re.search(r"\{[\s\S]*\}", raw)
        return json.loads(match.group(0)) if match else _fallback_outline(by_category)
    except Exception:
        return _fallback_outline(by_category)


def _fallback_outline(by_category: dict[str, list[str]]) -> dict:
    """LLM 失败时的兜底大纲"""
    chapters = []
    for i, (cat, items) in enumerate(by_category.items(), 1):
        chapters.append({
            "title": f"第{i}章 {cat}",
            "hours": 4,
            "objectives": [f"掌握{cat}的核心概念"],
            "key_points": items[:5],
            "prerequisites": [chapters[-1]["title"]] if chapters else [],
        })
    return {"course_name": "医学整合课程", "total_hours": len(chapters) * 4, "chapters": chapters}


def compute_coverage_matrix(
    nodes: list[KnowledgeNode],
    categories: list[str] | None = None,
) -> dict:
    """计算教材×知识点分类的覆盖矩阵（用于热力图）。

    Returns:
        {
            "textbooks": ["教材A", "教材B", ...],
            "categories": ["解剖结构", "生理机制", ...],
            "matrix": [[12, 5, 0, ...], [8, 15, 3, ...], ...],
            "gaps": [{"textbook": "教材A", "category": "病理变化", "count": 0}]
        }
    """
    # 统计每本教材在每个分类下的知识点数量
    if not categories:
        categories = sorted(set(node.category or "其他" for node in nodes))

    textbooks = sorted(set(node.textbook_id for node in nodes))
    textbook_names = {}
    for node in nodes:
        textbook_names[node.textbook_id] = node.textbook_id  # 用 ID 作名称

    matrix = []
    gaps = []
    for tb_id in textbooks:
        row = []
        tb_nodes = [n for n in nodes if n.textbook_id == tb_id]
        for cat in categories:
            count = sum(1 for n in tb_nodes if (n.category or "其他") == cat)
            row.append(count)
            if count == 0:
                gaps.append({"textbook": tb_id, "category": cat, "count": 0})
        matrix.append(row)

    return {
        "textbooks": [textbook_names.get(tb, tb) for tb in textbooks],
        "categories": categories,
        "matrix": matrix,
        "gaps": gaps,
    }
