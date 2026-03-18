"""Shared pytest fixtures for PolyAgent tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def empty_state() -> dict:
    """Provide an empty PolyAgentState-like dict with default values."""
    return {
        "messages": [],
        "user_input": "",
        "intents": [],
        "current_intent": "",
        "topic_changed": False,
        "agent_output": "",
        "routing_reasoning": "",
        "context": "",
        "history_window": [],
        "agent_errors": [],
        "pending_intents": [],
        "completed_intents": [],
        "final_output": "",
        "rag_context": "",
    }
