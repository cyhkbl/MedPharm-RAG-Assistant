from __future__ import annotations

from collections import Counter

from fastapi import APIRouter

from backend.models.database import get_all_textbooks, get_decisions, get_kg_data

router = APIRouter()


async def _generate_report_data() -> dict:
    """生成整合报告数据"""
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


@router.get("/api/report")
async def integration_report() -> dict:
    return await _generate_report_data()


@router.get("/api/report/pdf")
async def report_pdf():
    """导出整合报告为 PDF"""
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    report_data = await _generate_report_data()

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    _width, height = A4
    y = height - 30 * mm

    def draw_text(text: str, yy: float, size: int = 10) -> float:
        c.setFont("Helvetica", size)
        c.drawString(30 * mm, yy, text)
        return yy - 5 * mm

    y = draw_text("Medical Textbook Knowledge Integration Report", y, 16)
    y -= 5 * mm
    y = draw_text(f"Textbooks: {report_data['original_stats']['total_textbooks']}", y)
    y = draw_text(f"Original chars: {report_data['original_stats']['total_chars']}", y)
    y = draw_text(f"Compressed chars: {report_data['compressed_stats']['compressed_chars']}", y)
    y = draw_text(f"Compression ratio: {report_data['compressed_stats']['compression_ratio']*100:.1f}%", y)
    y -= 5 * mm
    y = draw_text("Decision Summary:", y, 12)
    for action, count in report_data.get("decision_summary", {}).items():
        y = draw_text(f"  {action}: {count}", y)
    y -= 5 * mm
    y = draw_text("Knowledge Graph:", y, 12)
    y = draw_text(f"  Nodes: {report_data['knowledge_graph_stats']['nodes']}", y)
    y = draw_text(f"  Edges: {report_data['knowledge_graph_stats']['edges']}", y)

    # Token stats
    from backend.core.llm.client import get_token_stats
    stats = get_token_stats().to_dict()
    y -= 5 * mm
    y = draw_text("Token Usage:", y, 12)
    y = draw_text(f"  Total calls: {stats['total_calls']}", y)
    y = draw_text(f"  Total tokens: {stats['total_tokens']}", y)
    y = draw_text(f"  Avg latency: {stats['avg_elapsed_ms']:.0f}ms", y)

    c.save()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=integration_report.pdf"},
    )
