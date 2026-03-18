"""Guide agent for step-by-step procedure assistance with procedure-only RAG."""

from __future__ import annotations

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import get_llm
from knowledge.vectorstore import format_search_results, search

logger = logging.getLogger(__name__)

GUIDE_SYSTEM_PROMPT = """你是一位耐心专业的政务与校园办事引导助手。你的职责是根据参考资料，以清晰的分步骤方式引导用户完成办事流程。
引导原则：
1. 将办事流程拆解为清晰步骤，每步用“第X步”标注
2. 每个步骤说明：需要做什么、去哪里办理、需要准备什么材料
3. 如果流程有前置条件或注意事项，在开头提醒
4. 如果参考资料中有办理时限、收费情况等信息，在末尾总结说明
5. 语气亲切专业，像一位经验丰富的窗口工作人员在面对面指导

回答格式：
【办事事项】简要说明要办理什么事
【前置准备】办理前需要满足的条件或准备的材料（如有）
【办理步骤】
第1步：...
第2步：...
第3步：...
（根据实际流程确定步骤数量）
【温馨提示】办理时限、收费情况、注意事项等补充信息

如果参考资料中没有与用户需求直接相关的流程信息，坦诚告知用户“当前知识库中未找到该事项的详细办理流程”，并建议用户咨询相关部门。不要编造流程步骤。
【参考资料】
{rag_context}
"""

_NOT_FOUND_RAG_CONTEXT = "未检索到相关办事流程资料。"
_STRICT_NOT_FOUND_MESSAGE = "当前知识库中未找到该事项的详细办理流程，建议咨询相关部门获取准确办理指引。"

_GUIDE_FILLER_PHRASES = (
    "一步步",
    "手把手",
    "教我",
    "怎么",
    "怎么办",
    "如何",
    "申请",
    "办理",
    "申报",
    "流程",
    "请",
    "帮我",
)


def _to_text(response: object) -> str:
    """Convert LLM response object to plain text."""
    return str(getattr(response, "content", "")).strip()


def _extract_titles_from_rag_context(rag_context: str) -> list[str]:
    """Extract source titles from formatted rag context blocks."""
    if not rag_context:
        return []
    return re.findall(r"\[来源\]\s*(.+?)(?:（|\()", rag_context)


def _extract_core_terms(user_input: str) -> list[str]:
    """Extract core semantic terms from user query for lightweight relevance checks."""
    text = user_input
    for phrase in _GUIDE_FILLER_PHRASES:
        text = text.replace(phrase, " ")
    text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text)
    parts = [part.strip() for part in text.split() if part.strip()]
    return [part for part in parts if len(part) >= 2]


def _ngram_overlap_score(term: str, title: str) -> int:
    """Compute simple n-gram overlap count between term and title."""
    score = 0
    for n in (2, 3):
        if len(term) < n:
            continue
        grams = {term[i : i + n] for i in range(len(term) - n + 1)}
        score += sum(1 for gram in grams if gram in title)
    return score


def _is_retrieval_directly_related(user_input: str, docs: list[object]) -> bool:
    """Judge whether retrieval results are directly related to current user request."""
    if not docs:
        return False

    terms = _extract_core_terms(user_input)
    if not terms:
        return True

    for doc in docs:
        title = str(getattr(doc, "metadata", {}).get("title", "")).strip()
        if not title:
            continue
        for term in terms:
            if term in title:
                return True
            if len(term) >= 4 and _ngram_overlap_score(term, title) >= 2:
                return True
    return False


def guide_agent_node(state: dict) -> dict:
    """LangGraph node for guided process assistance."""
    rag_context = _NOT_FOUND_RAG_CONTEXT

    try:
        user_input = state["user_input"]
        context = state.get("context", "")

        docs = search(user_input, k=5, category_filter="procedure")
        if docs:
            if _is_retrieval_directly_related(user_input, docs):
                formatted = format_search_results(docs)
                rag_context = (
                    formatted.strip() if formatted and formatted.strip() else _NOT_FOUND_RAG_CONTEXT
                )
            else:
                rag_context = _NOT_FOUND_RAG_CONTEXT
                logger.info("Guide 检索结果与用户事项匹配度低，触发无流程兜底")

        system_prompt = GUIDE_SYSTEM_PROMPT.format(rag_context=rag_context)
        if context:
            system_prompt += (
                "\n\n【前序任务结果】\n"
                f"{context}\n"
                "请结合前序任务的结果进行引导。"
            )

        llm = get_llm("primary")
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input),
        ]
        response = llm.invoke(messages)
        answer = _to_text(response)
        if rag_context == _NOT_FOUND_RAG_CONTEXT:
            has_fallback_phrase = "当前知识库中未找到该事项的详细办理流程" in answer
            has_steps = "第1步" in answer or "第 1 步" in answer
            if (not has_fallback_phrase) or has_steps:
                answer = _STRICT_NOT_FOUND_MESSAGE
        return {
            "agent_output": answer,
            "rag_context": rag_context,
        }
    except Exception as e:
        logger.error("办事引导服务调用失败: %s", e, exc_info=True)
        # 记录结构化错误信息，供调试和日志排查使用。
        error_record = {
            "agent": "guide",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "intent": str(state.get("current_intent", "guide") or "guide"),
        }
        return {
            "agent_output": "[系统提示] 办事引导服务暂时不可用，请稍后重试。",
            "rag_context": rag_context,
            "agent_errors": [error_record],
        }


def _run_case(
    case_id: str,
    user_input: str,
    context: str = "",
    expect_fallback: bool = False,
) -> bool:
    """Run one local guide test case and print concise verification."""
    try:
        docs = search(user_input, k=5, category_filter="procedure")
        titles = [str(doc.metadata.get("title", "")).strip() for doc in docs]
    except Exception as e:
        logger.error("%s 检索失败: %s", case_id, e, exc_info=True)
        docs = []
        titles = []

    result = guide_agent_node({"user_input": user_input, "context": context})
    output = str(result.get("agent_output", ""))

    has_steps = "第1步" in output or "第 1 步" in output
    has_structured_sections = "【办事事项】" in output and "【办理步骤】" in output
    fallback_ok = (
        "当前知识库中未找到该事项的详细办理流程" in output
        and ("咨询相关部门" in output or "咨询" in output)
    )

    passed = fallback_ok if expect_fallback else (has_steps and has_structured_sections)

    print("=" * 80)
    print(case_id)
    print(f"检索文档标题: {titles}")
    print(f"Guide 输出前 400 字: {output[:400]}")
    print(f"结果: {'PASS' if passed else 'FAIL'}")
    return passed


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    total = 4
    passed = 0

    passed += int(_run_case("T01（政务办事流程）", "我想办理奖学金申请，帮我一步步说明流程。"))
    passed += int(_run_case("T02（校园办事流程）", "手把手教我怎么申请家庭经济困难学生资助。"))
    passed += int(_run_case("T03（与 QA 区分）", "教育事业贡献奖励怎么申报，请一步步引导我。"))
    passed += int(_run_case("T04（知识库无关内容）", "一步步教我怎么申请出国留学签证", expect_fallback=True))

    print("=" * 80)
    print(f"测试汇总: {passed}/{total} PASS")
