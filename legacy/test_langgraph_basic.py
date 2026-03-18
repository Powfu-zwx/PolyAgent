"""Minimal LangGraph StateGraph example (no LLM calls)."""

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    """Graph state."""

    messages: Annotated[list[str], operator.add]
    current_intent: str


def node_a(state: State) -> State:
    """Append one message and set the intent."""
    return {
        "messages": ["node_a: set intent to qa"],
        "current_intent": "qa",
    }


def node_b(state: State) -> State:
    """Read current intent and append a confirmation message."""
    intent = state["current_intent"]
    return {"messages": [f"node_b: confirmed current_intent={intent}"]}


def main() -> int:
    graph_builder = StateGraph(State)
    graph_builder.add_node("node_a", node_a)
    graph_builder.add_node("node_b", node_b)

    graph_builder.add_edge(START, "node_a")
    graph_builder.add_edge("node_a", "node_b")
    graph_builder.add_edge("node_b", END)

    graph = graph_builder.compile()

    final_state = graph.invoke({"messages": [], "current_intent": ""})
    print("Final State:", final_state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
