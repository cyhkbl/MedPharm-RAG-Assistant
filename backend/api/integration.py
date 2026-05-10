from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.kg.aligner import align_knowledge_points
from backend.core.kg.integrator import calculate_compression_ratio, integrate
from backend.models.database import get_all_textbooks, get_decisions, get_kg_data, save_decisions
from backend.models.schemas import IntegrationDecision, IntegrationStats, KnowledgeNode

router = APIRouter()


class OverrideRequest(BaseModel):
    decision_id: str
    action: str
    reason: str = "用户手动覆盖"


@router.post("/api/integrate")
async def run_integration() -> dict:
    nodes = await _all_nodes()
    matches = await align_knowledge_points(nodes)
    decisions = await integrate(nodes, matches)
    await save_decisions(decisions)
    return {
        "matched_pairs": [
            {"source": a.id, "target": b.id, "score": score}
            for a, b, score in matches
        ],
        "decisions": [decision.model_dump(mode="json") for decision in decisions],
        "compression_ratio": calculate_compression_ratio(nodes, decisions),
    }


@router.get("/api/integrate/decisions")
async def integration_decisions() -> list[dict]:
    return [decision.model_dump(mode="json") for decision in await get_decisions()]


@router.post("/api/integrate/override")
async def override_decision(payload: OverrideRequest) -> dict:
    decisions = await get_decisions()
    valid_actions = {"merge", "keep", "remove"}
    if payload.action not in valid_actions:
        raise HTTPException(status_code=400, detail="Invalid action")
    for index, decision in enumerate(decisions):
        if decision.decision_id == payload.decision_id:
            decisions[index] = IntegrationDecision(
                decision_id=decision.decision_id,
                action=payload.action,  # type: ignore[arg-type]
                affected_nodes=decision.affected_nodes,
                result_node=decision.result_node,
                reason=payload.reason,
                confidence=1.0,
            )
            await save_decisions(decisions)
            return decisions[index].model_dump(mode="json")
    raise HTTPException(status_code=404, detail="Decision not found")


@router.get("/api/integrate/stats")
async def integration_stats() -> dict:
    nodes = await _all_nodes()
    decisions = await get_decisions()
    removed = {node_id for decision in decisions if decision.action == "remove" for node_id in decision.affected_nodes}
    original_chars = sum(len(node.definition) for node in nodes)
    compressed_chars = sum(len(node.definition) for node in nodes if node.id not in removed)
    stats = IntegrationStats(
        original_chars=original_chars,
        compressed_chars=compressed_chars,
        compression_ratio=(compressed_chars / original_chars) if original_chars else 0.0,
        merge_count=sum(1 for decision in decisions if decision.action == "merge"),
        keep_count=sum(1 for decision in decisions if decision.action == "keep"),
        remove_count=sum(1 for decision in decisions if decision.action == "remove"),
    )
    return stats.model_dump(mode="json")


async def _all_nodes() -> list[KnowledgeNode]:
    nodes: list[KnowledgeNode] = []
    for textbook in await get_all_textbooks():
        kg_nodes, _ = await get_kg_data(textbook.id)
        nodes.extend(kg_nodes)
    return nodes
