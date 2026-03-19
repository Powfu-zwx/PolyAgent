"""Generate desktop-oriented README screenshots for PolyAgent."""

from __future__ import annotations

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
SERVER_URL = "http://127.0.0.1:7860"
WINDOW_SIZE = (1440, 960)

HOME_SHOT = "polyagent-home-desktop.png"
FEATURE_SHOTS = [
    "polyagent-feature-multi-agent.png",
    "polyagent-feature-summary.png",
    "polyagent-feature-writing.png",
    "polyagent-feature-guide.png",
]

SCENARIOS = [
    {
        "filename": FEATURE_SHOTS[0],
        "status": "本轮处理：知识问答 -> 正式写作",
        "user": "先帮我整理供应商准入要求，再起草一段合作申请的开头。",
        "assistant_html": """
            <p><strong>根据你的需求，以下为分步处理结果：</strong></p>
            <p><strong>【信息整理】</strong></p>
            <ul>
              <li>通常需要提供营业执照、资质证明、过往项目案例和联系人信息。</li>
              <li>审核重点通常包括合规性、交付能力、服务稳定性和历史合作记录。</li>
              <li>在提交申请前，建议先补齐资质附件并确认业务范围匹配。</li>
            </ul>
            <p><strong>【申请开头草稿】</strong></p>
            <p>
              尊敬的负责人，您好。现就合作接入事宜提交申请。我方已完成基础资质材料整理，
              具备稳定的交付能力与项目执行经验，希望参与后续合作评估与准入审核。
            </p>
        """,
    },
    {
        "filename": FEATURE_SHOTS[1],
        "status": "本轮处理：摘要生成",
        "user": "我上传了一份运营通知，请提炼重点并列出后续动作。",
        "assistant_html": """
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
    },
    {
        "filename": FEATURE_SHOTS[2],
        "status": "本轮处理：正式写作",
        "user": "帮我写一份设备维护通知，说明本周六晚间将暂停服务两小时。",
        "assistant_html": """
            <p><strong>关于系统维护窗口调整的通知</strong></p>
            <p>
              为保障系统运行稳定，平台计划于本周六 22:00 至 24:00 开展例行维护。
              维护期间，部分功能将暂时不可用，请相关使用人员提前安排操作时间，避免影响业务办理。
            </p>
            <p>
              维护完成后将第一时间恢复服务。如有紧急事项，请提前联系对应支持人员。
              特此通知。
            </p>
            <p><strong>发布单位：</strong>平台运营组<br><strong>日期：</strong>2026 年 3 月 19 日</p>
        """,
    },
    {
        "filename": FEATURE_SHOTS[3],
        "status": "本轮处理：办事引导",
        "user": "请一步步引导我完成项目报销流程。",
        "assistant_html": """
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
    },
]


def wait_for_server(timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.get(SERVER_URL, timeout=3)
            if response.status_code == 200:
                return
        except requests.RequestException:
            time.sleep(0.8)
    raise RuntimeError("PolyAgent UI did not become ready in time.")


def build_driver() -> webdriver.Edge:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"--window-size={WINDOW_SIZE[0]},{WINDOW_SIZE[1]}")
    options.add_argument("--disable-gpu")
    options.add_argument("--force-device-scale-factor=1")
    driver = webdriver.Edge(options=options)
    driver.set_window_size(*WINDOW_SIZE)
    return driver


def normalize_shell(driver: webdriver.Edge) -> None:
    script = """
    const docEl = document.documentElement;
    const body = document.body;
    docEl.style.overflow = 'hidden';
    body.style.overflow = 'hidden';
    const shell = document.querySelector('#main-shell');
    if (shell) {
      shell.style.paddingRight = '22px';
    }
    """
    driver.execute_script(script)


def capture_home(driver: webdriver.Edge, output_path: Path) -> None:
    driver.get(SERVER_URL)
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))
    normalize_shell(driver)
    time.sleep(1.0)
    driver.save_screenshot(str(output_path))


def inject_conversation(
    driver: webdriver.Edge,
    *,
    status: str,
    user_text: str,
    assistant_html: str,
) -> None:
    script = """
    const payload = JSON.parse(arguments[0]);
    const statusStrip = document.querySelector('#status-strip');
    if (statusStrip) {
      statusStrip.innerHTML = `<div class="status-copy">${payload.status}</div>`;
    }

    const bubbleWrap = document.querySelector('#main-chatbot .bubble-wrap');
    if (!bubbleWrap) {
      throw new Error('Unable to locate chat bubble container.');
    }

    bubbleWrap.innerHTML = `
      <div class="message-row">
        <div class="message user">
          <div class="md"><p>${payload.user}</p></div>
        </div>
      </div>
      <div class="message-row">
        <div class="message bot">
          <div class="md">${payload.assistant}</div>
        </div>
      </div>
    `;

    const promptRow = document.querySelector('#prompt-row');
    if (promptRow) {
      promptRow.style.marginTop = '14px';
    }
    bubbleWrap.scrollTop = bubbleWrap.scrollHeight;
    """
    driver.execute_script(
        script,
        json.dumps(
            {
                "status": status,
                "user": user_text,
                "assistant": assistant_html,
            }
        ),
    )


def capture_feature_screenshot(driver: webdriver.Edge, scenario: dict[str, str], output_path: Path) -> None:
    driver.get(SERVER_URL)
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))
    normalize_shell(driver)
    inject_conversation(
        driver,
        status=scenario["status"],
        user_text=scenario["user"],
        assistant_html=scenario["assistant_html"],
    )
    time.sleep(0.8)
    driver.save_screenshot(str(output_path))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    server_process = subprocess.Popen(
        [sys.executable, "ui.py"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        wait_for_server()
        driver = build_driver()
        try:
            capture_home(driver, OUTPUT_DIR / HOME_SHOT)
            for scenario in SCENARIOS:
                capture_feature_screenshot(driver, scenario, OUTPUT_DIR / scenario["filename"])
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
