"""Pytest suite for summary agent."""

from __future__ import annotations

from agents.summary_agent import STUFF_THRESHOLD, summary_agent_node


class TestSummaryAgent:
    def test_stuff_strategy(self, empty_state: dict) -> None:
        """Short text should trigger Stuff strategy."""
        short_text = "关于开展2026年春季学期学生资助工作的通知。" * 10
        empty_state["user_input"] = "请总结以下内容"
        empty_state["context"] = short_text
        assert len(short_text) <= STUFF_THRESHOLD
        result = summary_agent_node(empty_state)
        assert "agent_output" in result
        assert len(result["agent_output"]) > 0

    def test_map_reduce_strategy(self, empty_state: dict) -> None:
        """Long text should trigger Map-Reduce strategy."""
        long_text = "这是一段关于高等教育改革的政策文件内容。" * 500
        empty_state["user_input"] = "请总结以下内容"
        empty_state["context"] = long_text
        assert len(long_text) > STUFF_THRESHOLD
        result = summary_agent_node(empty_state)
        assert "agent_output" in result
        assert len(result["agent_output"]) > 0

    def test_empty_input_defense(self, empty_state: dict) -> None:
        """Empty content should return defensive prompt."""
        empty_state["user_input"] = "帮我总结一下"
        empty_state["context"] = ""
        result = summary_agent_node(empty_state)
        assert "agent_output" in result
        assert len(result["agent_output"]) > 0

