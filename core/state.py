"""State schema for PolyAgent graph execution.

Field purposes:
- ``messages``: Full conversation history used across all graph nodes.
- ``user_input``: The latest raw user query to process.
- ``intents``: Router-detected intent list (``qa``/``summary``/``writing``/``guide``).
- ``current_intent``: The specific intent currently being handled by a node.
- ``topic_changed``: Whether the latest turn indicates a topic shift.
- ``agent_output``: Current agent's generated output text.
- ``routing_reasoning``: Router explanation of why an intent was chosen.
- ``context``: Extra context passed into agents (for example prior agent output).
- ``rag_context``: RAG-retrieved snippets for QA/Guide agents (default ``""``).
- ``history_window``: Sliding window of the latest N messages for topic detection.
- ``agent_errors``: Accumulated per-agent error records for observability/debugging.
"""

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


class PolyAgentState(TypedDict):
    """Shared runtime state for router and agent nodes."""

    messages: Annotated[list[BaseMessage], operator.add]
    user_input: str
    intents: list[str]
    current_intent: str
    topic_changed: bool
    agent_output: str
    routing_reasoning: str
    context: str
    rag_context: str  # RAG snippets for QA/Guide agents; default empty string
    history_window: list[BaseMessage]
    agent_errors: Annotated[list[dict], operator.add]
    pending_intents: list[str]  # 寰呮墽琛岀殑鎰忓浘闃熷垪锛堝浠诲姟璋冨害鐢級
    completed_intents: list[str]  # 宸插畬鎴愮殑鎰忓浘鍒楄〃
    final_output: str  # 鏁村悎鍚庣殑鏈€缁堣緭鍑猴紙澶?Agent 缁撴灉鎷兼帴锛?

__all__ = ["AIMessage", "BaseMessage", "HumanMessage", "PolyAgentState"]
