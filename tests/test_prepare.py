"""Unit tests for prepare node behavior."""

from __future__ import annotations

from types import SimpleNamespace

from langchain_core.messages import HumanMessage

import core.prepare as prepare_module


def _patch_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        prepare_module,
        "get_settings",
        lambda: SimpleNamespace(MAX_HISTORY_WINDOW=5),
    )


def test_prepare_preserves_incoming_context(monkeypatch) -> None:
    """Keep caller-provided context for downstream agents."""
    _patch_settings(monkeypatch)
    state = {
        "context": "uploaded file extracted text",
        "history_window": [],
        "topic_changed": False,
    }

    result = prepare_module.prepare_node(state)

    assert result["context"] == "uploaded file extracted text"


def test_prepare_clears_history_on_topic_change(monkeypatch) -> None:
    """Clear history window when topic_changed is true."""
    _patch_settings(monkeypatch)
    state = {
        "context": "keep me",
        "history_window": [HumanMessage(content="old turn")],
        "topic_changed": True,
    }

    result = prepare_module.prepare_node(state)

    assert result["history_window"] == []
    assert result["context"] == "keep me"
