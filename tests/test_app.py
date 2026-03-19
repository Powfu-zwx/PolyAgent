"""Tests for the custom FastAPI frontend backend."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import create_app


class MockGraph:
    """Minimal graph stub for endpoint tests."""

    def invoke(self, state: dict) -> dict:
        user_input = state.get("user_input", "")
        return {
            "final_output": f"Echo: {user_input or 'file'}",
            "completed_intents": ["qa"],
            "routing_reasoning": "用户在提问，因此归为知识问答。",
            "topic_changed": False,
            "agent_errors": [],
        }


def test_index_serves_custom_frontend() -> None:
    """Root path should serve the custom HTML entrypoint."""
    app = create_app(graph=MockGraph())
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "PolyAgent Workspace" in response.text


def test_chat_endpoint_returns_assistant_payload() -> None:
    """Chat endpoint should return message text and metadata."""
    app = create_app(graph=MockGraph())
    client = TestClient(app)

    response = client.post(
        "/api/chat",
        data={"session_id": "test-session", "message": "奖学金申请条件是什么？"},
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["assistant_message"].startswith("Echo:")
    assert payload["assistant_html"].startswith("<p>")
    assert payload["meta"]["completed_intent_labels"] == ["知识问答"]
    assert "本轮处理" in payload["status_text"]


def test_reset_endpoint_clears_session_state() -> None:
    """Reset should clear the server-side session for the target id."""
    app = create_app(graph=MockGraph())
    client = TestClient(app)

    chat_response = client.post(
        "/api/chat",
        data={"session_id": "reset-session", "message": "hello"},
    )
    assert chat_response.status_code == 200
    assert len(app.state.sessions.get("reset-session")["messages"]) == 2

    reset_response = client.post("/api/reset", json={"session_id": "reset-session"})

    assert reset_response.status_code == 200
    assert reset_response.json() == {"ok": True}
    assert app.state.sessions.get("reset-session")["messages"] == []


def test_frontend_assets_exist() -> None:
    """The new frontend bundle should be present on disk."""
    assert Path("frontend/index.html").exists()
    assert Path("frontend/static/styles.css").exists()
    assert Path("frontend/static/app.js").exists()
