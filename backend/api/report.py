from __future__ import annotations

from collections import Counter

from fastapi import APIRouter

from backend.models.database import get_all_textbooks, get_decisions, get_kg_data

router = APIRouter()


@router.get("/api/report")
async def integration_report() -> dict:
    textbooks = await get_all_textbooks()
    decisions = await get_decisions()
    all_nodes = []
    all_edges = []
    for textbook in textbooks:
        nodes, edges = await get_kg_data(textbook.id)
        all_nodes.extend(nodes)
        all_edges.extend(edges)

    removed = {node_id for decision in decisions if decision.action == "remove" for node_id in decision.affected_nodes}
    original_chars = sum(textbook.total_chars for textbook in textbooks)
    compressed_chars = sum(len(node.definition) for node in all_nodes if node.id not in removed)
    action_counts = Counter(decision.action for decision in decisions)
    notable = [
        decision.model_dump(mode="json")
        for decision in sorted(decisions, key=lambda item: item.confidence, reverse=True)
        if decision.action == "merge"
    ][:10]
    return {
        "original_stats": {
            "total_textbooks": len(textbooks),
            "total_chars": original_chars,
            "total_chapters": sum(len(textbook.chapters) for textbook in textbooks),
        },
        "compressed_stats": {
            "compressed_chars": compressed_chars,
            "compression_ratio": (compressed_chars / original_chars) if original_chars else 0.0,
        },
        "decision_summary": {
            "merge": action_counts.get("merge", 0),
            "keep": action_counts.get("keep", 0),
            "remove": action_counts.get("remove", 0),
        },
        "knowledge_graph_stats": {
            "nodes": len(all_nodes),
            "edges": len(all_edges),
            "textbooks_with_graph": sum(1 for textbook in textbooks if any(node.textbook_id == textbook.id for node in all_nodes)),
        },
        "notable_integration_cases": notable,
    }
