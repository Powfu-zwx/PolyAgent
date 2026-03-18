"""RAG-based QA agent node for government/campus question answering."""

from __future__ import annotations

import logging
import re

from langchain_core.messages import SystemMessage, HumanMessage

from config.settings import get_llm
from knowledge.vectorstore import search, format_search_results

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """浣犳槸涓€涓斂鍔′笌鏍″洯鏈嶅姟鐭ヨ瘑闂瓟鍔╂墜銆傝鍩轰簬涓嬫柟鎻愪緵鐨勩€愬弬鑰冭祫鏂欍€戝洖绛旂敤鎴烽棶棰樸€?
鍥炵瓟鍘熷垯锛?1. 涓ユ牸鍩轰簬鍙傝€冭祫鏂欏洖绛旓紝涓嶈缂栭€犳垨鎺ㄦ祴璧勬枡涓病鏈夌殑淇℃伅
2. 濡傛灉鍙傝€冭祫鏂欎腑娌℃湁涓庨棶棰樼洿鎺ョ浉鍏崇殑淇℃伅锛屽潶璇氬憡鐭ョ敤鎴?褰撳墠鐭ヨ瘑搴撲腑鏈壘鍒扮浉鍏充俊鎭?锛屼笉瑕佸己琛屾嫾鍑戠瓟妗?3. 鍥炵瓟绠€娲佸噯纭紝浣跨敤娓呮櫚鐨勪腑鏂囪〃杈?4. 鍦ㄥ洖绛旀湯灏炬敞鏄庝俊鎭潵婧愶紙鍙傝€冭祫鏂欑殑鏍囬锛?
銆愬弬鑰冭祫鏂欍€?{rag_context}
"""


def qa_agent_node(state: dict) -> dict:
    """Handle QA intent with RAG retrieval and grounded response generation."""
    rag_context = ""

    try:
        user_input = state["user_input"]
        context = state.get("context", "")
        retrieval_missing = False

        try:
            docs = search(user_input, k=5)
            if docs:
                rag_context = format_search_results(docs)
                if not rag_context.strip():
                    rag_context = "未检索到相关资料。"
                    retrieval_missing = True
            else:
                rag_context = "未检索到相关资料。"
                retrieval_missing = True
        except Exception as e:
            logger.error("RAG retrieval failed: %s", e, exc_info=True)
            rag_context = "未检索到相关资料。"
            retrieval_missing = True

        system_prompt = SYSTEM_PROMPT.format(rag_context=rag_context)
        if retrieval_missing:
            system_prompt += "\n知识库中未找到直接相关内容，请基于通用知识谨慎回答并提醒用户核实。"
        if context:
            system_prompt += (
                "\n\n【前序任务结果】\n"
                f"{context}\n"
                "请结合前序任务的结果和参考资料来回答。"
            )

        llm = get_llm("primary")
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input),
        ]
        response = llm.invoke(messages)
        answer = str(getattr(response, "content", "")).strip()
        return {
            "agent_output": answer,
            "rag_context": rag_context,
        }
    except Exception as e:
        logger.error("QA agent execution failed: %s", e, exc_info=True)
        # 记录结构化错误信息，供调试和日志排查使用。
        error_record = {
            "agent": "qa",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "intent": str(state.get("current_intent", "qa") or "qa"),
        }
        return {
            "agent_output": "[系统提示] 知识问答服务暂时不可用，请稍后重试。",
            "rag_context": rag_context,
            "agent_errors": [error_record],
        }

def _extract_titles(rag_context: str) -> list[str]:
    """Extract titles from formatted RAG context."""
    if not rag_context:
        return []
    return re.findall(r"\[来源\]\s*(.+?)(?:（|\()", rag_context)

def _run_case(case_id: str, query: str, context: str = "") -> dict:
    """Run one QA case and return node output."""
    state = {
        "user_input": query,
        "context": context,
    }
    result = qa_agent_node(state)
    answer = result.get("agent_output", "")
    rag_context = result.get("rag_context", "")

    print("=" * 72)
    print(f"{case_id} | Query: {query}")
    if context:
        print(f"Context: {context}")
    print(f"RAG empty: {rag_context == '未检索到相关资料。'}")
    print(f"Answer preview: {answer[:200]}")
    return result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    _run_case("T01", "奖学金申请条件是什么？")