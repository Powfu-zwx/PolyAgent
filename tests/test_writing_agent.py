"""Pytest suite for writing agent."""

from __future__ import annotations

from agents.writing_agent import writing_agent_node


class TestWritingAgent:
    """写作 Agent 测试。"""

    def test_leave_application(self, empty_state: dict) -> None:
        """请假申请生成应满足基本语义要素。"""
        empty_state["user_input"] = "帮我写一份请假申请，我叫张三，因为家中有急事需要请假3天"
        result = writing_agent_node(empty_state)
        assert "agent_output" in result

        output = result["agent_output"]
        assert output, "agent_output 不应为空"
        assert any(keyword in output for keyword in ["请假", "假条", "申请"]), "请假申请输出应包含请假相关关键词"
        assert any(
            keyword in output for keyword in ["申请人", "日期", "时间", "事由", "审批"]
        ), "请假申请输出应包含申请要素关键词"

    def test_notice(self, empty_state: dict) -> None:
        """Notice generation."""
        empty_state["user_input"] = "帮我起草一份关于期末考试安排的通知"
        result = writing_agent_node(empty_state)
        assert "agent_output" in result
        assert len(result["agent_output"]) > 100

    def test_unknown_fallback(self, empty_state: dict) -> None:
        """Unknown type should use fallback template."""
        empty_state["user_input"] = "帮我写一段自我介绍"
        result = writing_agent_node(empty_state)
        assert "agent_output" in result
        assert len(result["agent_output"]) > 0
