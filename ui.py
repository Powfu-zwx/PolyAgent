"""Gradio frontend for PolyAgent minimal multi-turn conversation."""

from __future__ import annotations

import concurrent.futures
import html
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Generator

import docx
import gradio as gr
import pdfplumber
from langchain_core.messages import AIMessage, HumanMessage

from core.supervisor import build_graph

try:
    import requests

    _REQUEST_EXCEPTION_TYPES: tuple[type[BaseException], ...] = (
        requests.exceptions.RequestException,
    )
except Exception:  # noqa: BLE001
    _REQUEST_EXCEPTION_TYPES = ()

logger = logging.getLogger(__name__)

ChatHistory = list[dict[str, str]]
SessionState = dict[str, Any]

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?])|\n+")
_INTENT_LABELS = {
    "qa": "知识问答",
    "summary": "摘要生成",
    "writing": "公文写作",
    "guide": "办事引导",
}
_MAX_FILE_TEXT_LENGTH = 50000
_MAX_USER_INPUT_LENGTH = 10000
_INVOKE_TIMEOUT_SECONDS = 120
_READY_STATUS_TEXT = ""
_QUICK_PROMPTS: tuple[str, ...] = (
    "奖学金申请条件是什么？",
    "报销流程怎么走？一步步教我。",
    "帮我写一份请假申请，请假人张三，因感冒需请假两天。",
)

_APP_THEME = (
    gr.themes.Soft(
        primary_hue=gr.themes.colors.green,
        secondary_hue=gr.themes.colors.slate,
        neutral_hue=gr.themes.colors.gray,
        font=(
            gr.themes.GoogleFont("Manrope"),
            gr.themes.GoogleFont("Noto Sans SC"),
            "PingFang SC",
            "Microsoft YaHei",
            "sans-serif",
        ),
        font_mono=(
            gr.themes.GoogleFont("IBM Plex Mono"),
            "Consolas",
            "monospace",
        ),
    )
    .set(
        body_background_fill="transparent",
        background_fill_primary="#ffffff",
        background_fill_secondary="#ffffff",
        block_background_fill="#ffffff",
        block_border_color="rgba(15, 23, 42, 0.08)",
        block_border_width="1px",
        block_radius="24px",
        block_shadow="0 10px 30px rgba(15, 23, 42, 0.04)",
        body_text_color="#111827",
        body_text_color_subdued="#6b7280",
        color_accent="#10a37f",
        color_accent_soft="rgba(16, 163, 127, 0.10)",
        border_color_primary="rgba(15, 23, 42, 0.08)",
        input_background_fill="#ffffff",
        input_background_fill_focus="#ffffff",
        input_border_color="rgba(17, 24, 39, 0.12)",
        input_border_color_focus="rgba(16, 163, 127, 0.28)",
        input_shadow="0 8px 24px rgba(15, 23, 42, 0.04)",
        button_large_radius="999px",
        button_large_padding="14px 20px",
        button_primary_background_fill="#111827",
        button_primary_background_fill_hover="#0f172a",
        button_primary_border_color="#111827",
        button_primary_border_color_hover="#0f172a",
        button_primary_text_color="#ffffff",
        button_secondary_background_fill="#ffffff",
        button_secondary_background_fill_hover="#f9fafb",
        button_secondary_border_color="rgba(17, 24, 39, 0.08)",
        button_secondary_border_color_hover="rgba(17, 24, 39, 0.12)",
        button_secondary_text_color="#111827",
        panel_background_fill="#ffffff",
    )
)

_CUSTOM_CSS = """
:root {
    --app-bg: #ffffff;
    --surface: #ffffff;
    --surface-soft: #f9fafb;
    --line-soft: rgba(17, 24, 39, 0.08);
    --accent: #10a37f;
    --ink-strong: #111827;
    --ink-soft: #6b7280;
    --shadow-soft: 0 12px 40px rgba(15, 23, 42, 0.08);
    --radius-xl: 28px;
    --radius-lg: 24px;
}

html,
body,
body .gradio-container {
    min-height: 100%;
    background: var(--app-bg) !important;
}

body {
    color: var(--ink-strong);
}

.gradio-container {
    max-width: none !important;
    padding: 0 !important;
}

#app-shell {
    gap: 0;
    min-height: 100vh;
}

#side-rail {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: center;
    min-width: 60px !important;
    max-width: 60px !important;
    padding: 16px 0 20px !important;
    border-right: 1px solid var(--line-soft);
    background: #fcfcfc;
}

#side-rail .wrap {
    width: 100%;
}

#main-shell {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    padding: 10px 22px 18px !important;
    background: #ffffff;
}

#topbar {
    margin-bottom: 4px;
}

.topbar {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    min-height: 48px;
}

.topbar-title {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--ink-strong);
    font-size: 15px;
    font-weight: 700;
}

.topbar-title span {
    color: #9ca3af;
    font-weight: 500;
}

.topbar-pill {
    display: inline-flex;
    align-items: center;
    height: 30px;
    padding: 0 12px;
    border: 1px solid rgba(16, 163, 127, 0.16);
    border-radius: 999px;
    color: #0f7a60;
    background: rgba(16, 163, 127, 0.06);
    font-size: 12px;
    font-weight: 700;
}

#status-strip {
    margin: 0 0 8px;
    min-height: 0;
}

#status-strip p {
    margin: 0;
}

#status-strip .status-copy {
    display: inline-flex;
    align-items: center;
    min-height: 28px;
    padding: 0 10px;
    border: 1px solid rgba(17, 24, 39, 0.06);
    border-radius: 999px;
    background: #fafafa;
    color: var(--ink-soft);
    font-size: 12px;
    font-weight: 600;
}

#main-chatbot {
    flex: 1 1 auto;
    margin: 0;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

#main-chatbot .wrapper,
#main-chatbot .panel-wrap,
#main-chatbot .bubble-wrap {
    background: transparent !important;
}

#main-chatbot .bubble-wrap {
    height: calc(100vh - 240px);
    min-height: 420px;
    padding: 12px 12px 8px;
}

#main-chatbot .message-row {
    gap: 10px;
    margin-bottom: 14px;
}

#main-chatbot .message {
    max-width: min(76%, 860px);
    padding: 14px 16px !important;
    border-radius: 18px !important;
    border: 1px solid rgba(17, 24, 39, 0.06);
    box-shadow: none;
}

#main-chatbot .message.user {
    margin-left: auto;
    background: #f3f4f6;
}

#main-chatbot .message.bot {
    margin-right: auto;
    background: #ffffff;
}

#main-chatbot .message > button {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 0 !important;
    color: inherit !important;
}

#main-chatbot .message p,
#main-chatbot .message li {
    color: var(--ink-strong);
    line-height: 1.8;
}

#main-chatbot .message ul,
#main-chatbot .message ol {
    margin: 0.8em 0;
    padding-left: 1.2em;
}

#main-chatbot .message-buttons button {
    border-radius: 999px !important;
}

#main-chatbot .placeholder-container .message-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: calc(100vh - 290px);
}

#main-chatbot .placeholder-container .message.bot {
    max-width: 100%;
    border: none;
    background: transparent;
    box-shadow: none;
}

#main-chatbot .placeholder-container .message.bot > button {
    text-align: center !important;
}

#main-chatbot .placeholder-container h2,
#main-chatbot .placeholder-container h3 {
    margin: 0 0 12px;
    font-size: clamp(34px, 4vw, 54px);
    font-weight: 700;
    letter-spacing: -0.05em;
}

#main-chatbot .placeholder-container p {
    color: var(--ink-soft);
    font-size: 15px;
    line-height: 1.75;
}

#composer-shell {
    width: min(920px, calc(100vw - 160px));
    margin: 0 auto;
    padding: 14px 18px 12px !important;
    border: 1px solid rgba(17, 24, 39, 0.12);
    border-radius: 28px;
    background: var(--surface);
    box-shadow: var(--shadow-soft);
}

#user-input {
    margin: 0;
}

#user-input textarea,
#user-input .scroll-hide {
    min-height: 76px !important;
    padding: 8px 6px 6px !important;
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    font-size: 16px !important;
    line-height: 1.75 !important;
}

#user-input textarea::placeholder {
    color: #9ca3af;
}

#user-input textarea:focus {
    border: none !important;
    box-shadow: none !important;
}

#composer-toolbar {
    gap: 12px;
    align-items: stretch;
    margin-top: 8px;
}

#upload-button button,
#send-button button,
#new-chat-button button,
.prompt-btn button {
    min-height: 40px;
    border-radius: 999px !important;
    font-weight: 700 !important;
    box-shadow: none !important;
}

#upload-button button {
    padding: 0 14px !important;
    border: 1px solid rgba(17, 24, 39, 0.08) !important;
    background: #ffffff !important;
    color: var(--ink-strong) !important;
}

#feature-badge {
    display: flex;
    align-items: center;
}

#feature-badge .cap-badge {
    display: inline-flex;
    align-items: center;
    min-height: 32px;
    padding: 0 12px;
    border-radius: 999px;
    background: rgba(16, 163, 127, 0.08);
    color: #0f7a60;
    font-size: 12px;
    font-weight: 700;
}

#send-button button {
    width: 44px;
    min-width: 44px !important;
    padding: 0 !important;
}

#new-chat-button button {
    width: 36px;
    min-width: 36px !important;
    height: 36px;
    min-height: 36px;
    padding: 0 !important;
}

#prompt-row {
    width: min(920px, calc(100vw - 160px));
    gap: 10px;
    margin: 10px auto 0;
}

.prompt-btn button {
    min-height: 34px;
    padding: 0 14px !important;
    border: 1px solid rgba(17, 24, 39, 0.08) !important;
    background: #ffffff !important;
    color: var(--ink-soft) !important;
    font-size: 13px !important;
}

.sidebar-top,
.sidebar-bottom {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
}

.brand-mark {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: #111827;
    color: #ffffff;
    font-size: 14px;
    font-weight: 800;
}

.sidebar-dot {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: #e5e7eb;
}

@media (max-width: 980px) {
    #composer-shell,
    #prompt-row {
        width: min(920px, calc(100vw - 110px));
    }
}

@media (max-width: 768px) {
    .gradio-container {
        padding: 0 !important;
    }

    #side-rail {
        display: none !important;
    }

    #main-shell {
        padding: 10px 14px 16px !important;
    }

    #main-chatbot .bubble-wrap {
        height: calc(100vh - 220px);
        min-height: 360px;
    }

    #main-chatbot .placeholder-container .message-wrap {
        min-height: calc(100vh - 240px);
    }

    #composer-shell,
    #prompt-row {
        width: 100%;
    }

    #main-chatbot .message {
        max-width: 92%;
    }

    #composer-toolbar,
    #prompt-row,
    .topbar {
        flex-wrap: wrap;
    }

    #feature-badge {
        display: none;
    }
}
"""

_SIDEBAR_HTML = """
<div class="sidebar-top">
  <div class="brand-mark">P</div>
</div>
<div class="sidebar-bottom">
  <div class="sidebar-dot"></div>
</div>
"""

_TOPBAR_HTML = """
<div class="topbar">
  <div class="topbar-title">
    PolyAgent <span>Campus</span>
  </div>
  <div class="topbar-pill">校园知识库</div>
</div>
"""

_FEATURE_BADGE_HTML = """
<div class="cap-badge">问答 / 摘要 / 写作</div>
"""

_CHAT_PLACEHOLDER = """
## 有什么可以帮忙的？

校园知识问答、材料摘要、公文写作，都可以直接开始。
"""


def _new_session_state() -> SessionState:
    """Create cross-turn state stored in gr.State."""
    return {
        "messages": [],
        "history_window": [],
        "topic_changed": False,
    }


def _ensure_session_state(session_state: Any) -> SessionState:
    """Ensure session state has expected keys and value types."""
    if not isinstance(session_state, dict):
        return _new_session_state()

    messages = session_state.get("messages", [])
    history_window = session_state.get("history_window", [])
    topic_changed = bool(session_state.get("topic_changed", False))

    return {
        "messages": list(messages) if isinstance(messages, list) else [],
        "history_window": list(history_window) if isinstance(history_window, list) else [],
        "topic_changed": topic_changed,
    }


def _ensure_chat_history(chatbot: Any) -> ChatHistory:
    """Normalize chatbot history into Gradio messages format."""
    if not isinstance(chatbot, list):
        return []

    history: ChatHistory = []
    for item in chatbot:
        if not isinstance(item, dict):
            continue

        role = str(item.get("role", "assistant"))
        content = str(item.get("content", ""))
        if role not in {"user", "assistant"}:
            continue
        history.append({"role": role, "content": content})

    return history


def _resolve_file_path(file_obj: Any) -> str | None:
    """Resolve Gradio file value into a local temporary file path."""
    if file_obj is None:
        return None
    if isinstance(file_obj, str):
        return file_obj
    if isinstance(file_obj, dict):
        for key in ("path", "name"):
            value = file_obj.get(key)
            if isinstance(value, str):
                return value

    name = getattr(file_obj, "name", None)
    if isinstance(name, str):
        return name

    return None


def _format_status_text(text: str) -> str:
    """Format status text as left-aligned gray markdown html."""
    if not text:
        return ""
    escaped = html.escape(text)
    return f"<div class=\"status-copy\">{escaped}</div>"


def _ui_updates(
    processing: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build UI update payloads for textbox, file input and send button."""
    if processing:
        return (
            gr.update(value="", interactive=False),
            gr.update(value=None, interactive=False),
            gr.update(interactive=False),
        )

    return (
        gr.update(value="", interactive=True),
        gr.update(value=None, interactive=True),
        gr.update(interactive=True),
    )


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

        if len(text) > _MAX_FILE_TEXT_LENGTH:
            text = (
                text[:_MAX_FILE_TEXT_LENGTH]
                + "\n\n（文件内容较长，已截取前 50000 字符）"
            )

        return text
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to extract file text: %s", file_path, exc_info=True)
        return f"文件读取失败：{exc}"


def invoke_with_timeout(
    graph: Any,
    state: dict[str, Any],
    timeout: int = _INVOKE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Invoke LangGraph with timeout protection via worker thread."""
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


def _build_status_text(result: dict[str, Any]) -> str:
    """Build user-visible status text from completed intents and errors."""
    completed = result.get("completed_intents", [])
    if isinstance(completed, list) and completed:
        labels = [_INTENT_LABELS.get(str(intent), str(intent)) for intent in completed]
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
            label = _INTENT_LABELS.get(agent, agent)
            error_tips.append(f"{label}服务暂时不可用")

        if error_tips:
            unique_tips = list(dict.fromkeys(error_tips))
            status = f"{status}（{'；'.join(unique_tips)}）"

    return status


def _build_invoke_state(
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


def _split_for_streaming(text: str) -> list[str]:
    """Split output into sentence-like chunks for simulated streaming."""
    content = str(text or "").strip()
    if not content:
        return ["（无输出）"]

    parts = [segment.strip() for segment in _SENTENCE_SPLIT_RE.split(content)]
    chunks = [segment for segment in parts if segment]
    return chunks or [content]


def _chat_handler(
    user_input: str,
    file_input: Any,
    chatbot: Any,
    session_state: Any,
    graph: Any,
) -> Generator[Any, None, None]:
    """Handle one user turn with graph.invoke and simulated streaming output."""
    safe_session = _ensure_session_state(session_state)
    safe_chat = _ensure_chat_history(chatbot)

    original_text = str(user_input or "").strip()
    text = original_text
    text_truncated = False

    if len(text) > _MAX_USER_INPUT_LENGTH:
        text = text[:_MAX_USER_INPUT_LENGTH]
        text_truncated = True

    file_path = _resolve_file_path(file_input)
    file_name = Path(file_path).name if file_path else ""

    if not text and not file_path:
        safe_chat.append({"role": "assistant", "content": "请输入内容后再发送。"})
        text_update, file_update, send_update = _ui_updates(processing=False)
        yield safe_chat, text_update, file_update, safe_session, "", send_update
        return

    effective_input = text if text else "请对以下文件内容进行摘要总结"
    display_input = effective_input
    if file_name:
        display_input = f"{effective_input}\n[已上传文件: {file_name}]"

    logger.info(
        "New turn started: user_input_len=%d, history_window_len=%d",
        len(effective_input),
        len(safe_session["history_window"]),
    )

    safe_chat.append({"role": "user", "content": display_input})
    if text_truncated:
        safe_chat.append(
            {
                "role": "assistant",
                "content": "（输入文本较长，已截取前 10000 字符）",
            }
        )

    safe_chat.append({"role": "assistant", "content": "正在思考..."})
    text_update, file_update, send_update = _ui_updates(processing=True)
    yield (
        safe_chat,
        text_update,
        file_update,
        safe_session,
        _format_status_text("正在分析您的需求..."),
        send_update,
    )

    file_context = ""
    if file_path:
        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            file_size = -1

        logger.info(
            "File uploaded: name=%s, size=%s bytes",
            file_name,
            file_size if file_size >= 0 else "unknown",
        )

        extracted_text = extract_file_text(file_path)
        extracted_clean = extracted_text.strip()

        file_warning = ""
        if not extracted_clean:
            file_warning = "上传的文件内容为空，请检查文件后重试。"
        elif extracted_text.startswith("不支持的文件格式"):
            file_warning = extracted_text
        elif extracted_text.startswith("文件读取失败"):
            file_warning = extracted_text
        else:
            file_context = extracted_text

        if file_warning:
            safe_chat[-1] = {"role": "assistant", "content": f"[系统提示] {file_warning}"}
            if text:
                safe_chat.append({"role": "assistant", "content": "正在思考..."})
                text_update, file_update, send_update = _ui_updates(processing=True)
                yield (
                    safe_chat,
                    text_update,
                    file_update,
                    safe_session,
                    _format_status_text("正在分析您的需求..."),
                    send_update,
                )
            else:
                text_update, file_update, send_update = _ui_updates(processing=False)
                yield (
                    safe_chat,
                    text_update,
                    file_update,
                    safe_session,
                    "",
                    send_update,
                )
                return

    try:
        invoke_state = _build_invoke_state(effective_input, safe_session, context=file_context)
        result = invoke_with_timeout(graph, invoke_state, timeout=_INVOKE_TIMEOUT_SECONDS)

        final_output = str(result.get("final_output", "") or "").strip()
        if not final_output:
            final_output = "已完成处理，但未生成可展示内容。"

        # Keep only cross-turn fields outside graph invoke.
        next_session: SessionState = {
            "messages": list(safe_session["messages"]),
            "history_window": list(safe_session["history_window"]),
            "topic_changed": bool(result.get("topic_changed", False)),
        }
        next_session["messages"].append(HumanMessage(content=effective_input))
        next_session["messages"].append(AIMessage(content=final_output))
        next_session["history_window"].append(HumanMessage(content=effective_input))
        next_session["history_window"].append(AIMessage(content=final_output))

        logger.info(
            "Turn finished: completed_intents=%s, topic_changed=%s, output_len=%d",
            result.get("completed_intents", []),
            next_session["topic_changed"],
            len(final_output),
        )

        status_text = _format_status_text(_build_status_text(result))
        streamed_output = ""
        chunks = _split_for_streaming(final_output)

        for idx, chunk in enumerate(chunks):
            streamed_output += chunk
            safe_chat[-1] = {"role": "assistant", "content": streamed_output}
            is_last = idx == len(chunks) - 1
            text_update, file_update, send_update = _ui_updates(processing=not is_last)
            yield (
                safe_chat,
                text_update,
                file_update,
                next_session,
                status_text,
                send_update,
            )
            if not is_last:
                time.sleep(0.05)

    except Exception as exc:  # noqa: BLE001
        logger.error("chat_handler failed: %s", exc, exc_info=True)

        if isinstance(exc, TimeoutError):
            message = "请求处理超时，请稍后重试。可能是网络不稳定或请求内容过于复杂。"
            status_text = _format_status_text("处理超时")
        elif isinstance(exc, ConnectionError) or (
            _REQUEST_EXCEPTION_TYPES and isinstance(exc, _REQUEST_EXCEPTION_TYPES)
        ):
            message = "网络连接异常，请检查网络后重试。"
            status_text = _format_status_text("网络连接异常")
        else:
            message = "系统处理异常，请稍后重试。如持续出现，请联系管理员。"
            status_text = _format_status_text("处理失败")

        safe_chat[-1] = {"role": "assistant", "content": f"[系统提示] {message}"}
        text_update, file_update, send_update = _ui_updates(processing=False)
        # Keep previous session state unchanged on invoke failure.
        yield safe_chat, text_update, file_update, safe_session, status_text, send_update


def _reset_conversation() -> tuple[Any, Any, Any, Any, Any, Any]:
    """Clear chat history and reset cross-turn state."""
    logger.info("Conversation reset by user.")
    text_update, file_update, send_update = _ui_updates(processing=False)
    return (
        [],
        text_update,
        file_update,
        _new_session_state(),
        _format_status_text(_READY_STATUS_TEXT),
        send_update,
    )


def _prefill_prompt(prompt: str) -> str:
    """Fill the input box with a suggested prompt."""
    return prompt


def create_demo(graph: Any) -> gr.Blocks:
    """Build Gradio Blocks UI and bind callbacks."""
    with gr.Blocks(
        title="PolyAgent | Conversational Workspace",
        theme=_APP_THEME,
        css=_CUSTOM_CSS,
        fill_height=True,
        fill_width=True,
    ) as demo:
        with gr.Row(elem_id="app-shell", equal_height=False):
            with gr.Column(scale=1, min_width=60, elem_id="side-rail"):
                gr.HTML(_SIDEBAR_HTML)
                clear_btn = gr.Button(
                    "+",
                    variant="secondary",
                    elem_id="new-chat-button",
                )

            with gr.Column(scale=30, min_width=420, elem_id="main-shell"):
                gr.HTML(_TOPBAR_HTML, elem_id="topbar")

                status_markdown = gr.Markdown(
                    value=_format_status_text(_READY_STATUS_TEXT),
                    elem_id="status-strip",
                )

                chatbot = gr.Chatbot(
                    label="对话历史",
                    show_label=False,
                    container=False,
                    elem_id="main-chatbot",
                    height="calc(100vh - 240px)",
                    type="messages",
                    show_copy_button=True,
                    show_copy_all_button=True,
                    bubble_full_width=False,
                    layout="bubble",
                    placeholder=_CHAT_PLACEHOLDER,
                )

                with gr.Column(elem_id="composer-shell"):
                    user_input = gr.Textbox(
                        placeholder="有问题，尽管问",
                        lines=3,
                        max_lines=8,
                        show_label=False,
                        container=False,
                        autofocus=True,
                        elem_id="user-input",
                    )

                    with gr.Row(elem_id="composer-toolbar"):
                        file_input = gr.UploadButton(
                            "上传文件",
                            variant="secondary",
                            size="sm",
                            file_count="single",
                            type="filepath",
                            file_types=[".txt", ".md", ".pdf", ".docx"],
                            elem_id="upload-button",
                        )
                        gr.HTML(_FEATURE_BADGE_HTML, elem_id="feature-badge")
                        send_btn = gr.Button(
                            "↑",
                            variant="primary",
                            elem_id="send-button",
                        )

                prompt_buttons: list[tuple[str, gr.Button]] = []
                with gr.Row(elem_id="prompt-row"):
                    for prompt in _QUICK_PROMPTS:
                        button = gr.Button(
                            prompt,
                            variant="secondary",
                            elem_classes="prompt-btn",
                        )
                        prompt_buttons.append((prompt, button))

        session_state = gr.State(_new_session_state())

        def on_submit(
            text: str,
            uploaded_file: Any,
            chat: Any,
            state: Any,
        ) -> Generator[Any, None, None]:
            """Wrapper callback with bound graph instance."""
            yield from _chat_handler(text, uploaded_file, chat, state, graph)

        send_btn.click(
            on_submit,
            inputs=[user_input, file_input, chatbot, session_state],
            outputs=[
                chatbot,
                user_input,
                file_input,
                session_state,
                status_markdown,
                send_btn,
            ],
            api_name=False,
            show_api=False,
        )
        user_input.submit(
            on_submit,
            inputs=[user_input, file_input, chatbot, session_state],
            outputs=[
                chatbot,
                user_input,
                file_input,
                session_state,
                status_markdown,
                send_btn,
            ],
            api_name=False,
            show_api=False,
        )
        clear_btn.click(
            _reset_conversation,
            inputs=None,
            outputs=[
                chatbot,
                user_input,
                file_input,
                session_state,
                status_markdown,
                send_btn,
            ],
            api_name=False,
            show_api=False,
        )

        for prompt, button in prompt_buttons:
            button.click(
                lambda value=prompt: _prefill_prompt(value),
                inputs=None,
                outputs=user_input,
                api_name=False,
                show_progress="hidden",
                show_api=False,
            )

    return demo


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    graph = build_graph()
    demo = create_demo(graph)
    demo.queue()
    demo.launch(
        server_name=os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1"),
        server_port=int(os.environ.get("GRADIO_SERVER_PORT", "7860")),
        show_api=False,
    )
