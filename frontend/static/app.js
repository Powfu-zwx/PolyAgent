const SESSION_KEY = "polyagent-session-id";
const MESSAGES_KEY = "polyagent-messages-v2";
const STATUS_KEY = "polyagent-status-v2";
const QUICK_PROMPT_SELECTOR = ".prompt-chip[data-prompt]";
const LOADING_STAGES = [
  "\u6b63\u5728\u8bc6\u522b\u610f\u56fe...",
  "\u6b63\u5728\u7ec4\u7ec7\u4e0a\u4e0b\u6587...",
  "\u6b63\u5728\u751f\u6210\u56de\u590d...",
];

const workspace = document.getElementById("workspace");
const emptyState = document.getElementById("emptyState");
const messagesEl = document.getElementById("messages");
const composerForm = document.getElementById("composerForm");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const fileInput = document.getElementById("fileInput");
const attachBtn = document.getElementById("attachBtn");
const fileMeta = document.getElementById("fileMeta");
const fileName = document.getElementById("fileName");
const removeFileBtn = document.getElementById("removeFileBtn");
const newChatBtn = document.getElementById("newChatBtn");
const statusStrip = document.getElementById("statusStrip");
const messageTemplate = document.getElementById("messageTemplate");

const appState = {
  sessionId: getOrCreateSessionId(),
  transcript: loadJson(MESSAGES_KEY, []),
  statusText: localStorage.getItem(STATUS_KEY) || "",
  pending: false,
  selectedFile: null,
  loadingTimer: null,
  loadingIndex: 0,
};

boot();

function boot() {
  bindEvents();
  renderTranscript();
  updateStatus(appState.statusText);
  syncLayout();
  autoResize();
  toggleSendDisabled();
}

function bindEvents() {
  composerForm.addEventListener("submit", onSubmit);
  messageInput.addEventListener("input", () => {
    autoResize();
    toggleSendDisabled();
  });
  attachBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", onFileSelected);
  removeFileBtn.addEventListener("click", clearSelectedFile);
  newChatBtn.addEventListener("click", resetConversation);
  window.addEventListener("resize", autoResize);

  document.querySelectorAll(QUICK_PROMPT_SELECTOR).forEach((button) => {
    button.addEventListener("click", () => {
      messageInput.value = button.dataset.prompt || "";
      autoResize();
      toggleSendDisabled();
      messageInput.focus();
    });
  });
}

async function onSubmit(event) {
  event.preventDefault();
  if (appState.pending) {
    return;
  }

  const message = messageInput.value.trim();
  if (!message && !appState.selectedFile) {
    return;
  }

  const userText = buildUserDisplay(message, appState.selectedFile);
  pushTranscript({
    role: "user",
    content: userText,
    html: renderPlainText(userText),
  });
  clearComposer();

  const pendingIndex = pushTranscript({
    role: "assistant",
    content: LOADING_STAGES[0],
    html: renderPendingHtml(LOADING_STAGES[0]),
    pending: true,
  });

  appState.pending = true;
  toggleSendDisabled();
  startLoadingAnimation(pendingIndex);

  const formData = new FormData();
  formData.append("session_id", appState.sessionId);
  formData.append("message", message);
  if (appState.selectedFile) {
    formData.append("uploaded_file", appState.selectedFile);
  }

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    replacePendingMessage(pendingIndex, {
      role: "assistant",
      content: payload.assistant_message,
      html: payload.assistant_html || renderPlainText(payload.assistant_message),
      meta: payload.meta,
    });
    updateStatus(payload.status_text || "");
  } catch (error) {
    replacePendingMessage(pendingIndex, {
      role: "assistant",
      content: "\u7cfb\u7edf\u5904\u7406\u5f02\u5e38\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002",
      html: renderPlainText("\u7cfb\u7edf\u5904\u7406\u5f02\u5e38\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002"),
    });
    updateStatus("\u5904\u7406\u5931\u8d25");
    console.error(error);
  } finally {
    stopLoadingAnimation();
    clearSelectedFile();
    appState.pending = false;
    toggleSendDisabled();
  }
}

function onFileSelected(event) {
  const file = (event.target.files || [])[0] || null;
  appState.selectedFile = file;
  renderSelectedFile();
  toggleSendDisabled();
}

function clearSelectedFile() {
  appState.selectedFile = null;
  fileInput.value = "";
  renderSelectedFile();
  toggleSendDisabled();
}

async function resetConversation() {
  try {
    await fetch("/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: appState.sessionId }),
    });
  } catch (error) {
    console.error(error);
  }

  appState.transcript = [];
  appState.statusText = "";
  stopLoadingAnimation();
  clearComposer();
  clearSelectedFile();
  localStorage.removeItem(MESSAGES_KEY);
  localStorage.removeItem(STATUS_KEY);
  renderTranscript();
  updateStatus("");
}

function buildUserDisplay(message, file) {
  if (!file) {
    return message;
  }
  const base = message || "\u8bf7\u5bf9\u4ee5\u4e0b\u6587\u4ef6\u5185\u5bb9\u8fdb\u884c\u6458\u8981\u603b\u7ed3";
  return `${base}\n[\u5df2\u4e0a\u4f20\u6587\u4ef6: ${file.name}]`;
}

function clearComposer() {
  messageInput.value = "";
  autoResize();
}

function renderSelectedFile() {
  if (!appState.selectedFile) {
    fileMeta.classList.add("hidden");
    fileName.textContent = "";
    return;
  }
  fileMeta.classList.remove("hidden");
  fileName.textContent = appState.selectedFile.name;
}

function toggleSendDisabled() {
  const disabled = appState.pending || (!messageInput.value.trim() && !appState.selectedFile);
  sendBtn.disabled = disabled;
}

function startLoadingAnimation(index) {
  appState.loadingIndex = 0;
  appState.loadingTimer = window.setInterval(() => {
    appState.loadingIndex = (appState.loadingIndex + 1) % LOADING_STAGES.length;
    const item = appState.transcript[index];
    if (!item || !item.pending) {
      stopLoadingAnimation();
      return;
    }
    item.content = LOADING_STAGES[appState.loadingIndex];
    item.html = renderPendingHtml(item.content);
    renderTranscript();
  }, 900);
}

function stopLoadingAnimation() {
  if (!appState.loadingTimer) {
    return;
  }
  window.clearInterval(appState.loadingTimer);
  appState.loadingTimer = null;
}

function pushTranscript(message) {
  appState.transcript.push(message);
  persistTranscript();
  renderTranscript();
  return appState.transcript.length - 1;
}

function replacePendingMessage(index, message) {
  appState.transcript[index] = message;
  persistTranscript();
  renderTranscript();
}

function persistTranscript() {
  localStorage.setItem(MESSAGES_KEY, JSON.stringify(appState.transcript));
}

function updateStatus(text) {
  appState.statusText = text;
  if (!text) {
    statusStrip.classList.add("hidden");
    statusStrip.innerHTML = "";
    localStorage.removeItem(STATUS_KEY);
    return;
  }
  statusStrip.classList.remove("hidden");
  statusStrip.innerHTML = `<div class="status-pill">${escapeHtml(text)}</div>`;
  localStorage.setItem(STATUS_KEY, text);
}

function renderTranscript() {
  messagesEl.innerHTML = "";
  if (!appState.transcript.length) {
    messagesEl.classList.add("hidden");
    emptyState.classList.remove("hidden");
    workspace.classList.add("is-empty");
    workspace.classList.remove("has-messages");
    return;
  }

  messagesEl.classList.remove("hidden");
  emptyState.classList.add("hidden");
  workspace.classList.remove("is-empty");
  workspace.classList.add("has-messages");

  appState.transcript.forEach((message) => {
    const fragment = messageTemplate.content.cloneNode(true);
    const row = fragment.querySelector(".message-row");
    const content = fragment.querySelector(".message-content");
    const meta = fragment.querySelector(".message-meta");
    const chips = fragment.querySelector(".meta-chips");
    const toggle = fragment.querySelector(".reasoning-toggle");
    const reasoning = fragment.querySelector(".reasoning-panel");

    row.classList.add(message.role);
    if (message.pending) {
      row.classList.add("pending");
    }

    content.innerHTML = message.html || renderPlainText(message.content || "");

    if (message.meta) {
      const chipNodes = buildMetaChips(message.meta);
      chipNodes.forEach((node) => chips.appendChild(node));
      const hasReasoning = Boolean(message.meta.routing_reasoning);
      if (chipNodes.length || hasReasoning) {
        meta.classList.remove("hidden");
      }
      if (hasReasoning) {
        toggle.classList.remove("hidden");
        toggle.addEventListener("click", () => {
          const hidden = reasoning.classList.toggle("hidden");
          toggle.textContent = hidden
            ? "\u67e5\u770b\u610f\u56fe\u601d\u8def"
            : "\u6536\u8d77\u610f\u56fe\u601d\u8def";
        });
        reasoning.textContent = message.meta.routing_reasoning;
      }
    }

    messagesEl.appendChild(fragment);
  });

  syncLayout();
}

function buildMetaChips(meta) {
  const nodes = [];
  (meta.completed_intent_labels || []).forEach((label) => {
    nodes.push(createChip(label, true));
  });
  if (meta.topic_changed) {
    nodes.push(createChip("\u5df2\u5207\u6362\u8bdd\u9898", false));
  }
  if (meta.file_name) {
    nodes.push(createChip(meta.file_name, false));
  }
  if (meta.text_truncated) {
    nodes.push(createChip("\u5df2\u622a\u65ad\u8d85\u957f\u8f93\u5165", false));
  }
  return nodes;
}

function createChip(text, accent) {
  const chip = document.createElement("span");
  chip.className = `meta-chip${accent ? " accent" : ""}`;
  chip.textContent = text;
  return chip;
}

function renderPendingHtml(text) {
  return (
    `${escapeHtml(text)} ` +
    '<span class="typing-dots"><span></span><span></span><span></span></span>'
  );
}

function renderPlainText(text) {
  return escapeHtml(text).replace(/\n/g, "<br>");
}

function syncLayout() {
  requestAnimationFrame(() => {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  });
}

function autoResize() {
  messageInput.style.height = "auto";
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 220)}px`;
}

function getOrCreateSessionId() {
  const existing = localStorage.getItem(SESSION_KEY);
  if (existing) {
    return existing;
  }
  const value = crypto.randomUUID();
  localStorage.setItem(SESSION_KEY, value);
  return value;
}

function loadJson(key, fallback) {
  const raw = localStorage.getItem(key);
  if (!raw) {
    return fallback;
  }
  try {
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
