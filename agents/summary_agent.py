"""Summary agent for structured text summarization."""

from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import get_llm

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ImportError:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# 文本长度阈值（字符数）。中文约 1.5 字符/token，4K tokens ≈ 6000 字符
STUFF_THRESHOLD = 6000

# Map 阶段每段最大字符数
MAP_CHUNK_SIZE = 4000
MAP_CHUNK_OVERLAP = 200

STUFF_SYSTEM_PROMPT = """你是一位专业的文档分析师。请对用户提供的文本内容进行结构化摘要。

输出格式要求：
【核心主题】
用一句话概括文档的核心内容。

【关键要点】
提炼 3-5 个最重要的信息点，每条用简短的陈述句表达。

【重要细节】
列出文档中不可遗漏的具体数据、日期、人名、政策条款等关键细节。

【结论/建议】
如果文档包含结论性内容或行动建议，在此概括；如果没有，可省略此部分。

摘要原则：
1. 忠于原文，不添加推测性内容
2. 语言简洁准确
3. 保留关键数据和事实
"""

MAP_SYSTEM_PROMPT = """你是一位专业的文档分析师。请提取以下文本片段中的关键信息。

要求：
1. 提取该片段中最重要的事实、数据、观点
2. 保留具体的数字、日期、名称等关键细节
3. 用简洁的要点形式列出
4. 不要添加推测，仅基于文本内容
"""

REDUCE_SYSTEM_PROMPT = """你是一位专业的文档分析师。以下是从一篇长文档的各个部分中提取的关键信息。
请将这些信息整合为一份完整的结构化摘要。

输出格式要求：
【核心主题】
用一句话概括文档的核心内容。

【关键要点】
提炼 3-5 个最重要的信息点，每条用简短的陈述句表达。

【重要细节】
列出文档中不可遗漏的具体数据、日期、人名、政策条款等关键细节。

【结论/建议】
如果内容包含结论性内容或行动建议，在此概括；如果没有，可省略此部分。

摘要原则：
1. 综合所有片段的信息，去除重复
2. 确保摘要完整覆盖原文核心内容
3. 语言简洁准确
"""

_RATE_LIMIT_MARKERS = (
    "rate limit",
    "too many requests",
    "429",
    "qps",
    "限流",
)


def _to_text(response: object) -> str:
    """Convert an LLM response object to plain text."""
    return str(getattr(response, "content", "")).strip()


def _invoke_with_retry(llm: Any, messages: list[SystemMessage | HumanMessage]) -> str:
    """Invoke LLM once, with a single retry on rate-limit errors."""
    try:
        return _to_text(llm.invoke(messages))
    except Exception as e:
        err = str(e).lower()
        if any(marker in err for marker in _RATE_LIMIT_MARKERS):
            time.sleep(0.5)
            return _to_text(llm.invoke(messages))
        raise


def _stuff_summarize(text: str) -> str:
    """Generate summary by stuffing full text into a single prompt."""
    llm = get_llm("primary")
    messages = [
        SystemMessage(content=STUFF_SYSTEM_PROMPT),
        HumanMessage(content=f"请对以下内容进行摘要：\n\n{text}"),
    ]
    summary = _invoke_with_retry(llm, messages)
    logger.info("Stuff 摘要完成，输入长度: %d 字符", len(text))
    return summary


def _split_for_map_reduce(text: str) -> list[str]:
    """Split long text into overlapped chunks for map-reduce summarization."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=MAP_CHUNK_SIZE,
        chunk_overlap=MAP_CHUNK_OVERLAP,
        separators=["\n\n", "\n", ""],
    )
    chunks = splitter.split_text(text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _map_reduce_summarize(text: str) -> str:
    """Generate summary with map-reduce strategy for long text."""
    llm = get_llm("primary")
    chunks = _split_for_map_reduce(text)
    if not chunks:
        return _stuff_summarize(text)

    map_outputs: list[str] = []
    for chunk in chunks:
        messages = [
            SystemMessage(content=MAP_SYSTEM_PROMPT),
            HumanMessage(content=f"请提取以下文本片段的关键信息：\n\n{chunk}"),
        ]
        map_outputs.append(_invoke_with_retry(llm, messages))
    logger.info("Map 阶段完成，共 %d 段", len(chunks))

    merged_parts = [
        f"--- 片段 {idx} 关键信息 ---\n{output}"
        for idx, output in enumerate(map_outputs, start=1)
    ]
    merged_text = "\n\n".join(merged_parts)

    reduce_messages = [
        SystemMessage(content=REDUCE_SYSTEM_PROMPT),
        HumanMessage(content=f"请整合以下分段关键信息并生成最终摘要：\n\n{merged_text}"),
    ]
    summary = _invoke_with_retry(llm, reduce_messages)
    logger.info("Reduce 阶段完成")
    return summary


def _extract_text_from_user_input(user_input: str) -> str:
    """Best-effort extraction of raw text pasted directly in user input."""
    raw = (user_input or "").strip()
    if not raw:
        return ""

    delimiters = ("以下内容", "内容如下", "如下：", "如下:", "：", ":")
    for delimiter in delimiters:
        if delimiter in raw:
            _, tail = raw.split(delimiter, 1)
            candidate = tail.strip()
            if candidate:
                return candidate

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(lines) > 1:
        return "\n".join(lines[1:]).strip()
    return raw


def summary_agent_node(state: dict) -> dict:
    """LangGraph node: summarize context text using adaptive strategy."""
    context = str(state.get("context", "") or "").strip()
    user_input = str(state.get("user_input", "") or "").strip()

    try:
        text = context if context else _extract_text_from_user_input(user_input)
        if len(text) < 50:
            return {
                "agent_output": "请提供需要摘要的文本内容（至少 50 字），我再为你生成结构化摘要。",
            }

        use_stuff = len(text) <= STUFF_THRESHOLD
        logger.info(
            "摘要策略: %s，文本长度: %d 字符",
            "Stuff" if use_stuff else "Map-Reduce",
            len(text),
        )

        summary_result = _stuff_summarize(text) if use_stuff else _map_reduce_summarize(text)
        return {"agent_output": summary_result}
    except Exception as e:
        logger.error("摘要生成失败: %s", e, exc_info=True)
        # 记录结构化错误信息，供调试和日志排查使用。
        error_record = {
            "agent": "summary",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "intent": str(state.get("current_intent", "summary") or "summary"),
        }
        return {
            "agent_output": "[系统提示] 摘要生成服务暂时不可用，请稍后重试。",
            "agent_errors": [error_record],
        }

def _build_policy_text() -> str:
    """Construct a medium-size sample policy notice for Stuff testing."""
    return """
关于 2026 年春季学期国家助学金与校内奖学金申请工作的通知

为进一步落实精准资助政策，保障家庭经济困难学生顺利完成学业，现启动 2026 年春季学期国家助学金与校内奖学金申请工作。申请对象为我校全日制在籍本科生与研究生。国家助学金申请人须满足家庭经济困难认定为一般困难及以上，且本学期无严重违纪处分；校内学业奖学金申请人须上一学期课程加权平均成绩不低于 82 分，并完成不少于 18 学分课程学习。

时间安排如下：2 月 20 日至 3 月 5 日为学生网上申报阶段；3 月 6 日至 3 月 12 日为院系审核阶段；3 月 13 日至 3 月 15 日为校级复核与公示阶段。逾期未提交材料视为自动放弃。申请入口为“智慧学工平台-资助服务-奖助申请”，学生需上传身份证正反面扫描件、家庭经济情况说明、上一学期成绩单及银行卡信息。家庭突发变故学生需补充上传街道或村委会出具的证明材料。

资助标准方面，国家助学金按困难等级分三档发放，分别为每生每学期 2200 元、1700 元、1200 元；校内学业奖学金分一、二、三等奖，标准分别为 3000 元、2000 元、1000 元。同一学生可在符合条件前提下同时申请国家助学金与校内学业奖学金，但不得重复享受同类型临时困难补贴。学院审核应重点核对学生身份信息、学籍状态、成绩真实性与困难认定有效期，并在公示期内设置举报邮箱与联系电话，接受监督。

学校要求各学院坚持公开、公平、公正原则，严禁弄虚作假。对提供虚假材料者，一经查实，取消本学年全部评优评奖资格，并按《学生纪律处分规定》处理。咨询电话：010-62780001，咨询邮箱：xsc@polyagent.edu.cn。请各单位严格按时间节点推进，确保资助资金按时发放到位。
""".strip()


def _print_test_result(name: str, strategy: str, text: str, output: str, passed: bool) -> None:
    """Print concise local test result."""
    print("=" * 72)
    print(f"{name}")
    print(f"策略类型: {strategy}")
    print(f"输入长度: {len(text)}")
    print(f"输出前 200 字: {output[:200]}")
    print(f"结果: {'PASS' if passed else 'FAIL'}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    short_text = _build_policy_text()
    long_text = "\n\n".join([short_text] * 12)

    # 测试 1（Stuff 策略）
    state_1 = {
        "user_input": "请总结以下内容",
        "context": short_text,
    }
    result_1 = summary_agent_node(state_1)
    output_1 = result_1.get("agent_output", "")
    pass_1 = bool(output_1.strip()) and "核心主题" in output_1
    _print_test_result("测试 1（Stuff）", "Stuff", short_text, output_1, pass_1)

    # 测试 2（Map-Reduce 策略）
    state_2 = {
        "user_input": "请总结以下长文档",
        "context": long_text,
    }
    result_2 = summary_agent_node(state_2)
    output_2 = result_2.get("agent_output", "")
    pass_2 = bool(output_2.strip()) and "核心主题" in output_2 and len(long_text) > STUFF_THRESHOLD
    _print_test_result("测试 2（Map-Reduce）", "Map-Reduce", long_text, output_2, pass_2)

    # 测试 3（空输入防御）
    state_3 = {
        "user_input": "帮我总结一下",
        "context": "",
    }
    result_3 = summary_agent_node(state_3)
    output_3 = result_3.get("agent_output", "")
    pass_3 = "请提供需要摘要的文本内容" in output_3
    _print_test_result("测试 3（空输入防御）", "N/A", "", output_3, pass_3)

