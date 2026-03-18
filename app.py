"""FastAPI entrypoint for the custom PolyAgent web client."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.chat_service import (
    delete_temp_file,
    handle_turn,
    new_session_state,
    save_upload_to_temp,
)
from core.supervisor import build_graph

PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"


class ResetRequest(BaseModel):
    """Payload for clearing a server-side chat session."""

    session_id: str


class SessionStore:
    """Minimal in-memory session store for chat history."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            return self._data.get(session_id, new_session_state()).copy()

    def set(self, session_id: str, state: dict[str, Any]) -> None:
        with self._lock:
            self._data[session_id] = state

    def reset(self, session_id: str) -> None:
        with self._lock:
            self._data[session_id] = new_session_state()


def create_app(graph: Any | None = None) -> FastAPI:
    """Create the FastAPI application with a custom frontend."""
    app = FastAPI(title="PolyAgent Web")
    app.state.graph = graph or build_graph()
    app.state.sessions = SessionStore()

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        index_path = FRONTEND_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=500, detail="Frontend bundle is missing.")
        return FileResponse(index_path)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/reset")
    def reset(request: ResetRequest) -> dict[str, bool]:
        app.state.sessions.reset(request.session_id)
        return {"ok": True}

    @app.post("/api/chat")
    async def chat(
        session_id: str = Form(...),
        message: str = Form(""),
        uploaded_file: UploadFile | None = File(None),
    ) -> dict[str, Any]:
        session_state = app.state.sessions.get(session_id)
        temp_file_path: str | None = None
        file_name = ""

        if uploaded_file is not None and uploaded_file.filename:
            file_name = uploaded_file.filename
            file_bytes = await uploaded_file.read()
            temp_file_path = save_upload_to_temp(file_name, file_bytes)

        try:
            result = handle_turn(
                app.state.graph,
                session_state,
                user_input=message,
                file_path=temp_file_path,
                file_name=file_name,
            )
            app.state.sessions.set(session_id, result["session_state"])
            return {
                "ok": result["ok"],
                "assistant_message": result["message"],
                "assistant_html": result["message_html"],
                "status_text": result["status_text"],
                "meta": result["meta"],
            }
        finally:
            delete_temp_file(temp_file_path)

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=os.environ.get("APP_HOST", "127.0.0.1"),
        port=int(os.environ.get("APP_PORT", "8000")),
        reload=False,
    )
