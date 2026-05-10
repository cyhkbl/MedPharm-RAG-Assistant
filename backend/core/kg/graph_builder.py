from __future__ import annotations

from collections import Counter

from backend.models.schemas import KnowledgeEdge, KnowledgeNode


def build_graph(nodes: list[KnowledgeNode], edges: list[KnowledgeEdge]) -> dict:
    """Build graph JSON and compute cross-textbook frequency by node name."""

    frequency = Counter(node.name for node in nodes)
    node_payload = []
    for node in nodes:
        data = node.model_dump(mode="json")
        data["frequency"] = frequency[node.name]
        node_payload.append(data)

    known_ids = {node.id for node in nodes}
    edge_payload = [
        edge.model_dump(mode="json")
        for edge in edges
        if edge.source in known_ids and edge.target in known_ids and edge.source != edge.target
    ]
    return {"nodes": node_payload, "edges": edge_payload}
