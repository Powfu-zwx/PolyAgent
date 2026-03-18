"""Reusable chat service helpers for HTTP and UI frontends."""

from __future__ import annotations

import concurrent.futures
import logging
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import docx
import pdfplumber
from langchain_core.messages import AIMessage, HumanMessage
from markdown_it import MarkdownIt

try:
    import requests

    REQUEST_EXCEPTION_TYPES: tuple[type[BaseException], ...] = (
        requests.exceptions.RequestException,
    )
except Exception:  # noqa: BLE001
    REQUEST_EXCEPTION_TYPES = ()

logger = logging.getLogger(__name__)

SessionState = dict[str, Any]
MARKDOWN = MarkdownIt(
    "commonmark",
    {
        "html": False,
        "breaks": True,
        "linkify": True,
    },
)

INTENT_LABELS = {
    "qa": "知识问答",
    "summary": "摘要生成",
    "writing": "公文写作",
    "guide": "办事引导",
}
MAX_FILE_TEXT_LENGTH = 50000
MAX_USER_INPUT_LENGTH = 10000
INVOKE_TIMEOUT_SECONDS = 120


def new_session_state() -> SessionState:
    """Create cross-turn state stored outside the graph runtime."""
    return {
        "messages": [],
        "history_window": [],
        "topic_changed": False,
    }


def ensure_session_state(session_state: Any) -> SessionState:
    """Normalize an arbitrary object into a valid session state."""
    if not isinstance(session_state, dict):
        return new_session_state()

    messages = session_state.get("messages", [])
    history_window = session_state.get("history_window", [])

    return {
        "messages": list(messages) if isinstance(messages, list) else [],
        "history_window": list(history_window) if isinstance(history_window, list) else [],
        "topic_changed": bool(session_state.get("topic_changed", False)),
    }


def extract_file_text(file_path: str) -> str:
    """Extract text from txt/md/pdf/docx with robust fallback handling."""
    ext = Path(file_path).suffix.lower()
    supported = ".txt、.md、.pdf、.docx"

    if ext not in {".txt", ".md", ".pdf", ".docx"}:
        return f"不支持的文件格式（{ext or '未知'}），目前支持 {supported}"

    try:
        text = ""
        if ext in {".txt", ".md"}:
            try:
                text = Path(file_path).read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = Path(file_path).read_text(encoding="gbk", errors="ignore")
        elif ext == ".pdf":
            pages: list[str] = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    pages.append(page.extract_text() or "")
            text = "\n".join(pages)
        elif ext == ".docx":
            document = docx.Document(file_path)
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)

        text = text.strip()
        if len(text) > MAX_FILE_TEXT_LENGTH:
            text = text[:MAX_FILE_TEXT_LENGTH] + "\n\n（文件内容较长，已截取前 50000 字符）"
        return text
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to extract file text: %s", file_path, exc_info=True)
        return f"文件读取失败：{exc}"


def save_upload_to_temp(filename: str, content: bytes) -> str:
    """Persist uploaded bytes to a temporary file and return its path."""
    suffix = Path(filename or "").suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(content)
        return temp_file.name


def delete_temp_file(path: str | None) -> None:
    """Best-effort cleanup for temporary uploaded files."""
    if not path:
        return
    try:
        os.unlink(path)
    except OSError:
        logger.warning("Failed to delete temp file: %s", path)


def invoke_with_timeout(
    graph: Any,
    state: dict[str, Any],
    timeout: int = INVOKE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Invoke LangGraph with timeout protection via a worker thread."""
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(graph.invoke, state)
    try:
        result = future.result(timeout=timeout)
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        raise TimeoutError(f"graph.invoke exceeded {timeout}s timeout") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if not isinstance(result, dict):
        raise RuntimeError("graph.invoke returned an invalid response")
    return result


def build_status_text(result: dict[str, Any]) -> str:
    """Build user-visible status text from completed intents and errors."""
    completed = result.get("completed_intents", [])
    if isinstance(completed, list) and completed:
        labels = [INTENT_LABELS.get(str(intent), str(intent)) for intent in completed]
        status = f"本轮处理：{' -> '.join(labels)}"
    else:
        status = "本轮处理：未识别到有效处理意图"

    errors = result.get("agent_errors", [])
    if isinstance(errors, list) and errors:
        error_tips: list[str] = []
        for item in errors:
            if not isinstance(item, dict):
                continue
            agent = str(item.get("agent", "")).strip()
            if not agent:
                continue
            label = INTENT_LABELS.get(agent, agent)
            error_tips.append(f"{label}服务暂时不可用")

        if error_tips:
            unique_tips = list(dict.fromkeys(error_tips))
            status = f"{status}（{'；'.join(unique_tips)}）"

    return status


def render_markdown(text: str) -> str:
    """Render assistant markdown into safe HTML."""
    content = str(text or "").strip()
    if not content:
        return "<p></p>"
    return MARKDOWN.render(content)


def build_invoke_state(
    user_input: str,
    session_state: SessionState,
    context: str = "",
) -> dict[str, Any]:
    """Build one-turn invoke payload with full PolyAgentState defaults."""
    return {
        "messages": list(session_state["messages"]),
        "user_input": user_input,
        "intents": [],
        "current_intent": "",
        "topic_changed": bool(session_state.get("topic_changed", False)),
        "agent_output": "",
        "routing_reasoning": "",
        "context": context,
        "history_window": list(session_state["history_window"]),
        "pending_intents": [],
        "completed_intents": [],
        "final_output": "",
        "rag_context": "",
        "agent_errors": [],
    }


def handle_turn(
    graph: Any,
    session_state: Any,
    user_input: str = "",
    file_path: str | None = None,
    file_name: str = "",
) -> dict[str, Any]:
    """Handle one end-to-end chat turn and return a frontend-friendly payload."""
    safe_session = ensure_session_state(session_state)

    original_text = str(user_input or "").strip()
    text = original_text
    if len(text) > MAX_USER_INPUT_LENGTH:
        text = text[:MAX_USER_INPUT_LENGTH]

    if not text and not file_path:
        return {
            "ok": False,
            "message": "请输入内容后再发送。",
            "status_text": "",
            "session_state": safe_session,
            "meta": {
                "completed_intents": [],
                "completed_intent_labels": [],
                "routing_reasoning": "",
                "topic_changed": False,
                "file_name": "",
                "text_truncated": False,
            },
        }

    effective_input = text if text else "请对以下文件内容进行摘要总结"
    text_truncated = bool(original_text and len(original_text) > MAX_USER_INPUT_LENGTH)
    file_context = ""

    if file_path:
        extracted_text = extract_file_text(file_path)
        extracted_clean = extracted_text.strip()
        if not extracted_clean:
            return {
                "ok": False,
                "message": "上传的文件内容为空，请检查文件后重试。",
                "status_text": "",
                "session_state": safe_session,
                "meta": {
                    "completed_intents": [],
                    "completed_intent_labels": [],
                    "routing_reasoning": "",
                    "topic_changed": False,
                    "file_name": file_name,
                    "text_truncated": text_truncated,
                },
            }
        if extracted_text.startswith("不支持的文件格式") or extracted_text.startswith("文件读取失败"):
            return {
                "ok": False,
                "message": extracted_text,
                "status_text": "",
                "session_state": safe_session,
                "meta": {
                    "completed_intents": [],
                    "completed_intent_labels": [],
                    "routing_reasoning": "",
                    "topic_changed": False,
                    "file_name": file_name,
                    "text_truncated": text_truncated,
                },
            }
        file_context = extracted_text

    try:
        invoke_state = build_invoke_state(effective_input, safe_session, context=file_context)
        result = invoke_with_timeout(graph, invoke_state, timeout=INVOKE_TIMEOUT_SECONDS)

        final_output = str(result.get("final_output", "") or "").strip()
        if not final_output:
            final_output = "已完成处理，但未生成可展示内容。"

        next_session = {
            "messages": list(safe_session["messages"]),
            "history_window": list(safe_session["history_window"]),
            "topic_changed": bool(result.get("topic_changed", False)),
        }
        next_session["messages"].append(HumanMessage(content=effective_input))
        next_session["messages"].append(AIMessage(content=final_output))
        next_session["history_window"].append(HumanMessage(content=effective_input))
        next_session["history_window"].append(AIMessage(content=final_output))

        completed_intents = list(result.get("completed_intents", []))
        return {
            "ok": True,
            "message": final_output,
            "message_html": render_markdown(final_output),
            "status_text": build_status_text(result),
            "session_state": next_session,
            "meta": {
                "completed_intents": completed_intents,
                "completed_intent_labels": [
                    INTENT_LABELS.get(str(intent), str(intent)) for intent in completed_intents
                ],
                "routing_reasoning": str(result.get("routing_reasoning", "") or "").strip(),
                "topic_changed": bool(result.get("topic_changed", False)),
                "file_name": file_name,
                "text_truncated": text_truncated,
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("handle_turn failed: %s", exc, exc_info=True)
        if isinstance(exc, TimeoutError):
            message = "请求处理超时，请稍后重试。可能是网络不稳定或请求内容过于复杂。"
            status_text = "处理超时"
        elif isinstance(exc, ConnectionError) or (
            REQUEST_EXCEPTION_TYPES and isinstance(exc, REQUEST_EXCEPTION_TYPES)
        ):
            message = "网络连接异常，请检查网络后重试。"
            status_text = "网络连接异常"
        else:
            message = "系统处理异常，请稍后重试。如持续出现，请联系管理员。"
            status_text = "处理失败"

        return {
            "ok": False,
            "message": message,
            "message_html": render_markdown(message),
            "status_text": status_text,
            "session_state": safe_session,
            "meta": {
                "completed_intents": [],
                "completed_intent_labels": [],
                "routing_reasoning": "",
                "topic_changed": False,
                "file_name": file_name,
                "text_truncated": text_truncated,
            },
        }


__all__ = [
    "INTENT_LABELS",
    "INVOKE_TIMEOUT_SECONDS",
    "REQUEST_EXCEPTION_TYPES",
    "build_invoke_state",
    "build_status_text",
    "delete_temp_file",
    "ensure_session_state",
    "extract_file_text",
    "handle_turn",
    "invoke_with_timeout",
    "new_session_state",
    "render_markdown",
    "save_upload_to_temp",
]
