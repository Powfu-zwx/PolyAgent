# PolyAgent

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-111827?logo=python&logoColor=white)](./pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-10a37f.svg)](./LICENSE)
[![Release Notes](https://img.shields.io/badge/release-v0.1.0-0f766e.svg)](./docs/releases/v0.1.0.md)

[English](./README.md)

PolyAgent 是一个面向知识密集型服务场景的多智能体工作台。它把知识问答、文档摘要、正式写作和分步式流程引导整合进一个统一的聊天界面。

当前仓库默认自带中文提示词、示例数据和界面文案，但整体架构本身是通用的。你可以把它迁移到内部知识库问答、服务台助手、运营流程支持、教育服务或面向公众的智能体场景中。

推荐默认入口：直接运行 `python app.py`，使用主 Web 工作台。

## 为什么是 PolyAgent

- 一个工作台，覆盖问答、摘要、写作、引导四类高频任务。
- 支持复合请求路由，例如“先查政策，再起草回复”。
- 具备 Markdown 知识库接入、向量检索和上下文聚合能力。
- 已整理好 README 截图、Release 文案和传播素材，便于首轮发布。

## Demo

桌面端首页

![PolyAgent desktop home](./docs/images/polyagent-home-desktop-zh.png)

能力展示

| 多智能体编排 | 文档摘要 |
| --- | --- |
| ![PolyAgent multi-agent flow](./docs/images/polyagent-feature-multi-agent-zh.png) | ![PolyAgent summary workflow](./docs/images/polyagent-feature-summary-zh.png) |
| 正式文稿写作 | 分步流程引导 |
| ![PolyAgent writing workflow](./docs/images/polyagent-feature-writing-zh.png) | ![PolyAgent guide workflow](./docs/images/polyagent-feature-guide-zh.png) |

## 核心能力

- 基于私有知识库进行带检索依据的问答。
- 对上传文件或长文本生成结构化摘要。
- 根据简短需求生成通知、公文或其他结构化文稿。
- 以对话方式引导用户完成多步骤流程。
- 将一条复合请求拆解成多个子任务并按顺序执行。

## 快速开始

环境要求

- Python 3.10+
- `DEEPSEEK_API_KEY`
- `DASHSCOPE_API_KEY`

安装

```bash
git clone https://github.com/Powfu-zwx/PolyAgent.git
cd PolyAgent

python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
```

默认启动方式

```bash
python app.py
```

然后访问 `http://127.0.0.1:8000`。

如果你希望启用知识库检索问答，请先把 Markdown 文档放到 `knowledge/data/` 下，再构建向量索引：

```bash
python -m knowledge.vectorstore build
```

如果你是第一次体验项目，优先走上面的 `app.py` 路线。`ui.py` 仅作为备用的 Gradio 演示入口保留。

## 工作方式

1. 先整理并压缩当前对话上下文。
2. 将用户请求路由到一个或多个任务意图。
3. 执行知识问答、摘要生成、文稿写作和流程引导等 Agent。
4. 将多段结果聚合成最终回复。

## 典型使用场景

- 内部知识库助手，用于政策、制度或流程查询
- 服务台或运营支持助手，用于多步骤事务引导
- 文档处理助手，用于通知、摘要和正式写作
- LangGraph、RAG、多智能体编排的演示项目

## 仓库结构

- `agents/`：提示词和任务型 Agent 行为
- `core/`：路由、状态、编排和聊天服务逻辑
- `knowledge/`：知识库文档与向量检索流程
- `app.py`：推荐默认入口，主 Web 工作台
- `ui.py`：备用的 Gradio 演示入口
- `docs/`：Release、传播素材和图片资源

## Release 与资料入口

- Release 文案：[`v0.1.0`](./docs/releases/v0.1.0.md)
- 更新记录：[`CHANGELOG.md`](./CHANGELOG.md)
- 路线图：[`ROADMAP.md`](./ROADMAP.md)
- 传播素材：[`docs/launch-kit.md`](./docs/launch-kit.md)

当前已知限制

- 运行时依赖 DeepSeek 和 DashScope 兼容接口的 API Key。
- 开箱即用的提示词与示例数据仍以中文场景为主。
- 目前尚未提供在线 Demo 和短视频演示。

## 使用你自己的知识库

PolyAgent 默认从 `knowledge/data/` 中读取 Markdown 文档。建议为文档补充轻量级 YAML 元数据，例如 `title`、`category`、`source`、`date`，这样更有利于检索质量和来源追踪。

更新文档后，重新构建向量索引：

```bash
python -m knowledge.vectorstore build
```

## 截图资源

README 和 GitHub 社交预览图可以通过以下命令重新生成：

```bash
pip install ".[assets]"
python scripts/generate_readme_screenshots.py
python scripts/generate_social_preview.py
```

截图脚本会同时生成英文版 (`*-en.png`) 和中文版 (`*-zh.png`) 两套素材，社交预览图会输出到 `docs/images/polyagent-social-preview.png`。

## 技术栈

- LangGraph：多智能体编排
- LangChain：LLM 集成
- Chroma：向量检索
- FastAPI + 自定义前端：主工作台界面
- Gradio：备用演示界面
- DeepSeek 与兼容 OpenAI 风格接口的 Qwen 服务
- pytest：测试

## 许可证

MIT
