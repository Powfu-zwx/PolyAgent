"""Supervisor graph wiring for PolyAgent."""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from agents.guide_agent import guide_agent_node
from agents.qa_agent import qa_agent_node
from agents.summary_agent import summary_agent_node
from agents.writing_agent import writing_agent_node
from config.settings import MAX_CONTEXT_LENGTH, get_llm
from core.prepare import prepare_node
from core.router import router_node
from core.state import PolyAgentState

_INTENT_LABELS = {
    "qa": "查询结果",
    "summary": "摘要结果",
    "writing": "写作结果",
    "guide": "引导结果",
}
_MULTI_INTENT_PREFIX = "根据您的需求，以下分别为您提供相关结果：\n\n"
_CONTEXT_TRUNCATION_SUFFIX = "...(内容已截断)"

logger = logging.getLogger(__name__)


def _route_from_intent(state: PolyAgentState) -> str:
    """Route key selector based on current intent."""
    intent = state.get("current_intent", "qa")
    if intent in {"qa", "writing", "summary", "guide"}:
        return intent
    return "qa"


def dispatch_next_node(state: PolyAgentState) -> dict:
    """Pop first pending intent and mark it as current intent.

    This node does not modify history_window.
    """
    pending = list(state.get("pending_intents", []))
    if not pending:
        return {"current_intent": "", "pending_intents": []}

    next_intent = pending.pop(0)
    return {
        "current_intent": next_intent,
        "pending_intents": pending,
    }


def _compress_context(text: str) -> str:
    """将过长的 Agent 输出压缩为简洁摘要，供后续 Agent 作为上下文使用。"""
    llm = get_llm("primary")
    prompt = (
        "你是一个信息压缩助手。请将以下内容压缩为简洁的摘要，"
        "保留核心事实、关键数据和结论，去除冗余细节、来源标注和格式修饰。"
        "摘要应控制在 500 字以内，使用陈述句，不要添加你的评论。\n\n"
        f"--- 原文 ---\n{text}\n--- 原文结束 ---\n\n"
        "请直接输出压缩后的摘要："
    )
    try:
        response = llm.invoke(prompt)
        compressed = str(getattr(response, "content", "")).strip()
        if compressed:
            return compressed
        return text[:MAX_CONTEXT_LENGTH] + _CONTEXT_TRUNCATION_SUFFIX
    except Exception as e:
        logger.warning("Context 压缩失败，降级为硬截断: %s", e)
        return text[:MAX_CONTEXT_LENGTH] + _CONTEXT_TRUNCATION_SUFFIX


def aggregate_output_node(state: PolyAgentState) -> dict:
    """Aggregate current output into final_output and update context safely.

    This node does not modify history_window.
    """
    current_output = str(state.get("agent_output", "") or "")
    current_intent = state.get("current_intent", "")
    existing_final = state.get("final_output", "")
    intents = state.get("intents", [])
    completed = list(state.get("completed_intents", []))

    is_error = current_output.startswith("[系统提示]")
    is_single = len(intents) == 1

    # 错误输出不进入 context，避免污染后续 Agent 输入。
    if is_error:
        new_context = state.get("context", "")
    else:
        # 正常输出超阈值时先压缩，避免 Prompt 空间被挤占。
        if len(current_output) > MAX_CONTEXT_LENGTH:
            new_context = _compress_context(current_output)
        else:
            new_context = current_output

    label = _INTENT_LABELS.get(current_intent, current_intent or "结果")
    if is_single:
        # 单意图场景：不加标签，不加过渡句。
        new_final = current_output
    else:
        segment = f"【{label}】\n{current_output}"
        if existing_final:
            new_final = f"{existing_final}\n\n{segment}"
        else:
            new_final = f"{_MULTI_INTENT_PREFIX}{segment}"

    if current_intent:
        completed.append(current_intent)

    return {
        "final_output": new_final,
        "context": new_context,
        "completed_intents": completed,
    }


def _check_pending(state: PolyAgentState) -> str:
    """Decide whether to continue dispatching intents or finish."""
    pending = state.get("pending_intents", [])
    return "has_more" if pending else "done"


def init_task_queue_node(state: PolyAgentState) -> dict:
    """Initialize pending/completed queues from router intents."""
    intents = list(state.get("intents", []))
    return {
        "pending_intents": intents,
        "completed_intents": [],
        "final_output": "",
    }


def build_graph():
    """Build and compile the PolyAgent supervisor graph."""
    # ============================================================
    # 设计约束：history_window 在单次 graph.invoke() 期间冻结
    #
    # 复合意图（如 ["qa", "writing"]）触发时，多个 Agent 按序执行，
    # 属于"同一轮对话"。图内节点不应修改 history_window。
    # history_window 的更新（追加本轮 HumanMessage/AIMessage）
    # 由外层调用方在 invoke 返回后完成。
    # ============================================================
    graph_builder = StateGraph(PolyAgentState)

    graph_builder.add_node("prepare", prepare_node)
    graph_builder.add_node("router", router_node)
    graph_builder.add_node("init_queue", init_task_queue_node)
    graph_builder.add_node("dispatch_next", dispatch_next_node)
    graph_builder.add_node("qa_agent", qa_agent_node)
    graph_builder.add_node("writing_agent", writing_agent_node)
    graph_builder.add_node("summary_agent", summary_agent_node)
    graph_builder.add_node("guide_agent", guide_agent_node)
    graph_builder.add_node("aggregate", aggregate_output_node)

    graph_builder.add_edge(START, "prepare")
    graph_builder.add_edge("prepare", "router")
    graph_builder.add_edge("router", "init_queue")
    graph_builder.add_edge("init_queue", "dispatch_next")

    graph_builder.add_conditional_edges(
        "dispatch_next",
        _route_from_intent,
        {
            "qa": "qa_agent",
            "writing": "writing_agent",
            "summary": "summary_agent",
            "guide": "guide_agent",
        },
    )

    graph_builder.add_edge("qa_agent", "aggregate")
    graph_builder.add_edge("writing_agent", "aggregate")
    graph_builder.add_edge("summary_agent", "aggregate")
    graph_builder.add_edge("guide_agent", "aggregate")

    graph_builder.add_conditional_edges(
        "aggregate",
        _check_pending,
        {"has_more": "dispatch_next", "done": END},
    )

    return graph_builder.compile()


graph = build_graph()


def _build_initial_state(user_input: str) -> PolyAgentState:
    """Create a minimal initial state for local smoke tests."""
    return {
        "messages": [],
        "user_input": user_input,
        "intents": [],
        "current_intent": "",
        "topic_changed": False,
        "agent_output": "",
        "routing_reasoning": "",
        "context": "",
        "rag_context": "",
        "history_window": [],
        "agent_errors": [],
        "pending_intents": [],
        "completed_intents": [],
        "final_output": "",
    }


if __name__ == "__main__":
    sample_queries = [
        "报销流程是怎样的？",
        "帮我写一份请假申请。",
        "请总结这段通知内容：明天教务处停电检修，课程改为线上。",
        "一步步教我怎么办理奖学金申请。",
    ]

    for query in sample_queries:
        result = graph.invoke(_build_initial_state(query))
        print("=" * 72)
        print(f"Input: {query}")
        print(f"Intents: {result.get('intents', [])}")
        print(f"Completed: {result.get('completed_intents', [])}")
        print(f"Output preview: {str(result.get('final_output', ''))[:240]}")


__all__ = [
    "aggregate_output_node",
    "build_graph",
    "dispatch_next_node",
    "graph",
    "init_task_queue_node",
]
