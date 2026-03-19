# PolyAgent Launch Kit

## GitHub Repository Metadata

| Item | Recommendation |
| --- | --- |
| Repository description | `A multi-agent workspace for grounded QA, document summarization, formal writing, and step-by-step guidance.` |
| 仓库简介 | `一个将知识问答、文档摘要、正式写作和流程引导整合进统一聊天界面的多智能体工作台。` |
| Suggested homepage | Set this after the first release is published: `https://github.com/Powfu-zwx/PolyAgent/releases/tag/v0.1.0` |
| Suggested topics | `multi-agent`, `langgraph`, `rag`, `knowledge-base`, `gradio`, `document-summarization`, `ai-writing`, `workflow-assistant`, `openai-compatible`, `python` |
| Social preview asset | `docs/images/polyagent-social-preview.png` |

## Standard Screenshot Set

| Asset | Scenario | README title | Recommended use |
| --- | --- | --- | --- |
| `polyagent-home-desktop-en.png` / `polyagent-home-desktop-zh.png` | Clean workspace overview | Desktop home / 桌面端首页 | Hero image for README and release page |
| `polyagent-feature-multi-agent-*.png` | One request routed into multiple tasks | Multi-agent orchestration / 多智能体编排 | Show why this is not a single-agent chat bot |
| `polyagent-feature-summary-*.png` | Structured summary output | Document summarization / 文档摘要 | Highlight file and long-text handling |
| `polyagent-feature-writing-*.png` | Formal notice drafting | Formal writing / 正式文稿写作 | Show practical writing value |
| `polyagent-feature-guide-*.png` | Guided step-by-step workflow | Step-by-step guidance / 分步流程引导 | Show service or process assistance |

## Demo Talk Track

### Chinese 45-60s Script

`0-8s`
PolyAgent 是一个多智能体工作台，不是单一问答机器人。它把知识问答、文档摘要、正式写作和流程引导放进了同一个聊天界面。

`8-18s`
先看首页，用户进入后可以直接输入问题、上传文档，或者从几个高频任务开始试用。

`18-30s`
如果用户发来复合请求，比如先查资料、再起草回复，系统会拆成多个任务顺序处理，而不是一次性糊成一段答案。

`30-42s`
如果上传通知、制度或流程文档，PolyAgent 可以先提炼重点，再生成结构化摘要和后续动作建议。

`42-52s`
在写作和流程引导场景里，它既可以起草正式通知，也可以把复杂事务拆成一步步可执行的流程。

`52-60s`
这套架构可以迁移到企业知识库、内部服务台、教育服务和流程助手等场景。

### English 45-60s Script

`0-8s`
PolyAgent is a multi-agent workspace rather than a single-purpose chatbot. It brings grounded QA, document summarization, formal writing, and workflow guidance into one interface.

`8-18s`
Start on the home screen: users can ask a question, upload a document, or pick a high-frequency task right away.

`18-30s`
When a request contains multiple goals, such as finding policy details and then drafting a reply, PolyAgent routes the work into separate tasks instead of forcing one generic answer.

`30-42s`
For uploaded notices or process documents, it can extract key points, produce a structured summary, and surface next actions.

`42-52s`
In writing and workflow scenarios, it can draft a formal notice or turn a complex process into clear, step-by-step guidance.

`52-60s`
The same architecture can be adapted to internal knowledge bases, service desks, education workflows, and other knowledge-heavy operations.

## Reusable Short Copy

### One-line Pitch

- EN: `A multi-agent workspace for grounded QA, summaries, formal writing, and workflow guidance.`
- ZH: `一个把知识问答、文档摘要、正式写作和流程引导整合进统一聊天界面的多智能体工作台。`

### Short Channel Intro

- EN: `PolyAgent helps teams answer questions, summarize documents, draft formal text, and guide workflows in one chat workspace.`
- ZH: `PolyAgent 让团队在一个聊天工作台里完成问答、摘要、写作和流程引导。`

### Poster / Cover Copy

- EN: `One workspace. Four capabilities. Multi-agent by default.`
- ZH: `一个工作台，四种能力，多智能体协同处理。`

## Release Publishing Checklist

1. Confirm screenshots under `docs/images/` are up to date.
2. Run `python scripts/generate_social_preview.py` if the social preview needs refreshing.
3. Create GitHub release `v0.1.0` and paste content from `docs/releases/v0.1.0.md`.
4. In repository settings, update description, topics, homepage, and social preview image.
5. After release goes live, link to the release page in external posts for first-time visitors.
