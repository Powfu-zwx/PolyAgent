"""Regression tests for router intent classification."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.router import router_node
from core.state import PolyAgentState


def _build_state(user_input: str) -> PolyAgentState:
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
    }


@pytest.mark.parametrize(
    ("case_id", "user_input", "expected_intents"),
    [
        ("T04", "报销流程怎么走，一步步教我", ["guide"]),
        ("T05", "查一下奖学金政策，然后帮我写申请书", ["qa", "writing"]),
        ("T09", "怎么办理离校手续", ["qa"]),
        ("T10", "奖学金", ["qa"]),
        ("T11", "你好", ["qa"]),
    ],
)
def test_router_intent_regression(
    case_id: str,
    user_input: str,
    expected_intents: list[str],
) -> None:
    result = router_node(_build_state(user_input))
    assert result["intents"] == expected_intents, (
        f"{case_id} failed: input={user_input!r}, "
        f"expected={expected_intents}, actual={result['intents']}, "
        f"reasoning={result.get('routing_reasoning', '')!r}"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
