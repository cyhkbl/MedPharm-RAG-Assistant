"""学习路径推荐与知识点难度评估"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from backend.models.schemas import KnowledgeEdge, KnowledgeNode


def assess_difficulty(nodes: list[KnowledgeNode], edges: list[KnowledgeEdge]) -> list[dict]:
    """基于频次和关系深度评估知识点难度。

    难度规则：
    - 频次越高 → 越基础 → 难度越低
    - prerequisite 入度越高 → 需要先修越多 → 难度越高
    - 无前置依赖 → 入门级（难度1）
    - 有1-2个前置 → 中级（难度2）
    - 有3+个前置 → 高级（难度3）
    """
    # 计算每个节点的 prerequisite 入度
    prereq_indegree: dict[str, int] = defaultdict(int)
    for edge in edges:
        if edge.relation_type == "prerequisite":
            prereq_indegree[edge.target] += 1

    results = []
    for node in nodes:
        indegree = prereq_indegree.get(node.id, 0)
        frequency = node.frequency or 1

        # 难度计算：入度权重 + 频次反向权重
        if indegree == 0:
            level = 1  # 入门
            label = "入门"
        elif indegree <= 2:
            level = 2  # 中级
            label = "中级"
        else:
            level = 3  # 高级
            label = "高级"

        # 频次修正：高频知识点难度降一级
        if frequency >= 3 and level > 1:
            level -= 1
            label = ["入门", "入门", "中级"][level - 1] if level > 0 else "入门"

        results.append({
            "node_id": node.id,
            "name": node.name,
            "difficulty": level,
            "label": label,
            "prerequisite_count": indegree,
            "frequency": frequency,
        })

    return sorted(results, key=lambda x: x["difficulty"])


def recommend_learning_path(
    nodes: list[KnowledgeNode],
    edges: list[KnowledgeEdge],
    target_node_name: str | None = None,
) -> dict[str, Any]:
    """基于 prerequisite 关系推荐学习路径。

    如果指定了 target_node_name，返回到达该知识点的前置路径。
    否则返回整体学习路径（从入门到高级的拓扑排序）。
    """
    # 构建 prerequisite 图
    graph: dict[str, list[str]] = defaultdict(list)  # node_id -> [prerequisite_ids]
    name_to_id: dict[str, str] = {}
    id_to_node: dict[str, KnowledgeNode] = {}

    for node in nodes:
        name_to_id[node.name] = node.id
        id_to_node[node.id] = node

    for edge in edges:
        if edge.relation_type == "prerequisite":
            graph[edge.target].append(edge.source)

    def get_prerequisites(node_id: str, visited: set[str] | None = None) -> list[str]:
        """递归获取所有前置知识点"""
        if visited is None:
            visited = set()
        if node_id in visited:
            return []
        visited.add(node_id)
        prereqs = []
        for prereq_id in graph.get(node_id, []):
            prereqs.extend(get_prerequisites(prereq_id, visited))
            prereqs.append(prereq_id)
        return prereqs

    if target_node_name and target_node_name in name_to_id:
        # 指定目标的学习路径
        target_id = name_to_id[target_node_name]
        path_ids = get_prerequisites(target_id)
        path_ids.append(target_id)
        # 去重保持顺序
        seen = set()
        unique_path = []
        for nid in path_ids:
            if nid not in seen:
                seen.add(nid)
                unique_path.append(nid)
        return {
            "target": target_node_name,
            "path": [
                {"node_id": nid, "name": id_to_node[nid].name, "step": i + 1}
                for i, nid in enumerate(unique_path)
                if nid in id_to_node
            ],
            "total_steps": len(unique_path),
        }
    else:
        # 整体学习路径（拓扑排序）
        # 找出入度为0的节点（无前置）
        all_ids = set(id_to_node.keys())
        has_prereq = set()
        for edge in edges:
            if edge.relation_type == "prerequisite":
                has_prereq.add(edge.target)

        entry_nodes = all_ids - has_prereq
        # BFS 拓扑排序
        from collections import deque
        queue = deque(entry_nodes)
        visited = set()
        path = []
        while queue:
            nid = queue.popleft()
            if nid in visited:
                continue
            visited.add(nid)
            path.append(nid)
            # 找依赖当前节点的后续节点
            for edge in edges:
                if edge.relation_type == "prerequisite" and edge.source == nid:
                    if edge.target not in visited:
                        queue.append(edge.target)

        return {
            "target": "all",
            "path": [
                {"node_id": nid, "name": id_to_node[nid].name, "step": i + 1}
                for i, nid in enumerate(path)
                if nid in id_to_node
            ],
            "total_steps": len(path),
        }
