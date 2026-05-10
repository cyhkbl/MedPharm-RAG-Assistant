"""tests/test_integrator.py — 整合决策引擎单元测试"""

from backend.models.schemas import IntegrationDecision


def test_decision_model():
    """IntegrationDecision 应能正常创建"""
    d = IntegrationDecision(
        decision_id="test_001",
        action="merge",
        affected_nodes=["node_a", "node_b"],
        result_node="merged_node",
        reason="两个知识点描述同一概念",
        confidence=0.92,
    )
    assert d.action == "merge"
    assert len(d.affected_nodes) == 2
    assert d.confidence == 0.92


def test_decision_actions():
    """action 只允许 merge/keep/remove"""
    for action in ("merge", "keep", "remove"):
        d = IntegrationDecision(
            decision_id=f"test_{action}",
            action=action,
            affected_nodes=["n1"],
            result_node="n1",
            reason="test",
            confidence=1.0,
        )
        assert d.action == action


def test_decision_serialization():
    """决策应能序列化为 JSON 并反序列化"""
    d = IntegrationDecision(
        decision_id="test_ser",
        action="merge",
        affected_nodes=["n1", "n2"],
        result_node="merged",
        reason="test",
        confidence=0.85,
    )
    json_data = d.model_dump(mode="json")
    assert json_data["decision_id"] == "test_ser"
    assert json_data["action"] == "merge"
    assert isinstance(json_data["affected_nodes"], list)
