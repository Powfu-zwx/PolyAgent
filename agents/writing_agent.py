"""Writing agent for official document generation with a two-stage workflow."""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import get_llm

logger = logging.getLogger(__name__)

COMMON_PLACEHOLDER_INSTRUCTION = (
    "请基于用户提供的信息生成公文。对于用户未提供的要素，使用合理的占位符"
    "（如 [姓名]、[日期]、[具体事由]）标注，方便用户后续补充。"
)

WRITING_TEMPLATES = {
    "leave_application": f"""你是一位专业行政文书写作助手。请撰写正式、简洁的请假申请。
结构要求：
1. 标题：请假申请
2. 称呼：致XX（审批人/部门）
3. 正文：请假人信息、请假事由、起止日期、请假天数
4. 结尾：望批准 + 申请人签名 + 日期
5. 语气正式、简洁
{COMMON_PLACEHOLDER_INSTRUCTION}
""",
    "notice": f"""你是一位专业行政文书写作助手。请撰写正式、权威的通知公告。
结构要求：
1. 标题：关于XX的通知
2. 发文编号（可选）
3. 称呼：各部门/各单位
4. 正文：通知背景、具体事项、执行要求
5. 落款：发文单位 + 日期
6. 语气正式、权威
{COMMON_PLACEHOLDER_INSTRUCTION}
""",
    "scholarship_application": f"""你是一位专业行政文书写作助手。请撰写诚恳得体的奖学金申请书。
结构要求：
1. 标题：XX奖学金申请书
2. 称呼：尊敬的XX
3. 正文：个人基本信息、学习成绩概述、获奖经历、社会实践、家庭经济情况（如适用）、申请理由
4. 结尾：恳请批准 + 申请人 + 日期
5. 语气诚恳、得体
{COMMON_PLACEHOLDER_INSTRUCTION}
""",
    "event_proposal": f"""你是一位专业行政文书写作助手。请撰写完整、结构化的活动策划书。
结构要求：
1. 活动名称
2. 活动目的与意义
3. 活动时间与地点
4. 参与对象
5. 活动流程/环节安排
6. 预算概算（如有信息）
7. 预期效果
8. 组织单位
{COMMON_PLACEHOLDER_INSTRUCTION}
""",
    "work_report": f"""你是一位专业行政文书写作助手。请撰写客观务实的工作报告/总结。
结构要求：
1. 标题：XX工作报告/总结
2. 报告周期
3. 主要工作完成情况
4. 取得的成效与亮点
5. 存在的问题与不足
6. 下一步工作计划
7. 语气客观、务实
{COMMON_PLACEHOLDER_INSTRUCTION}
""",
}

DEFAULT_TEMPLATE = (
    "你是一位专业的公文写作助手。请根据用户需求撰写相应文档。"
    "格式规范、语言正式、结构清晰。对于用户未提供的信息，使用 [占位符] 标注。"
)

EXTRACT_SYSTEM_PROMPT = """你是一个写作需求分析器。请分析用户的写作请求，提取以下信息并输出严格的 JSON：
{
  "writing_type": "leave_application | notice | scholarship_application | event_proposal | work_report | unknown",
  "extracted_elements": {
    // 从用户输入中提取到的具体信息，key-value 形式
    // 提取不到的信息不要编造
  },
  "additional_requirements": "用户的特殊要求（如有）"
}

类型判断规则：
- 涉及请假、病假、事假、休假 -> leave_application
- 涉及发布通知、公告、告知 -> notice
- 涉及奖学金、助学金申请 -> scholarship_application
- 涉及活动策划、活动方案、活动组织 -> event_proposal
- 涉及工作总结、工作汇报、述职 -> work_report
- 无法判断 -> unknown

输出严格为 JSON，不要包含 markdown 代码块包装。
"""

_VALID_WRITING_TYPES = {
    "leave_application",
    "notice",
    "scholarship_application",
    "event_proposal",
    "work_report",
    "unknown",
}

_EMPTY_EXTRACTION = {
    "writing_type": "unknown",
    "extracted_elements": {},
    "additional_requirements": "",
}


def _strip_markdown_code_fence(text: str) -> str:
    """Remove optional markdown code-fence wrapper from model output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _to_text(response: object) -> str:
    """Convert LLM response to plain string."""
    return str(getattr(response, "content", "")).strip()


def _extract_writing_elements(user_input: str, context: str = "") -> dict:
    """Extract writing type and key elements from the request."""
    human_content = (
        f"【参考信息】\n{context}\n\n用户请求：{user_input}"
        if context.strip()
        else user_input
    )

    llm = get_llm("primary")
    response = llm.invoke(
        [
            SystemMessage(content=EXTRACT_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]
    )
    raw = _to_text(response)

    cleaned = _strip_markdown_code_fence(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("要素提取 JSON 解析失败，回退 unknown 类型")
        logger.info("要素提取完成: type=unknown")
        return dict(_EMPTY_EXTRACTION)

    if not isinstance(parsed, dict):
        logger.warning("要素提取结果非 JSON 对象，回退 unknown 类型")
        logger.info("要素提取完成: type=unknown")
        return dict(_EMPTY_EXTRACTION)

    writing_type = str(parsed.get("writing_type", "unknown")).strip()
    if writing_type not in _VALID_WRITING_TYPES:
        writing_type = "unknown"

    extracted_elements = parsed.get("extracted_elements", {})
    if not isinstance(extracted_elements, dict):
        extracted_elements = {}

    additional_requirements = parsed.get("additional_requirements", "")
    if not isinstance(additional_requirements, str):
        additional_requirements = str(additional_requirements)

    result = {
        "writing_type": writing_type,
        "extracted_elements": extracted_elements,
        "additional_requirements": additional_requirements.strip(),
    }
    logger.info("要素提取完成: type=%s", writing_type)
    return result


def _generate_document(
    writing_type: str,
    elements: dict,
    additional_req: str,
    user_input: str,
    context: str = "",
) -> str:
    """Generate the final document using selected template and extracted info."""
    system_prompt = WRITING_TEMPLATES.get(writing_type, DEFAULT_TEMPLATE)

    lines = [f"用户请求：{user_input}"]

    if elements:
        formatted = "\n".join(f"- {key}: {value}" for key, value in elements.items())
        lines.append(f"已提取的信息：\n{formatted}")

    if additional_req and additional_req.strip():
        lines.append(f"特殊要求：{additional_req.strip()}")

    if context and context.strip():
        lines.append(f"参考资料：\n{context.strip()}")

    human_prompt = "\n\n".join(lines)

    llm = get_llm("primary")
    response = llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt),
        ]
    )
    return _to_text(response)


def writing_agent_node(state: dict) -> dict:
    """LangGraph node for writing tasks with extract-then-generate pipeline."""
    try:
        user_input = state["user_input"]
        context = state.get("context", "")

        extraction = _extract_writing_elements(user_input, context)
        result = _generate_document(
            extraction["writing_type"],
            extraction.get("extracted_elements", {}),
            extraction.get("additional_requirements", ""),
            user_input,
            context,
        )
        return {"agent_output": result}
    except Exception as e:
        logger.error("公文写作服务调用失败: %s", e, exc_info=True)
        # 记录结构化错误信息，供调试和日志排查使用。
        error_record = {
            "agent": "writing",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "intent": str(state.get("current_intent", "writing") or "writing"),
        }
        return {
            "agent_output": "[系统提示] 公文写作服务暂时不可用，请稍后重试。",
            "agent_errors": [error_record],
        }


def _run_test_case(case_id: str, user_input: str, context: str, expected_type: str) -> bool:
    """Run one local test case and print extraction/generation previews."""
    try:
        extraction = _extract_writing_elements(user_input, context)
        writing_type = extraction.get("writing_type", "unknown")
        elements = extraction.get("extracted_elements", {})
        additional_req = extraction.get("additional_requirements", "")
        document = _generate_document(writing_type, elements, additional_req, user_input, context)

        passed = writing_type == expected_type
        print("=" * 80)
        print(case_id)
        print(f"要素提取结果: writing_type={writing_type}, extracted_elements={elements}")
        print(f"公文前 300 字: {document[:300]}")
        print(f"结果: {'PASS' if passed else 'FAIL'}")
        return passed
    except Exception as e:
        logger.error("%s 执行失败: %s", case_id, e, exc_info=True)
        print("=" * 80)
        print(case_id)
        print("要素提取结果: writing_type=unknown, extracted_elements={}")
        print("公文前 300 字: 抱歉，测试执行失败。")
        print("结果: FAIL")
        return False


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    total = 5
    passed = 0

    passed += int(
        _run_test_case(
            "T01（请假申请）",
            "帮我写一份请假申请，我叫张三，因为家中有急事需要请假3天，从3月1日到3月3日。",
            "",
            "leave_application",
        )
    )
    passed += int(
        _run_test_case(
            "T02（通知公告）",
            "帮我起草一份关于期末考试安排的通知。",
            "",
            "notice",
        )
    )
    passed += int(
        _run_test_case(
            "T03（奖学金申请 + context）",
            "帮我写一份奖学金申请书。",
            "该奖学金要求GPA 3.5以上，申请人需有社会实践经历。",
            "scholarship_application",
        )
    )
    passed += int(
        _run_test_case(
            "T04（活动策划）",
            "我们社团要办一个编程马拉松活动，帮我写个策划书。",
            "",
            "event_proposal",
        )
    )
    passed += int(
        _run_test_case(
            "T05（通用兜底）",
            "帮我写一段自我介绍。",
            "",
            "unknown",
        )
    )

    print("=" * 80)
    print(f"测试汇总: {passed}/{total} PASS")
