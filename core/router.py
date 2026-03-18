"""Intent router node for PolyAgent state graph."""

from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from config.settings import get_llm, get_settings
from core.state import PolyAgentState

logger = logging.getLogger(__name__)

VALID_INTENTS = {"qa", "summary", "writing", "guide"}


def _message_role(message: BaseMessage) -> str:
    """Map LangChain message type to a readable role name."""
    msg_type = getattr(message, "type", "")
    if msg_type == "human":
        return "user"
    if msg_type == "ai":
        return "assistant"
    return msg_type or "unknown"


def _format_history(history_window: list[BaseMessage]) -> str:
    """Format recent history into prompt-friendly plain text."""
    if not history_window:
        return "（无）"

    lines: list[str] = []
    for message in history_window:
        role = _message_role(message)
        content = str(getattr(message, "content", "")).strip()
        if role == "user":
            prefix = "用户"
        elif role == "assistant":
            prefix = "助手"
        else:
            prefix = role
        lines.append(f"{prefix}：{content}")
    return "\n".join(lines)


def router_node(state: PolyAgentState) -> dict:
    """Classify user intent and update routing fields in state."""
    settings = get_settings()
    user_input = state.get("user_input", "").strip()
    history_window = state.get("history_window", [])

    system_prompt = """你是 PolyAgent 系统的意图分类器。你的唯一任务是：根据用户当前输入和最近对话历史，判断用户意图并输出结构化 JSON。

你必须输出且仅输出一个 JSON 对象，不要输出任何其他内容。

## 意图类别

共 4 种意图，可多选：

1. qa — 事实性信息查询
   用户想知道某个事实、政策、规定、数据、条件、时间等。
   典型动词：是什么、有哪些、多少、什么时候、在哪里、谁负责
   注意：用户问"怎么办理 X"时，如果只是想了解流程概况，归 qa；只有用户明确要求逐步引导时才归 guide。

2. summary — 文档/内容摘要
   用户要求对一段文本、一份文件、一篇通知进行压缩总结。
   触发条件：必须存在明确的摘要对象（文档、文件、内容、通知等）。
   典型动词：总结、概括、摘要、提炼要点、归纳
   注意：如果用户只是问问题而没有指定摘要对象，不归 summary。

3. writing — 文本撰写/起草
   用户要求生成一份新文本。
   典型动词：写、拟、草拟、起草、生成、帮我写
   覆盖类型：通知、申请书、请假条、报告、邮件、策划书等

4. guide — 办事流程逐步引导
   用户明确要求按步骤引导完成某个事务。
   触发条件：用户使用了"一步步""手把手""引导我""教我怎么做""流程怎么走"等逐步引导类表述。
   注意：仅仅问"X 怎么办理"不算 guide，归 qa。

## 边界规则

- qa 是默认兜底意图。当你无法确定时，归 qa。
- intents 数组不能为空，至少包含一个意图。
- intents 数组的顺序代表推荐执行顺序（如先查询再写作）。
- 每个意图最多出现一次，不要重复。
- 闲聊、问候、无法理解的输入，统一归 ["qa"]。

## 话题转变检测

根据"最近对话历史"和"当前输入"判断话题是否发生了转变。

topic_changed = true 的条件：
- 当前输入的主题与最近对话历史中的主题明显不同
- 例如：连续讨论选课问题，突然问食堂营业时间

topic_changed = false 的条件：
- 当前输入是对之前话题的追问、补充、或相关延伸
- 第一轮对话（没有历史）时，固定为 false

注意：话题转变的判断基于语义相关性，不是关键词匹配。即使用了不同的词，只要讨论的是同一件事的不同方面，就不算转变。

## 示例

### 示例 1：单意图-qa
最近对话历史：（无）
当前输入：奖学金申请条件是什么
输出：{"intents": ["qa"], "topic_changed": false, "reasoning": "用户询问奖学金申请条件，属于事实性信息查询"}

### 示例 2：单意图-writing
最近对话历史：（无）
当前输入：帮我写一份请假申请
输出：{"intents": ["writing"], "topic_changed": false, "reasoning": "用户要求撰写请假申请，属于文本生成任务"}

### 示例 3：单意图-summary
最近对话历史：（无）
当前输入：总结一下这份文件的要点
输出：{"intents": ["summary"], "topic_changed": false, "reasoning": "用户要求对文件进行摘要，有明确的摘要对象"}

### 示例 4：单意图-guide
最近对话历史：（无）
当前输入：报销流程怎么走，一步步教我
输出：{"intents": ["guide"], "topic_changed": false, "reasoning": "用户明确要求逐步引导完成报销流程"}

### 示例 5：边界-qa 而非 guide
最近对话历史：（无）
当前输入：怎么办理离校手续
输出：{"intents": ["qa"], "topic_changed": false, "reasoning": "用户询问离校手续办理方式，是信息查询而非要求逐步引导"}

### 示例 6：复合意图
最近对话历史：（无）
当前输入：查一下奖学金政策，然后帮我写申请书
输出：{"intents": ["qa", "writing"], "topic_changed": false, "reasoning": "用户先要查询政策信息，再要撰写申请书，两个独立子任务"}

### 示例 7：话题转变
最近对话历史：
用户：大三下学期可以选哪些专业课？
助手：大三下学期可选的专业课包括...
用户：这些课的学分分别是多少？
助手：各课程学分如下...
当前输入：食堂几点开门
输出：{"intents": ["qa"], "topic_changed": true, "reasoning": "之前讨论选课相关问题，当前突然转向食堂营业时间，话题明显转变"}

### 示例 8：话题未转变
最近对话历史：
用户：大三下学期可以选哪些专业课？
助手：大三下学期可选的专业课包括...
当前输入：选课截止时间是什么时候
输出：{"intents": ["qa"], "topic_changed": false, "reasoning": "当前输入仍围绕选课话题，属于相关追问"}

## 输出要求

严格输出以下 JSON 格式，不要输出任何其他内容（不要加 markdown 代码块标记、不要加解释）：

{"intents": [...], "topic_changed": ..., "reasoning": "..."}

约束：
- intents: 字符串数组，元素只能是 "qa"/"summary"/"writing"/"guide"，至少一个，不重复
- topic_changed: 布尔值 true 或 false
- reasoning: 字符串，简要说明判断依据"""

    history_text = _format_history(history_window)
    user_prompt = (
        f"最近对话历史：\n{history_text}\n\n"
        f"当前输入：{user_input}"
    )

    llm = get_llm("primary").bind(temperature=settings.ROUTER_TEMPERATURE)
    response = llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
    )
    raw = str(getattr(response, "content", "")).strip()

    # L1: strip markdown code fences.
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    # L2: parse JSON with fallback.
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("router_node defensive layer L2 triggered: JSON parsing failed, fallback to qa")
        result = {
            "intents": ["qa"],
            "topic_changed": False,
            "reasoning": "JSON 解析失败，fallback 到 qa",
        }

    if not isinstance(result, dict):
        logger.warning("router_node defensive layer L2 triggered: parsed payload is not an object, fallback to qa")
        result = {
            "intents": ["qa"],
            "topic_changed": False,
            "reasoning": "JSON 解析结果不是对象，fallback 到 qa",
        }

    # L3: intents missing/invalid/empty -> fallback qa.
    if (
        "intents" not in result
        or not isinstance(result["intents"], list)
        or len(result["intents"]) == 0
    ):
        logger.warning("router_node defensive layer L3 triggered: intents missing/invalid/empty, fallback to qa")
        result["intents"] = ["qa"]

    # L4: filter invalid intents.
    filtered = [intent for intent in result["intents"] if intent in VALID_INTENTS]
    if not filtered:
        logger.warning("router_node defensive layer L4 triggered: no valid intents after filtering, fallback to qa")
        filtered = ["qa"]
    result["intents"] = filtered

    # L5: deduplicate while preserving order.
    seen = set()
    deduped: list[str] = []
    for intent in result["intents"]:
        if intent not in seen:
            seen.add(intent)
            deduped.append(intent)
    if len(deduped) != len(result["intents"]):
        logger.warning("router_node defensive layer L5 triggered: duplicate intents removed")
    result["intents"] = deduped

    # L6: topic_changed must be bool.
    if "topic_changed" not in result or not isinstance(result["topic_changed"], bool):
        logger.warning("router_node defensive layer L6 triggered: topic_changed invalid, fallback to false")
        result["topic_changed"] = False

    if "reasoning" not in result or not isinstance(result["reasoning"], str):
        logger.warning("router_node defensive layer FINAL triggered: reasoning invalid, fallback to empty string")
        result["reasoning"] = ""

    # 话题转变时清空上下文
    updates = {
        "intents": result["intents"],
        "current_intent": result["intents"][0],
        "topic_changed": result["topic_changed"],
        "routing_reasoning": result.get("reasoning", ""),
    }

    if result["topic_changed"]:
        updates["context"] = ""
        logger.info("Topic changed detected — context cleared")

    return updates
