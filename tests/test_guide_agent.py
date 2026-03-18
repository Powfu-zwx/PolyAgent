"""Pytest suite for guide agent."""

from __future__ import annotations

from agents.guide_agent import guide_agent_node


class TestGuideAgent:
    def test_procedure_guidance(self, empty_state: dict) -> None:
        """Procedure guidance should return a substantive output."""
        empty_state["user_input"] = "一步步教我怎么办理动物防疫条件合格证"
        result = guide_agent_node(empty_state)
        assert "agent_output" in result
        assert len(result["agent_output"]) > 100

    def test_irrelevant_procedure_fallback(self, empty_state: dict) -> None:
        """Irrelevant procedure query should still return fallback output."""
        empty_state["user_input"] = "一步步教我怎么申请出国留学签证"
        result = guide_agent_node(empty_state)
        assert "agent_output" in result
        assert len(result["agent_output"]) > 0

