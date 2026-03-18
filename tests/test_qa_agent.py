"""Pytest suite for QA agent."""

from __future__ import annotations

from agents.qa_agent import qa_agent_node


class TestQAAgent:
    def test_basic_query(self, empty_state: dict) -> None:
        """Basic policy/procedure query should return non-empty output."""
        empty_state["user_input"] = "报销流程是怎样的"
        result = qa_agent_node(empty_state)
        assert "agent_output" in result
        assert len(result["agent_output"]) > 0

    def test_irrelevant_query_honesty(self, empty_state: dict) -> None:
        """Irrelevant query should still return an explicit response."""
        empty_state["user_input"] = "量子计算的原理是什么"
        result = qa_agent_node(empty_state)
        assert "agent_output" in result
        assert len(result["agent_output"]) > 0

    def test_context_integration(self, empty_state: dict) -> None:
        """Context from previous tasks should be accepted in QA flow."""
        empty_state["user_input"] = "基于上面的信息，我符合条件吗"
        empty_state["context"] = "奖学金政策要求GPA 3.5以上"
        result = qa_agent_node(empty_state)
        assert "agent_output" in result
        assert len(result["agent_output"]) > 0

