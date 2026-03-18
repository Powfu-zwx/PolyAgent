"""Prepare node - pre-processing before intent routing."""

from __future__ import annotations

import logging

from langchain_core.messages import BaseMessage

from config.settings import get_settings
from core.state import PolyAgentState

logger = logging.getLogger(__name__)


def prepare_node(state: PolyAgentState) -> dict:
    """Prepare runtime fields and sanitize history window before router execution."""
    settings = get_settings()
    max_messages = settings.MAX_HISTORY_WINDOW * 2
    incoming_context = str(state.get("context", "") or "")

    # ============================================================
    # 阶段 1：回合生命周期重置
    # 以下字段为本轮临时数据，必须由图自身保证每轮从干净状态开始，
    # 不依赖外层调用方手动清理。
    # ============================================================
    runtime_reset = {
        "pending_intents": [],
        "completed_intents": [],
        "final_output": "",
        "agent_errors": [],
        "agent_output": "",
        "current_intent": "",
        "routing_reasoning": "",
        "rag_context": "",
    }

    # ============================================================
    # 阶段 2：话题转变处理
    # 若上一轮检测到 topic_changed=True，清空 history_window。
    # ============================================================
    window = list(state.get("history_window", []) or [])
    if state.get("topic_changed", False):
        logger.info("检测到上一轮话题转变，history_window 已清空")
        window = []

    # ============================================================
    # 阶段 3：history_window 类型校验 + 裁剪
    # 仅保留 BaseMessage，过滤非法对象后再执行窗口裁剪。
    # ============================================================
    clean_window = [msg for msg in window if isinstance(msg, BaseMessage)]
    if len(clean_window) != len(window):
        logger.warning(
            f"history_window 中发现 {len(window) - len(clean_window)} 个非法对象，已过滤"
        )

    if len(clean_window) > max_messages:
        clean_window = clean_window[-max_messages:]
        logger.info(
            "history_window trimmed to %d messages (%d rounds)",
            max_messages,
            settings.MAX_HISTORY_WINDOW,
        )

    result = {**runtime_reset}
    # Preserve caller-provided context (e.g., uploaded file text from UI).
    result["context"] = incoming_context
    result["history_window"] = clean_window
    return result
