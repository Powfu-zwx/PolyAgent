"""Application settings and LLM factory helpers for PolyAgent."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"

# 加载项目根目录 .env 到进程环境变量。
load_dotenv(dotenv_path=ENV_PATH, override=False)


@dataclass(frozen=True)
class Settings:
    """Centralized runtime settings."""

    # --- API Keys（从环境变量读取，无默认值）---
    DEEPSEEK_API_KEY: str = ""
    DASHSCOPE_API_KEY: str = ""

    PRIMARY_MODEL: str = "deepseek-chat"
    PRIMARY_BASE_URL: str = "https://api.deepseek.com"

    BACKUP_MODEL: str = "qwen-plus"
    BACKUP_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_DIMENSIONS: int = 1024

    MAX_HISTORY_WINDOW: int = 5
    MAX_CONTEXT_LENGTH: int = 2000
    ROUTER_TEMPERATURE: float = 0.0
    AGENT_TEMPERATURE: float = 0.7


# 供业务模块直接 import 的配置常量。
MAX_CONTEXT_LENGTH = Settings.MAX_CONTEXT_LENGTH


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取全局配置单例，从环境变量读取 API Key 并校验。"""
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    dashscope_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()

    # Fail fast：必需 Key 缺失时立即报错，避免运行到调用阶段才失败。
    missing: list[str] = []
    if not deepseek_key:
        missing.append("DEEPSEEK_API_KEY")
    if not dashscope_key:
        missing.append("DASHSCOPE_API_KEY")
    if missing:
        raise ValueError(
            f"缺少必需的环境变量: {', '.join(missing)}。"
            "请在项目根目录的 .env 文件中配置，参考 .env.example。"
        )

    return Settings(
        DEEPSEEK_API_KEY=deepseek_key,
        DASHSCOPE_API_KEY=dashscope_key,
    )


def get_llm(role: Literal["primary", "backup"] = "primary") -> ChatOpenAI:
    """Create a provider-specific ChatOpenAI client by role."""
    settings = get_settings()

    if role == "primary":
        return ChatOpenAI(
            model=settings.PRIMARY_MODEL,
            base_url=settings.PRIMARY_BASE_URL,
            api_key=settings.DEEPSEEK_API_KEY,
            temperature=settings.AGENT_TEMPERATURE,
        )

    if role == "backup":
        return ChatOpenAI(
            model=settings.BACKUP_MODEL,
            base_url=settings.BACKUP_BASE_URL,
            api_key=settings.DASHSCOPE_API_KEY,
            temperature=settings.AGENT_TEMPERATURE,
        )

    raise ValueError("role must be either 'primary' or 'backup'.")


def get_embedding() -> OpenAIEmbeddings:
    """Create an OpenAI-compatible embedding client for DashScope."""
    settings = get_settings()
    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        base_url=settings.EMBEDDING_BASE_URL,
        api_key=settings.DASHSCOPE_API_KEY,
        dimensions=settings.EMBEDDING_DIMENSIONS,
    )
