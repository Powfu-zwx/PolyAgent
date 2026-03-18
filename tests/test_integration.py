"""End-to-end integration tests through supervisor graph."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agents.qa_agent as qa_agent_module
import agents.writing_agent as writing_agent_module
import core.supervisor as supervisor_module
from config.settings import MAX_CONTEXT_LENGTH
from core.supervisor import build_graph


def _new_state(user_input: str) -> dict:
    """构造基础状态。"""
    return {
        "messages": [],
        "user_input": user_input,
        "intents": [],
        "current_intent": "",
        "topic_changed": False,
        "agent_output": "",
        "routing_reasoning": "",
        "context": "",
        "history_window": [],
        "pending_intents": [],
        "completed_intents": [],
        "final_output": "",
        "rag_context": "",
        "agent_errors": [],
    }


@pytest.fixture
def graph():
    """构造 LangGraph 实例。"""
    return build_graph()


def simulate_conversation(graph, turns: list[str]) -> list[dict]:
    """
    模拟多轮对话，返回每轮 invoke 的结果列表。

    每轮自动处理：
    - 构造 state 并调用 graph.invoke()
    - 从结果中提取 final_output 作为 AIMessage
    - 追加 (HumanMessage, AIMessage) 到 history_window
    - 传递 topic_changed 到下一轮

    Args:
        graph: 编译后的 LangGraph 图
        turns: 每轮的用户输入文本列表

    Returns:
        每轮 invoke 返回的完整 state 列表
    """
    results = []
    history_window = []
    topic_changed = False

    for user_input in turns:
        state = {
            "messages": [],
            "user_input": user_input,
            "intents": [],
            "current_intent": "",
            "topic_changed": topic_changed,
            "agent_output": "",
            "routing_reasoning": "",
            "context": "",
            "history_window": list(history_window),
            "pending_intents": [],
            "completed_intents": [],
            "final_output": "",
            "rag_context": "",
            "agent_errors": [],
        }

        result = graph.invoke(state)
        results.append(result)

        ai_response = result.get("final_output", "")
        history_window.append(HumanMessage(content=user_input))
        history_window.append(AIMessage(content=ai_response))
        topic_changed = result.get("topic_changed", False)

    return results


def _make_router_stub(
    route_map: dict[str, tuple[list[str], bool]],
    history_len_recorder: list[int] | None = None,
):
    """构造可注入的 Router stub，按 user_input 返回固定 intents/topic_changed。"""

    def _router_stub(state: dict) -> dict:
        user_input = state.get("user_input", "")
        if history_len_recorder is not None:
            history_len_recorder.append(len(state.get("history_window", [])))

        intents, topic_changed = route_map.get(user_input, (["qa"], False))
        updates = {
            "intents": intents,
            "current_intent": intents[0],
            "topic_changed": topic_changed,
            "routing_reasoning": "router stub",
        }
        if topic_changed:
            # 与真实 router 行为保持一致：话题转变时冗余清空 context。
            updates["context"] = ""
        return updates

    return _router_stub


def _llm_raise(exc_msg: str = "模拟API故障") -> Mock:
    """返回一个 invoke 抛异常的 LLM mock。"""
    llm = Mock()
    llm.invoke.side_effect = Exception(exc_msg)
    return llm


def _llm_success(text: str) -> Mock:
    """返回一个 invoke 恒定成功的 LLM mock。"""
    llm = Mock()
    llm.invoke.return_value = Mock(content=text)
    return llm


# ============================================================
# 原有集成测试（保留）
# ============================================================


@pytest.mark.slow
class TestIntegration:
    """原有端到端用例（真实 LLM）。"""

    def test_single_intent_qa(self, graph) -> None:
        """单意图 QA 端到端。"""
        result = graph.invoke(_new_state("报销流程是怎样的？"))
        assert result["final_output"] != ""
        assert "qa" in result["completed_intents"]

    def test_single_intent_writing(self, graph) -> None:
        """单意图写作端到端。"""
        result = graph.invoke(_new_state("帮我写一份请假申请"))
        assert result["final_output"] != ""
        assert "writing" in result["completed_intents"]

    def test_single_intent_summary(self, graph) -> None:
        """单意图摘要端到端。"""
        result = graph.invoke(_new_state("请总结以下内容：本周教务处发布了课程调整通知，周五课程改为线上。"))
        assert result["final_output"] != ""
        assert "summary" in result["completed_intents"]

    def test_single_intent_guide(self, graph) -> None:
        """单意图引导端到端。"""
        result = graph.invoke(_new_state("报销流程怎么走，一步步教我"))
        assert result["final_output"] != ""
        assert "guide" in result["completed_intents"]

    def test_multi_intent_qa_writing(self, graph) -> None:
        """复合意图 qa + writing 端到端。"""
        result = graph.invoke(_new_state("查一下奖学金政策，然后帮我写申请书"))
        assert result["final_output"] != ""
        assert "qa" in result["completed_intents"]
        assert "writing" in result["completed_intents"]
        assert "查询结果" in result["final_output"]
        assert "写作结果" in result["final_output"]


# ============================================================
# A 类：复合意图组合扩展
# ============================================================


@pytest.mark.slow
class TestCompositeIntents:
    """复合意图组合的端到端测试。"""

    def test_qa_then_summary(self, monkeypatch) -> None:
        """A1: qa + summary，qa 输出作为 summary 的 context。"""
        user_input = "帮我查一下报销制度的规定，然后总结要点"
        route_map = {user_input: (["qa", "summary"], False)}

        monkeypatch.setattr(supervisor_module, "router_node", _make_router_stub(route_map))
        patched_graph = supervisor_module.build_graph()

        result = patched_graph.invoke(_new_state(user_input))
        assert result["completed_intents"] == ["qa", "summary"]
        assert result["final_output"]
        assert result["final_output"].count("根据您的需求") == 1
        assert "【查询结果】" in result["final_output"]
        assert "【摘要结果】" in result["final_output"]
        assert result["agent_errors"] == []

    def test_qa_then_guide(self, monkeypatch) -> None:
        """A2: qa + guide，qa 输出作为 guide 的 context。"""
        user_input = "奖学金有哪些类型？然后一步步教我怎么申请"
        route_map = {user_input: (["qa", "guide"], False)}

        monkeypatch.setattr(supervisor_module, "router_node", _make_router_stub(route_map))
        patched_graph = supervisor_module.build_graph()

        result = patched_graph.invoke(_new_state(user_input))
        assert result["completed_intents"] == ["qa", "guide"]
        assert result["final_output"]
        assert result["final_output"].count("根据您的需求") == 1
        assert "【查询结果】" in result["final_output"]
        assert "【引导结果】" in result["final_output"]
        assert result["agent_errors"] == []

    def test_summary_then_writing(self, monkeypatch) -> None:
        """A3: summary + writing，summary 输出作为 writing 的 context。"""
        sample_text = (
            "请总结以下会议纪要并据此写通知："
            "今天上午学院召开教学工作例会，明确下周开始推进课程过程性考核改革。"
            "会议要求各教研室在本周五前提交课程评价方案，重点补充课堂参与、阶段测验和作业反馈机制。"
            "教务办公室将于周三发布统一模板，并在周四组织线上答疑。"
            "各任课教师需在系统中完成课程目标与考核项映射，确保数据可追溯。"
            "学院强调改革期间要同步做好学生沟通，避免因信息不对称影响学习节奏。"
            "请各单位按时落实并反馈执行进度。"
        )
        route_map = {sample_text: (["summary", "writing"], False)}

        monkeypatch.setattr(supervisor_module, "router_node", _make_router_stub(route_map))
        patched_graph = supervisor_module.build_graph()

        result = patched_graph.invoke(_new_state(sample_text))
        assert result["completed_intents"] == ["summary", "writing"]
        assert result["final_output"]
        assert result["final_output"].count("根据您的需求") == 1
        assert "【摘要结果】" in result["final_output"]
        assert "【写作结果】" in result["final_output"]
        assert result["agent_errors"] == []

    def test_triple_intent_qa_summary_writing(self, monkeypatch) -> None:
        """A4: qa + summary + writing，三意图串联。"""
        user_input = "帮我查一下出差报销政策，总结要点，再写一份报销申请"
        route_map = {user_input: (["qa", "summary", "writing"], False)}

        monkeypatch.setattr(supervisor_module, "router_node", _make_router_stub(route_map))
        patched_graph = supervisor_module.build_graph()

        result = patched_graph.invoke(_new_state(user_input))
        assert result["completed_intents"] == ["qa", "summary", "writing"]
        assert result["final_output"].count("根据您的需求") == 1
        assert "【查询结果】" in result["final_output"]
        assert "【摘要结果】" in result["final_output"]
        assert "【写作结果】" in result["final_output"]
        assert result["agent_errors"] == []


# ============================================================
# B 类：容错场景
# ============================================================


class TestFaultTolerance:
    """Agent 容错机制测试。"""

    def test_single_intent_failure(self, monkeypatch) -> None:
        """B1: 单意图 Agent 失败，验证错误记录和用户提示。"""
        user_input = "请告诉我奖学金申请条件"
        route_map = {user_input: (["qa"], False)}

        monkeypatch.setattr(supervisor_module, "router_node", _make_router_stub(route_map))
        monkeypatch.setattr(qa_agent_module, "get_llm", lambda role="primary": _llm_raise())
        patched_graph = supervisor_module.build_graph()

        result = patched_graph.invoke(_new_state(user_input))
        assert len(result["agent_errors"]) == 1
        assert result["agent_errors"][0]["agent"] == "qa"
        assert result["agent_errors"][0]["error_type"]
        assert "[系统提示]" in result["final_output"]
        assert "知识问答服务暂时不可用" in result["final_output"]

    def test_composite_first_agent_failure(self, monkeypatch) -> None:
        """B2: 复合意图中首个 Agent 失败，后续 Agent 正常执行。"""
        user_input = "查一下报销政策，然后帮我写报销申请"
        route_map = {user_input: (["qa", "writing"], False)}

        monkeypatch.setattr(supervisor_module, "router_node", _make_router_stub(route_map))
        monkeypatch.setattr(qa_agent_module, "get_llm", lambda role="primary": _llm_raise())
        monkeypatch.setattr(
            writing_agent_module,
            "get_llm",
            lambda role="primary": _llm_success("MOCK_WRITING_OK"),
        )
        patched_graph = supervisor_module.build_graph()

        result = patched_graph.invoke(_new_state(user_input))
        assert result["completed_intents"] == ["qa", "writing"]
        assert len(result["agent_errors"]) == 1
        assert result["agent_errors"][0]["agent"] == "qa"
        assert "[系统提示]" in result["final_output"]
        assert "MOCK_WRITING_OK" in result["final_output"]
        assert not str(result["context"]).startswith("[系统提示]")

    def test_composite_last_agent_failure(self, monkeypatch) -> None:
        """B3: 复合意图中末个 Agent 失败，前序结果正常保留。"""
        user_input = "查一下奖学金政策，然后写申请书"
        route_map = {user_input: (["qa", "writing"], False)}

        monkeypatch.setattr(supervisor_module, "router_node", _make_router_stub(route_map))
        monkeypatch.setattr(qa_agent_module, "get_llm", lambda role="primary": _llm_success("MOCK_QA_OK"))
        monkeypatch.setattr(writing_agent_module, "get_llm", lambda role="primary": _llm_raise())
        patched_graph = supervisor_module.build_graph()

        result = patched_graph.invoke(_new_state(user_input))
        assert len(result["agent_errors"]) == 1
        assert result["agent_errors"][0]["agent"] == "writing"
        assert "MOCK_QA_OK" in result["final_output"]
        assert "[系统提示] 公文写作服务暂时不可用，请稍后重试。" in result["final_output"]


# ============================================================
# C 类：多轮对话交叉场景
# ============================================================


class TestMultiTurnConversation:
    """多轮对话与复合意图交叉场景测试。"""

    @pytest.mark.slow
    def test_multi_turn_then_composite(self, monkeypatch) -> None:
        """C1: 多轮同话题后触发复合意图。"""
        turns = [
            "奖学金有哪些类型？",
            "申请截止日期是什么时候？",
            "帮我查一下具体要求，然后写一份申请书",
        ]
        route_map = {
            turns[0]: (["qa"], False),
            turns[1]: (["qa"], False),
            turns[2]: (["qa", "writing"], False),
        }

        monkeypatch.setattr(supervisor_module, "router_node", _make_router_stub(route_map))
        patched_graph = supervisor_module.build_graph()

        results = simulate_conversation(patched_graph, turns)
        round3 = results[2]
        assert round3["completed_intents"] == ["qa", "writing"]
        assert round3["topic_changed"] is False
        assert "根据您的需求" in round3["final_output"]
        assert round3["agent_errors"] == []

    @pytest.mark.slow
    def test_topic_change_then_composite(self, monkeypatch) -> None:
        """C2: 话题转变后触发复合意图。"""
        turns = [
            "选课系统什么时候开放？",
            "大三下有哪些必修课？",
            "帮我查一下报销政策，然后写报销申请",
        ]
        route_map = {
            turns[0]: (["qa"], False),
            turns[1]: (["qa"], False),
            turns[2]: (["qa", "writing"], True),
        }

        monkeypatch.setattr(supervisor_module, "router_node", _make_router_stub(route_map))
        patched_graph = supervisor_module.build_graph()

        results = simulate_conversation(patched_graph, turns)
        round3 = results[2]
        assert round3["topic_changed"] is True
        assert round3["completed_intents"] == ["qa", "writing"]
        assert round3["final_output"]
        assert round3["agent_errors"] == []

    def test_runtime_state_isolation(self, monkeypatch) -> None:
        """C3: 验证回合临时字段不泄漏到下一轮。"""
        turns = [
            "查一下报销政策，然后帮我写申请",
            "食堂几点开门？",
        ]
        route_map = {
            turns[0]: (["qa", "writing"], False),
            turns[1]: (["qa"], False),
        }

        def qa_stub(state: dict) -> dict:
            if "食堂" in state.get("user_input", ""):
                return {"agent_output": "ROUND2_QA"}
            return {"agent_output": "ROUND1_QA"}

        def writing_stub(state: dict) -> dict:
            return {"agent_output": "ROUND1_WRITING"}

        monkeypatch.setattr(supervisor_module, "router_node", _make_router_stub(route_map))
        monkeypatch.setattr(supervisor_module, "qa_agent_node", qa_stub)
        monkeypatch.setattr(supervisor_module, "writing_agent_node", writing_stub)
        patched_graph = supervisor_module.build_graph()

        results = simulate_conversation(patched_graph, turns)
        round2 = results[1]
        assert round2["pending_intents"] == []
        assert round2["completed_intents"] == ["qa"]
        assert round2["agent_errors"] == []
        assert "ROUND1_QA" not in round2["final_output"]
        assert "ROUND1_WRITING" not in round2["final_output"]


# ============================================================
# D 类：格式与压缩验证
# ============================================================


class TestOutputFormat:
    """final_output 格式和 context 压缩测试。"""

    def test_single_intent_no_label(self, monkeypatch) -> None:
        """D1: 单意图输出不含标签。"""
        user_input = "单意图测试"
        route_map = {user_input: (["qa"], False)}

        def qa_stub(state: dict) -> dict:
            return {"agent_output": "SINGLE_QA_OK"}

        monkeypatch.setattr(supervisor_module, "router_node", _make_router_stub(route_map))
        monkeypatch.setattr(supervisor_module, "qa_agent_node", qa_stub)
        patched_graph = supervisor_module.build_graph()

        result = patched_graph.invoke(_new_state(user_input))
        assert result["final_output"] == "SINGLE_QA_OK"
        assert "【查询结果】" not in result["final_output"]
        assert "【摘要结果】" not in result["final_output"]
        assert "【写作结果】" not in result["final_output"]
        assert "【引导结果】" not in result["final_output"]
        assert "根据您的需求" not in result["final_output"]

    def test_multi_intent_has_transition_once(self, monkeypatch) -> None:
        """D2: 多意图输出过渡句出现且仅出现一次。"""
        user_input = "多意图格式测试"
        route_map = {user_input: (["qa", "writing"], False)}

        monkeypatch.setattr(supervisor_module, "router_node", _make_router_stub(route_map))
        monkeypatch.setattr(
            supervisor_module,
            "qa_agent_node",
            lambda state: {"agent_output": "MULTI_QA_OK"},
        )
        monkeypatch.setattr(
            supervisor_module,
            "writing_agent_node",
            lambda state: {"agent_output": "MULTI_WRITING_OK"},
        )
        patched_graph = supervisor_module.build_graph()

        result = patched_graph.invoke(_new_state(user_input))
        assert result["final_output"].count("根据您的需求") == 1
        assert "【查询结果】" in result["final_output"]
        assert "【写作结果】" in result["final_output"]

    def test_context_compression_triggered(self, monkeypatch) -> None:
        """D3: 超长 Agent 输出触发 context 压缩。"""
        user_input = "压缩测试"
        route_map = {user_input: (["qa", "writing"], False)}
        long_text = "L" * (MAX_CONTEXT_LENGTH + 128)

        received_contexts: list[str] = []
        compress_mock = Mock(return_value="压缩后的摘要内容")

        def qa_stub(state: dict) -> dict:
            return {"agent_output": long_text}

        def writing_spy(state: dict) -> dict:
            received_contexts.append(str(state.get("context", "")))
            return {"agent_output": "WRITE_AFTER_COMPRESS"}

        monkeypatch.setattr(supervisor_module, "router_node", _make_router_stub(route_map))
        monkeypatch.setattr(supervisor_module, "qa_agent_node", qa_stub)
        monkeypatch.setattr(supervisor_module, "writing_agent_node", writing_spy)
        monkeypatch.setattr(supervisor_module, "_compress_context", compress_mock)
        patched_graph = supervisor_module.build_graph()

        result = patched_graph.invoke(_new_state(user_input))
        assert result["completed_intents"] == ["qa", "writing"]
        compress_mock.assert_called_once()
        called_arg = compress_mock.call_args.args[0]
        assert len(called_arg) > MAX_CONTEXT_LENGTH
        assert received_contexts == ["压缩后的摘要内容"]
