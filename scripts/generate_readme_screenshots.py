"""Generate localized README screenshots for the FastAPI web workspace."""

from __future__ import annotations

import html
import json
import subprocess
import sys
import time
from pathlib import Path

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "docs" / "images"
SERVER_URL = "http://127.0.0.1:8000"
HEALTH_URL = f"{SERVER_URL}/api/health"
WINDOW_SIZE = (1440, 960)

SESSION_KEY = "polyagent-session-id"
MESSAGES_KEY = "polyagent-messages-v2"
STATUS_KEY = "polyagent-status-v2"

SHOT_BASENAMES = {
    "home": "polyagent-home-desktop",
    "multi_agent": "polyagent-feature-multi-agent",
    "summary": "polyagent-feature-summary",
    "writing": "polyagent-feature-writing",
    "guide": "polyagent-feature-guide",
}

LOCALE_CONFIGS: dict[str, dict[str, object]] = {
    "en": {
        "ui": {
            "document_title": "PolyAgent Workspace",
            "topbar_suffix": "Workspace",
            "badge": "Multi-Agent Assistant",
            "hero_title": "How can PolyAgent help?",
            "hero_subtitle": "Ask questions, summarize documents, draft formal text, or guide a workflow.",
            "input_placeholder": "Ask a question, describe a document task, or request a draft",
            "feature_badge": "QA / Summary / Writing / Guidance",
            "upload_label": "Upload file",
            "remove_label": "Remove",
            "reasoning_show": "View routing notes",
            "reasoning_hide": "Hide routing notes",
            "quick_prompts": [
                {
                    "label": "Notice summary",
                    "prompt": "Summarize the key points and follow-up actions in this notice.",
                },
                {
                    "label": "Reimbursement flow",
                    "prompt": "Walk me through the project reimbursement process step by step.",
                },
                {
                    "label": "Maintenance notice",
                    "prompt": "Draft a system maintenance notice for me.",
                },
            ],
        },
        "scenarios": [
            {
                "basename": SHOT_BASENAMES["multi_agent"],
                "status": "This turn: Knowledge QA -> Formal writing",
                "messages": [
                    {
                        "role": "user",
                        "content": "First organize the supplier onboarding requirements, then draft the opening of a partnership request.",
                        "html": "<p>First organize the supplier onboarding requirements, then draft the opening of a partnership request.</p>",
                    },
                    {
                        "role": "assistant",
                        "content": "Multi-agent result",
                        "html": """
                            <p><strong>Here is the result, split by step:</strong></p>
                            <p><strong>[Requirement Summary]</strong></p>
                            <ul>
                              <li>Typical materials include a business license, qualification documents, case studies, and contact details.</li>
                              <li>Review usually focuses on compliance, delivery capability, service stability, and prior cooperation history.</li>
                              <li>Before submission, complete all supporting documents and confirm scope alignment.</li>
                            </ul>
                            <p><strong>[Draft Opening]</strong></p>
                            <p>Dear Team, I am submitting this request regarding partnership onboarding. We have completed the initial qualification package and can provide stable delivery, structured execution, and relevant project experience for the review process.</p>
                        """,
                        "meta": {
                            "completed_intent_labels": ["Knowledge QA", "Formal writing"],
                            "routing_reasoning": "",
                            "topic_changed": False,
                            "file_name": "",
                            "text_truncated": False,
                        },
                    },
                ],
            },
            {
                "basename": SHOT_BASENAMES["summary"],
                "status": "This turn: Document summarization",
                "messages": [
                    {
                        "role": "user",
                        "content": "I uploaded an operations notice. Please extract the key points and follow-up actions.\n[Uploaded file: operations-notice.md]",
                        "html": "<p>I uploaded an operations notice. Please extract the key points and follow-up actions.<br>[Uploaded file: operations-notice.md]</p>",
                    },
                    {
                        "role": "assistant",
                        "content": "Summary result",
                        "html": """
                            <p><strong>[Core Theme]</strong></p>
                            <p>This notice explains a temporary service adjustment and clarifies timing, impact scope, and execution requirements.</p>
                            <p><strong>[Key Points]</strong></p>
                            <ul>
                              <li>During maintenance, related services will be handled online only.</li>
                              <li>Requests submitted before Friday 18:00 will enter the processing queue first.</li>
                              <li>Users should prepare identity information and required attachments in advance.</li>
                            </ul>
                            <p><strong>[Follow-up Actions]</strong></p>
                            <ul>
                              <li>Notify affected users about the temporary change.</li>
                              <li>Complete any missing documents before formal submission.</li>
                              <li>Track the recovery announcement after the maintenance window ends.</li>
                            </ul>
                        """,
                        "meta": {
                            "completed_intent_labels": ["Summary"],
                            "routing_reasoning": "",
                            "topic_changed": False,
                            "file_name": "operations-notice.md",
                            "text_truncated": False,
                        },
                    },
                ],
            },
            {
                "basename": SHOT_BASENAMES["writing"],
                "status": "This turn: Formal writing",
                "messages": [
                    {
                        "role": "user",
                        "content": "Draft a maintenance notice explaining that services will pause for two hours on Saturday night.",
                        "html": "<p>Draft a maintenance notice explaining that services will pause for two hours on Saturday night.</p>",
                    },
                    {
                        "role": "assistant",
                        "content": "Writing result",
                        "html": """
                            <p><strong>Notice on Scheduled Maintenance Window</strong></p>
                            <p>To maintain platform stability, the system is scheduled for routine maintenance this Saturday from 22:00 to 24:00. During that period, some functions will be temporarily unavailable, and affected users should arrange operations in advance.</p>
                            <p>Service will resume immediately after maintenance is complete. For urgent matters, please contact the relevant support owner ahead of time.</p>
                            <p><strong>Issued by:</strong> Platform Operations Team<br><strong>Date:</strong> March 19, 2026</p>
                        """,
                        "meta": {
                            "completed_intent_labels": ["Formal writing"],
                            "routing_reasoning": "",
                            "topic_changed": False,
                            "file_name": "",
                            "text_truncated": False,
                        },
                    },
                ],
            },
            {
                "basename": SHOT_BASENAMES["guide"],
                "status": "This turn: Step-by-step guidance",
                "messages": [
                    {
                        "role": "user",
                        "content": "Please guide me through the project reimbursement process step by step.",
                        "html": "<p>Please guide me through the project reimbursement process step by step.</p>",
                    },
                    {
                        "role": "assistant",
                        "content": "Guide result",
                        "html": """
                            <p><strong>[Overview]</strong></p>
                            <p>This process covers preparation, submission, review feedback, and payment tracking.</p>
                            <p><strong>[Steps]</strong></p>
                            <ol>
                              <li>Prepare invoices, the reimbursement form, payment proof, and all required attachments.</li>
                              <li>Check that the expense category, budget code, and amount are consistent.</li>
                              <li>Submit the full packet through the designated entry point or approval system.</li>
                              <li>Respond to review feedback and supplement any missing explanations or files.</li>
                              <li>Track the payment status after approval and archive the final materials.</li>
                            </ol>
                            <p><strong>[Tips]</strong></p>
                            <p>Confirm invoice validity before submission and keep digital backups of all attachments.</p>
                        """,
                        "meta": {
                            "completed_intent_labels": ["Step-by-step guidance"],
                            "routing_reasoning": "",
                            "topic_changed": False,
                            "file_name": "",
                            "text_truncated": False,
                        },
                    },
                ],
            },
        ],
    },
    "zh": {
        "ui": {
            "document_title": "PolyAgent Workspace",
            "topbar_suffix": "智能工作台",
            "badge": "多智能体助手",
            "hero_title": "有什么可以帮忙的？",
            "hero_subtitle": "知识问答、文档摘要、正式写作、流程引导，都可以直接开始。",
            "input_placeholder": "输入问题、文档处理需求，或让它帮你起草内容",
            "feature_badge": "问答 / 摘要 / 写作 / 引导",
            "upload_label": "上传文件",
            "remove_label": "移除",
            "reasoning_show": "查看意图思路",
            "reasoning_hide": "收起意图思路",
            "quick_prompts": [
                {
                    "label": "通知摘要",
                    "prompt": "帮我总结这份通知的关键点和待办事项。",
                },
                {
                    "label": "报销流程",
                    "prompt": "请一步步说明项目报销该怎么处理。",
                },
                {
                    "label": "维护通知",
                    "prompt": "帮我起草一封系统升级维护通知。",
                },
            ],
        },
        "scenarios": [
            {
                "basename": SHOT_BASENAMES["multi_agent"],
                "status": "本轮处理：知识问答 -> 正式写作",
                "messages": [
                    {
                        "role": "user",
                        "content": "先帮我整理供应商准入要求，再起草一段合作申请的开头。",
                        "html": "<p>先帮我整理供应商准入要求，再起草一段合作申请的开头。</p>",
                    },
                    {
                        "role": "assistant",
                        "content": "多智能体结果",
                        "html": """
                            <p><strong>根据你的需求，以下为分步处理结果：</strong></p>
                            <p><strong>【信息整理】</strong></p>
                            <ul>
                              <li>通常需要提供营业执照、资质证明、过往项目案例和联系人信息。</li>
                              <li>审核重点通常包括合规性、交付能力、服务稳定性和历史合作记录。</li>
                              <li>在提交申请前，建议先补齐资质附件并确认业务范围匹配。</li>
                            </ul>
                            <p><strong>【申请开头草稿】</strong></p>
                            <p>尊敬的负责人，您好。现就合作接入事宜提交申请。我方已完成基础资质材料整理，具备稳定的交付能力与项目执行经验，希望参与后续合作评估与准入审核。</p>
                        """,
                        "meta": {
                            "completed_intent_labels": ["知识问答", "正式写作"],
                            "routing_reasoning": "",
                            "topic_changed": False,
                            "file_name": "",
                            "text_truncated": False,
                        },
                    },
                ],
            },
            {
                "basename": SHOT_BASENAMES["summary"],
                "status": "本轮处理：摘要生成",
                "messages": [
                    {
                        "role": "user",
                        "content": "我上传了一份运营通知，请提炼重点并列出后续动作。\n[已上传文件: 运营通知.md]",
                        "html": "<p>我上传了一份运营通知，请提炼重点并列出后续动作。<br>[已上传文件: 运营通知.md]</p>",
                    },
                    {
                        "role": "assistant",
                        "content": "摘要结果",
                        "html": """
                            <p><strong>【核心主题】</strong></p>
                            <p>这份通知主要说明了服务调整安排，并明确了时间节点、影响范围与执行要求。</p>
                            <p><strong>【关键要点】</strong></p>
                            <ul>
                              <li>维护期间，相关业务统一切换为线上处理。</li>
                              <li>周五 18:00 前提交的事项将优先进入处理队列。</li>
                              <li>用户需提前准备身份信息与所需附件材料。</li>
                            </ul>
                            <p><strong>【后续动作】</strong></p>
                            <ul>
                              <li>向受影响用户同步临时调整说明。</li>
                              <li>在正式提交前补齐缺失资料。</li>
                              <li>持续关注维护结束后的恢复公告。</li>
                            </ul>
                        """,
                        "meta": {
                            "completed_intent_labels": ["摘要生成"],
                            "routing_reasoning": "",
                            "topic_changed": False,
                            "file_name": "运营通知.md",
                            "text_truncated": False,
                        },
                    },
                ],
            },
            {
                "basename": SHOT_BASENAMES["writing"],
                "status": "本轮处理：正式写作",
                "messages": [
                    {
                        "role": "user",
                        "content": "帮我写一份设备维护通知，说明本周六晚间将暂停服务两小时。",
                        "html": "<p>帮我写一份设备维护通知，说明本周六晚间将暂停服务两小时。</p>",
                    },
                    {
                        "role": "assistant",
                        "content": "写作结果",
                        "html": """
                            <p><strong>关于系统维护窗口调整的通知</strong></p>
                            <p>为保障系统运行稳定，平台计划于本周六 22:00 至 24:00 开展例行维护。维护期间，部分功能将暂时不可使用，请相关使用人员提前安排操作时间，避免影响业务办理。</p>
                            <p>维护完成后将第一时间恢复服务。如有紧急事项，请提前联系对应支持人员。特此通知。</p>
                            <p><strong>发布单位：</strong>平台运营组<br><strong>日期：</strong>2026 年 3 月 19 日</p>
                        """,
                        "meta": {
                            "completed_intent_labels": ["正式写作"],
                            "routing_reasoning": "",
                            "topic_changed": False,
                            "file_name": "",
                            "text_truncated": False,
                        },
                    },
                ],
            },
            {
                "basename": SHOT_BASENAMES["guide"],
                "status": "本轮处理：流程引导",
                "messages": [
                    {
                        "role": "user",
                        "content": "请一步步引导我完成项目报销流程。",
                        "html": "<p>请一步步引导我完成项目报销流程。</p>",
                    },
                    {
                        "role": "assistant",
                        "content": "引导结果",
                        "html": """
                            <p><strong>【事项说明】</strong></p>
                            <p>本流程覆盖材料准备、提交审核、补件反馈和款项跟踪四个环节。</p>
                            <p><strong>【办理步骤】</strong></p>
                            <ol>
                              <li>先准备发票、报销单、付款凭证及对应附件。</li>
                              <li>核对费用类别、预算科目和金额是否一致。</li>
                              <li>将完整材料提交到指定入口或审批系统。</li>
                              <li>根据审核反馈及时补充缺失说明或附件。</li>
                              <li>审批通过后跟进付款状态，并保留归档材料。</li>
                            </ol>
                            <p><strong>【温馨提示】</strong></p>
                            <p>提交前先确认发票有效性，并建议提前保留全部附件的电子备份。</p>
                        """,
                        "meta": {
                            "completed_intent_labels": ["流程引导"],
                            "routing_reasoning": "",
                            "topic_changed": False,
                            "file_name": "",
                            "text_truncated": False,
                        },
                    },
                ],
            },
        ],
    },
}


def wait_for_server(timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.get(HEALTH_URL, timeout=3)
            if response.status_code == 200:
                return
        except requests.RequestException:
            time.sleep(0.8)
    raise RuntimeError("PolyAgent web workspace did not become ready in time.")


def build_driver() -> webdriver.Edge:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"--window-size={WINDOW_SIZE[0]},{WINDOW_SIZE[1]}")
    options.add_argument("--disable-gpu")
    options.add_argument("--force-device-scale-factor=1")
    driver = webdriver.Edge(options=options)
    driver.set_window_size(*WINDOW_SIZE)
    return driver


def shot_path(basename: str, locale: str) -> Path:
    return OUTPUT_DIR / f"{basename}-{locale}.png"


def wait_until_ready(driver: webdriver.Edge) -> None:
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "messageInput")))


def normalize_shell(driver: webdriver.Edge) -> None:
    script = """
    document.documentElement.style.overflow = 'hidden';
    document.body.style.overflow = 'hidden';
    const messages = document.getElementById('messages');
    if (messages) {
      messages.style.scrollbarWidth = 'none';
    }
    """
    driver.execute_script(script)


def apply_ui_locale(driver: webdriver.Edge, ui_strings: dict[str, object]) -> None:
    payload = json.dumps(ui_strings, ensure_ascii=False)
    script = """
    const payload = JSON.parse(arguments[0]);
    document.title = payload.document_title;

    const titleSub = document.querySelector('.title-sub');
    if (titleSub) {
      titleSub.textContent = payload.topbar_suffix;
    }

    const badge = document.querySelector('.topbar-badge');
    if (badge) {
      badge.textContent = payload.badge;
    }

    const heading = document.querySelector('#emptyState h1');
    if (heading) {
      heading.textContent = payload.hero_title;
    }

    const subtitle = document.querySelector('#emptyState p');
    if (subtitle) {
      subtitle.textContent = payload.hero_subtitle;
    }

    const textarea = document.getElementById('messageInput');
    if (textarea) {
      textarea.setAttribute('placeholder', payload.input_placeholder);
    }

    const attachButton = document.getElementById('attachBtn');
    if (attachButton) {
      attachButton.textContent = payload.upload_label;
    }

    const removeButton = document.getElementById('removeFileBtn');
    if (removeButton) {
      removeButton.textContent = payload.remove_label;
    }

    const capBadge = document.querySelector('.cap-badge');
    if (capBadge) {
      capBadge.textContent = payload.feature_badge;
    }

    const quickButtons = Array.from(document.querySelectorAll('.prompt-chip'));
    quickButtons.forEach((button, index) => {
      const item = payload.quick_prompts[index];
      if (!item) {
        return;
      }
      button.textContent = item.label;
      button.dataset.prompt = item.prompt;
    });

    const reasoningButtons = Array.from(document.querySelectorAll('.reasoning-toggle'));
    reasoningButtons.forEach((button) => {
      const expanded = button.textContent === '收起意图思路' || button.textContent === payload.reasoning_hide;
      button.textContent = expanded ? payload.reasoning_hide : payload.reasoning_show;
    });
    """
    driver.execute_script(script, payload)


def set_storage_state(
    driver: webdriver.Edge,
    *,
    transcript: list[dict[str, object]],
    status_text: str,
) -> None:
    payload = json.dumps(
        {
            "session_id": "polyagent-screenshot-session",
            "transcript": transcript,
            "status_text": status_text,
        },
        ensure_ascii=False,
    )
    script = f"""
    const payload = JSON.parse(arguments[0]);
    localStorage.setItem('{SESSION_KEY}', payload.session_id);
    localStorage.setItem('{MESSAGES_KEY}', JSON.stringify(payload.transcript));
    if (payload.status_text) {{
      localStorage.setItem('{STATUS_KEY}', payload.status_text);
    }} else {{
      localStorage.removeItem('{STATUS_KEY}');
    }}
    """
    driver.execute_script(script, payload)


def prepare_page(
    driver: webdriver.Edge,
    *,
    locale_config: dict[str, object],
    transcript: list[dict[str, object]],
    status_text: str,
) -> None:
    driver.get(SERVER_URL)
    wait_until_ready(driver)
    set_storage_state(driver, transcript=transcript, status_text=status_text)
    driver.refresh()
    wait_until_ready(driver)
    normalize_shell(driver)
    apply_ui_locale(driver, locale_config["ui"])  # type: ignore[arg-type]
    driver.execute_script(
        """
        const messages = document.getElementById('messages');
        if (messages) {
          messages.scrollTop = messages.scrollHeight;
        }
        """
    )
    time.sleep(0.8)


def capture_home(driver: webdriver.Edge, locale: str, locale_config: dict[str, object]) -> None:
    prepare_page(driver, locale_config=locale_config, transcript=[], status_text="")
    driver.save_screenshot(str(shot_path(SHOT_BASENAMES["home"], locale)))


def capture_feature_screenshot(
    driver: webdriver.Edge,
    locale: str,
    locale_config: dict[str, object],
    scenario: dict[str, object],
) -> None:
    prepare_page(
        driver,
        locale_config=locale_config,
        transcript=scenario["messages"],  # type: ignore[arg-type]
        status_text=str(scenario["status"]),
    )
    driver.save_screenshot(str(shot_path(str(scenario["basename"]), locale)))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    server_process = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        wait_for_server()
        driver = build_driver()
        try:
            for locale, locale_config in LOCALE_CONFIGS.items():
                capture_home(driver, locale, locale_config)
                for scenario in locale_config["scenarios"]:  # type: ignore[index]
                    capture_feature_screenshot(driver, locale, locale_config, scenario)
        finally:
            driver.quit()
    finally:
        server_process.terminate()
        try:
            server_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server_process.kill()


if __name__ == "__main__":
    main()
