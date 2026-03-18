# PolyAgent

**多智能体政务与校园服务对话系统 | Multi-Agent Conversational System for Government Affairs & Campus Services**

---

## 目录 / Table of Contents

- [项目简介 / Overview](#项目简介--overview)
- [系统架构 / Architecture](#系统架构--architecture)
- [功能模块 / Features](#功能模块--features)
- [技术栈 / Tech Stack](#技术栈--tech-stack)
- [快速开始 / Quick Start](#快速开始--quick-start)
- [知识库构建 / Knowledge Base Setup](#知识库构建--knowledge-base-setup)
- [项目结构 / Project Structure](#项目结构--project-structure)
- [测试 / Testing](#测试--testing)
- [设计决策 / Design Decisions](#设计决策--design-decisions)
- [许可证 / License](#许可证--license)

---

## 项目简介 / Overview

**中文**

PolyAgent 是一个基于 LangGraph 的多智能体对话系统，面向政务办事和高校校园服务场景。系统采用三层 Router-Supervisor-Agent 架构，通过意图识别自动将用户请求路由至专业 Agent 处理，支持单轮问答与多轮复合任务的自动编排。

知识库基于南京工业大学官方网站及政务服务门户的 3343 篇结构化文档构建，覆盖政策法规、办事流程、通知公告和校园服务四大类别。

**English**

PolyAgent is a multi-agent conversational system built on LangGraph, designed for government affairs and campus service scenarios. It employs a three-layer Router-Supervisor-Agent architecture that automatically routes user requests to specialized agents via intent recognition, supporting both single-turn Q&A and multi-turn compound task orchestration.

The knowledge base is built from 3,343 structured documents sourced from Nanjing Tech University's official website and government service portals, covering four categories: policies, procedures, notices, and campus services.

---

## 系统架构 / Architecture

```
                        +------------------+
                        |    User Input    |
                        +--------+---------+
                                 |
                        +--------v---------+
                        |  Prepare Node    |  Context compression,
                        |                  |  history window management
                        +--------+---------+
                                 |
                        +--------v---------+
                        |     Router       |  Intent recognition (LLM)
                        |  (DeepSeek, t=0) |  Outputs: intents[], topic_changed
                        +--------+---------+
                                 |
                   +-------------+-------------+
                   |             |             |
              single intent  compound     topic change
                   |          intents      -> reset
                   |             |
                   v             v
            +-----------+ +------------+
            | Dispatch  | | Task Queue |  Sequential execution
            |   Node    | | Init Node  |  of multiple intents
            +-----------+ +------------+
                   |             |
         +---------+---------+---+
         |         |         |         |
    +----v--+ +----v---+ +--v----+ +--v----+
    |  QA   | |Summary | |Writing| | Guide |
    | Agent | | Agent  | | Agent | | Agent |
    +----+--+ +----+---+ +--+----+ +--+----+
         |         |         |         |
         +---------+---------+---------+
                   |
          +--------v---------+
          | Aggregate Output |  Merge results from
          |      Node        |  all completed agents
          +--------+---------+
                   |
          +--------v---------+
          |   Final Output   |
          +------------------+
```

**三层架构说明 / Three-Layer Architecture:**

| 层级 / Layer | 组件 / Component | 职责 / Responsibility |
|---|---|---|
| 路由层 / Routing | Router | 意图识别、话题转变检测 / Intent recognition, topic change detection |
| 调度层 / Orchestration | Supervisor | 任务队列管理、Agent 分发、结果聚合 / Task queue management, agent dispatch, result aggregation |
| 执行层 / Execution | Agents (x4) | 专业任务执行 / Specialized task execution |

---

## 功能模块 / Features

### 知识问答 Agent / QA Agent

基于 RAG (Retrieval-Augmented Generation) 的知识问答，从向量知识库中检索相关文档片段，结合 LLM 生成精准回答。支持按文档类别过滤检索。

RAG-based knowledge Q&A. Retrieves relevant document chunks from the vector store and generates precise answers with LLM. Supports category-filtered retrieval.

### 摘要生成 Agent / Summary Agent

支持两种摘要策略：Stuff（短文本直接摘要）和 Map-Reduce（长文本分段摘要后合并）。系统根据输入长度自动选择策略。

Two summarization strategies: Stuff (direct summarization for short texts) and Map-Reduce (segment-then-merge for long texts). Strategy is auto-selected based on input length.

### 公文写作 Agent / Writing Agent

两阶段生成：先从用户输入中提取公文要素（类型、主送、事由等），再根据要素和模板生成规范公文。支持通知、申请、报告等常见公文类型。

Two-phase generation: first extracts document elements (type, recipient, subject, etc.) from user input, then generates formal documents based on elements and templates. Supports notices, applications, reports, and other common document types.

### 办事引导 Agent / Guide Agent

基于 RAG 检索流程类文档，以多轮对话形式逐步引导用户完成办事流程。动态适配不同业务场景，无需硬编码状态机。

RAG-based process guidance using procedure documents. Guides users step-by-step through administrative processes via multi-turn dialogue. Dynamically adapts to different scenarios without hardcoded state machines.

### 复合任务编排 / Compound Task Orchestration

支持单条用户输入包含多个意图的自动拆解与串行执行。例如"查一下奖学金政策，然后帮我写申请书"会自动拆解为 QA -> Writing 两个子任务，前序 Agent 的输出作为后续 Agent 的上下文输入。

Supports automatic decomposition and sequential execution of multiple intents within a single user input. For example, "Look up the scholarship policy, then help me draft an application" is decomposed into QA -> Writing subtasks, with the output of the preceding agent fed as context to the next.

---

## 技术栈 / Tech Stack

| 类别 / Category | 技术 / Technology |
|---|---|
| 多 Agent 编排 / Agent Orchestration | LangGraph (StateGraph) |
| LLM 框架 / LLM Framework | LangChain |
| 主力 LLM / Primary LLM | DeepSeek (deepseek-chat) |
| 备用 LLM / Backup LLM | Qwen (qwen-plus, DashScope) |
| 向量嵌入 / Embeddings | DashScope text-embedding-v3 (dim=1024) |
| 向量数据库 / Vector Store | Chroma (langchain-chroma) |
| 前端 / Frontend | Gradio 4.x |
| 测试 / Testing | pytest (fast/slow markers) |

---

## 快速开始 / Quick Start

### 环境要求 / Prerequisites

- Python 3.10+
- DeepSeek API Key ([获取 / Get one](https://platform.deepseek.com/))
- DashScope API Key ([获取 / Get one](https://dashscope.console.aliyun.com/))

### 安装 / Installation

```bash
# 克隆仓库 / Clone the repository
git clone https://github.com/<your-username>/PolyAgent.git
cd PolyAgent

# 创建虚拟环境 / Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 安装依赖 / Install dependencies
pip install -r requirements.txt
```

### 配置 / Configuration

```bash
# 复制环境变量模板 / Copy environment variable template
cp .env.example .env

# 编辑 .env，填入 API Key / Edit .env with your API keys
# DEEPSEEK_API_KEY=your_deepseek_key_here
# DASHSCOPE_API_KEY=your_dashscope_key_here
```

### 构建知识库 / Build Knowledge Base

详见下方 [知识库构建](#知识库构建--knowledge-base-setup) 章节。

See [Knowledge Base Setup](#知识库构建--knowledge-base-setup) section below.

### 启动 / Launch

```bash
python ui.py
```

启动后访问 `http://localhost:7860` 即可使用。

After launch, visit `http://localhost:7860` to use the system.

---

## 知识库构建 / Knowledge Base Setup

PolyAgent 的知识库基于结构化 Markdown 文档构建。由于文档数据量较大（3343 篇），原始文档未包含在 Git 仓库中。

The knowledge base is built from structured Markdown documents. Due to the large volume (3,343 documents), raw documents are not included in the Git repository.

### 文档格式 / Document Format

每篇文档为独立的 `.md` 文件，包含 YAML front matter 元数据：

Each document is a standalone `.md` file with YAML front matter metadata:

```markdown
---
title: 本科生奖学金评定办法
category: policy
source: 南京工业大学学生处
source_url: https://example.edu.cn/policy/123
date: 2024-03-15
format_type: policy
---

正文内容...
```

### 目录结构 / Directory Structure

```
knowledge/data/
├── index.md           # 数据索引说明 / Data index
├── policy/            # 政策法规 / Policies & regulations
├── procedure/         # 办事流程 / Procedures
├── notice/            # 通知公告 / Notices
└── service/           # 校园服务 / Campus services
```

### 构建向量索引 / Build Vector Index

将文档放入 `knowledge/data/` 对应目录后，运行以下命令构建 Chroma 向量索引：

After placing documents in the appropriate `knowledge/data/` directories, run:

```bash
python -m knowledge.vectorstore --build
```

构建参数：分块大小 500 字符，重叠 100 字符，使用 DashScope text-embedding-v3 (dim=1024)。索引持久化至 `knowledge/chroma_db/`。

Build parameters: chunk size 500 chars, overlap 100 chars, using DashScope text-embedding-v3 (dim=1024). Index is persisted to `knowledge/chroma_db/`.

---

## 项目结构 / Project Structure

```
PolyAgent/
├── README.md                    # 项目说明
├── LICENSE                      # MIT License
├── requirements.txt             # Python 依赖
├── .env.example                 # 环境变量模板
├── .gitignore
│
├── config/
│   ├── __init__.py
│   └── settings.py              # 配置管理 + get_llm() 工厂函数
│
├── agents/
│   ├── __init__.py
│   ├── qa_agent.py              # 知识问答 Agent (RAG)
│   ├── summary_agent.py         # 摘要生成 Agent (Stuff / Map-Reduce)
│   ├── writing_agent.py         # 公文写作 Agent (两阶段生成)
│   └── guide_agent.py           # 办事引导 Agent (RAG + 多轮引导)
│
├── core/
│   ├── __init__.py
│   ├── state.py                 # PolyAgentState 全局状态定义 (14 字段)
│   ├── router.py                # 意图识别 Router (结构化 Prompt)
│   ├── supervisor.py            # LangGraph StateGraph 编排
│   ├── context_manager.py       # 上下文压缩 (LLM-based)
│   └── prepare.py               # 轮间状态预处理
│
├── knowledge/
│   ├── __init__.py
│   ├── vectorstore.py           # 向量知识库管理 (Chroma + DashScope)
│   ├── data/                    # 文档语料 (not tracked by git)
│   └── chroma_db/               # Chroma 持久化索引 (not tracked by git)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # pytest 共享 fixture
│   ├── test_router.py           # Router 意图回归测试
│   ├── test_qa_agent.py         # QA Agent 测试
│   ├── test_summary_agent.py    # Summary Agent 测试
│   ├── test_writing_agent.py    # Writing Agent 测试
│   ├── test_guide_agent.py      # Guide Agent 测试
│   ├── test_integration.py      # 端到端集成测试
│   └── test_ui.py               # UI 工具函数测试
│
├── ui.py                        # Gradio 前端界面
└── app.py                       # FastAPI 后端 (预留)
```

---

## 测试 / Testing

```bash
# 运行全部快速测试 / Run all fast tests
pytest -m "not slow"

# 运行全部测试（含 LLM API 调用）/ Run all tests (including LLM API calls)
pytest

# 运行特定模块 / Run specific module
pytest tests/test_router.py -v

# 查看测试覆盖率 / Check coverage
pytest --cov=. --cov-report=html
```

测试分层说明：

| 标记 / Marker | 说明 / Description | 数量 / Count |
|---|---|---|
| (default) | 快速测试，Mock LLM 调用 / Fast tests with mocked LLM | 26 |
| `slow` | 需要真实 API 调用 / Requires real API calls | 18 |

---

## 设计决策 / Design Decisions

以下记录了开发过程中的关键技术选型及其理由：

Key technical decisions made during development and their rationale:

| 决策 / Decision | 选择 / Choice | 理由 / Rationale |
|---|---|---|
| 上下文压缩 / Context compression | LLM-based 压缩 vs 硬截断 | 保留语义连贯性，优于简单的滑动窗口截断 / Preserves semantic coherence over simple truncation |
| 状态管理 / State management | 图内无条件重置 vs 外部清理 | Fail-fast 设计，状态自包含于图执行周期 / Fail-fast, self-contained within graph execution cycle |
| 办事引导 / Service guidance | RAG 检索 + LLM 引导 vs 硬编码状态机 | 可维护性高，动态适配新流程 / Better maintainability, adapts to new processes dynamically |
| 嵌入模型 / Embedding model | DashScope API vs 本地模型 | 与现有 API 基础设施一致，质量稳定 / Consistent with existing API infra, stable quality |
| 向量数据库 / Vector store | Chroma vs FAISS | 内置元数据过滤能力，适配文档分类需求 / Built-in metadata filtering for document categories |
| 前端框架 / Frontend | Gradio vs Streamlit | 原生聊天组件 + 流式输出支持 / Native chat component + streaming support |
| 后端架构 / Backend | Gradio 内置后端 vs 独立 FastAPI | 减少架构复杂度，单进程部署 / Reduced complexity, single-process deployment |

---

## 许可证 / License

本项目基于 [MIT License](LICENSE) 开源。

This project is licensed under the [MIT License](LICENSE).
