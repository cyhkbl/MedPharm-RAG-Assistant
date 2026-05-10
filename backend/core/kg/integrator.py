from __future__ import annotations

import uuid

from backend.models.schemas import IntegrationDecision, KnowledgeNode


async def integrate(
    all_nodes: list[KnowledgeNode],
    matched_pairs: list[tuple[KnowledgeNode, KnowledgeNode, float]],
) -> list[IntegrationDecision]:
    """Generate merge/keep/remove decisions from aligned nodes."""

    parent: dict[str, str] = {node.id: node.id for node in all_nodes}
    by_id = {node.id: node for node in all_nodes}

    def find(node_id: str) -> str:
        while parent[node_id] != node_id:
            parent[node_id] = parent[parent[node_id]]
            node_id = parent[node_id]
        return node_id

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    for node_a, node_b, _ in matched_pairs:
        union(node_a.id, node_b.id)

    groups: dict[str, list[KnowledgeNode]] = {}
    for node in all_nodes:
        groups.setdefault(find(node.id), []).append(node)

    decisions: list[IntegrationDecision] = []
    for group in groups.values():
        if len(group) == 1:
            node = group[0]
            decisions.append(
                IntegrationDecision(
                    decision_id=_decision_id("keep", [node.id]),
                    action="keep",
                    affected_nodes=[node.id],
                    result_node=node.id,
                    reason="唯一知识点，保留原始表述。",
                    confidence=0.95,
                )
            )
            continue
        result = max(group, key=lambda item: len(item.definition))
        decisions.append(
            IntegrationDecision(
                decision_id=_decision_id("merge", [node.id for node in group]),
                action="merge",
                affected_nodes=[node.id for node in group],
                result_node=result.id,
                reason="语义等价知识点合并，保留定义最完整的版本。",
                confidence=0.9,
            )
        )
        for node in group:
            if node.id != result.id and node.id in by_id:
                decisions.append(
                    IntegrationDecision(
                        decision_id=_decision_id("remove", [node.id]),
                        action="remove",
                        affected_nodes=[node.id],
                        result_node=result.id,
                        reason=f"已合并到更完整知识点：{result.name}",
                        confidence=0.88,
                    )
                )
    return decisions


def calculate_compression_ratio(all_nodes: list[KnowledgeNode], decisions: list[IntegrationDecision]) -> float:
    original = sum(len(node.definition) for node in all_nodes) or 1
    removed = {node_id for decision in decisions if decision.action == "remove" for node_id in decision.affected_nodes}
    remaining = sum(len(node.definition) for node in all_nodes if node.id not in removed)
    return remaining / original


def _decision_id(action: str, node_ids: list[str]) -> str:
    seed = f"{action}:{':'.join(sorted(node_ids))}"
    return f"dec_{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:16]}"
