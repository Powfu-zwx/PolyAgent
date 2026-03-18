"""LangGraph Supervisor multi-agent orchestration verification script."""

import json
import re
from typing import Annotated, Any, Literal

BASE_URL: str = "https://api.deepseek.com"
MODEL: str = "deepseek-chat"
DEEPSEEK_API_KEY: str = "sk-4c06530e91264ade825c3dc69337cbd7"

ROUTER_SYSTEM_PROMPT: str = (
    "你是路由器。你只做意图分类，不回答问题。"
    "必须输出严格 JSON，格式为 {\"intent\": \"qa\"} 或 {\"intent\": \"writing\"}。"
)
QA_SYSTEM_PROMPT: str = (
    "你是知识问答助手。请给出准确、简洁、结构清晰的回答，优先使用要点式表达。"
)
WRITING_SYSTEM_PROMPT: str = (
    "你是公文写作助手。请输出规范、正式、可直接使用的公文文本。"
)


def _extract_text(content: Any) -> str:
    """Normalize message content to plain text."""
    if isinstance(content, str):
        return content
    return str(content)


def _latest_user_message(messages: list[Any]) -> str:
    """Get the latest human message text from state messages."""
    for message in reversed(messages):
        if getattr(message, "type", "") == "human":
            return _extract_text(getattr(message, "content", ""))
    return ""


def _parse_intent(raw_text: str, user_text: str) -> Literal["qa", "writing"]:
    """Parse router output JSON and fallback with simple heuristics."""
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
        payload = {}
        if match:
            try:
                payload = json.loads(match.group(0))
            except json.JSONDecodeError:
                payload = {}

    intent = payload.get("intent")
    if intent in ("qa", "writing"):
        return intent

    lowered = raw_text.lower()
    if "writing" in lowered or "公文" in lowered:
        return "writing"
    if "qa" in lowered or "问答" in lowered:
        return "qa"

    if any(token in user_text for token in ("写", "申请", "公文", "请假")):
        return "writing"
    return "qa"


def run_supervisor_check() -> bool:
    """Run two routing tests to verify LangGraph Supervisor orchestration."""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI
        from langgraph.graph import END, START, StateGraph
        from langgraph.graph.message import add_messages
        from openai import (
            APIConnectionError,
            APIStatusError,
            AuthenticationError,
            OpenAIError,
            RateLimitError,
        )
        from typing_extensions import TypedDict
    except ImportError as exc:
        print(
            "导入错误：缺少依赖，请先安装 "
            "`pip install -U langchain-openai langgraph langchain-core openai`。"
        )
        print(f"详情：{exc}")
        return False

    if not DEEPSEEK_API_KEY:
        print("配置错误：请在代码中填写 DEEPSEEK_API_KEY。")
        return False

    class State(TypedDict, total=False):
        """State for router and downstream agents."""

        messages: Annotated[list, add_messages]
        intent: str
        routed_agent: str

    llm = ChatOpenAI(
        base_url=BASE_URL,
        api_key=DEEPSEEK_API_KEY,
        model=MODEL,
    )

    def router(state: State) -> State:
        """Classify user intent to qa or writing."""
        user_text = _latest_user_message(state.get("messages", []))
        router_messages = [
            SystemMessage(content=ROUTER_SYSTEM_PROMPT),
            HumanMessage(content=user_text),
        ]
        response = llm.invoke(router_messages)
        raw_text = _extract_text(response.content).strip()
        intent = _parse_intent(raw_text, user_text)
        return {"intent": intent}

    def qa_agent(state: State) -> State:
        """Answer with knowledge-qa assistant role."""
        user_text = _latest_user_message(state.get("messages", []))
        qa_messages = [
            SystemMessage(content=QA_SYSTEM_PROMPT),
            HumanMessage(content=user_text),
        ]
        response = llm.invoke(qa_messages)
        return {"messages": [response], "routed_agent": "qa_agent"}

    def writing_agent(state: State) -> State:
        """Answer with official-document writing assistant role."""
        user_text = _latest_user_message(state.get("messages", []))
        writing_messages = [
            SystemMessage(content=WRITING_SYSTEM_PROMPT),
            HumanMessage(content=user_text),
        ]
        response = llm.invoke(writing_messages)
        return {"messages": [response], "routed_agent": "writing_agent"}

    def route_by_intent(state: State) -> str:
        """Return conditional path key based on router decision."""
        intent = state.get("intent", "qa")
        return intent if intent in ("qa", "writing") else "qa"

    graph_builder = StateGraph(State)
    graph_builder.add_node("router", router)
    graph_builder.add_node("qa_agent", qa_agent)
    graph_builder.add_node("writing_agent", writing_agent)
    graph_builder.add_edge(START, "router")
    graph_builder.add_conditional_edges(
        "router",
        route_by_intent,
        {"qa": "qa_agent", "writing": "writing_agent"},
    )
    graph_builder.add_edge("qa_agent", END)
    graph_builder.add_edge("writing_agent", END)
    graph = graph_builder.compile()

    tests: list[tuple[str, str]] = [
        ("奖学金申请条件是什么？", "qa"),
        ("帮我写一份请假申请", "writing"),
    ]

    all_passed = True
    for user_input, expected_intent in tests:
        print(f"\n测试输入：{user_input}")
        try:
            result: dict[str, Any] = graph.invoke(
                {"messages": [HumanMessage(content=user_input)]}
            )
        except APIConnectionError as exc:
            print(f"网络错误：无法连接 DeepSeek API。详情：{exc}")
            return False
        except AuthenticationError as exc:
            print(f"认证错误：API Key 无效或权限不足。详情：{exc}")
            return False
        except RateLimitError as exc:
            print(f"速率限制：请求过于频繁，请稍后重试。详情：{exc}")
            return False
        except APIStatusError as exc:
            print(f"接口状态错误：HTTP {exc.status_code}。详情：{exc}")
            return False
        except OpenAIError as exc:
            print(f"OpenAI SDK 错误：{exc}")
            return False
        except Exception as exc:
            print(f"执行错误：{exc}")
            return False

        actual_intent = str(result.get("intent", ""))
        routed_agent = str(result.get("routed_agent", ""))
        messages = result.get("messages")
        reply_text = ""
        if isinstance(messages, list) and messages:
            reply_text = _extract_text(getattr(messages[-1], "content", ""))

        route_ok = actual_intent == expected_intent
        expected_agent = "qa_agent" if expected_intent == "qa" else "writing_agent"
        agent_ok = routed_agent == expected_agent
        all_passed = all_passed and route_ok and agent_ok and bool(reply_text.strip())

        print(
            "路由结果："
            f"intent={actual_intent}, "
            f"expected_intent={expected_intent}, "
            f"agent={routed_agent}"
        )
        print("Agent 回复：")
        print(reply_text)

    return all_passed


def main() -> int:
    """Program entry point."""
    success = run_supervisor_check()
    print("LangGraph Supervisor 集成验证通过" if success else "验证失败")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
