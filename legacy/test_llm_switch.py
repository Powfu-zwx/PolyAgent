"""LLM primary/backup switch verification script."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional, TypedDict

DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEEPSEEK_MODEL: str = "deepseek-chat"
QWEN_MODEL: str = "qwen-plus"
TEST_PROMPT: str = "请用一句话介绍什么是多Agent系统"
DEEPSEEK_HARDCODED_API_KEY: str = "sk-4c06530e91264ade825c3dc69337cbd7"
QWEN_HARDCODED_API_KEY: str = "sk-dea121471f164ad3842939e1c951cc74"


class TokenUsage(TypedDict):
    """Token usage structure for one model call."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LLMCallResult(TypedDict):
    """Result structure returned by one model call."""

    text: str
    tokens: TokenUsage
    latency: float


class QualityMetrics(TypedDict):
    """Heuristic quality metrics for quick response comparison."""

    char_count: int
    keyword_hits: int
    sentence_marks: int
    score: float


@dataclass(frozen=True)
class LLMConfig:
    """Configuration for switching between different LLM providers."""

    provider: str
    base_url: str
    api_key: str
    model: str


def _to_int(value: Optional[int]) -> int:
    """Convert an optional integer to a concrete integer."""
    return int(value) if value is not None else 0


def call_llm(config: LLMConfig, prompt: str) -> LLMCallResult:
    """Call one provider via OpenAI SDK-compatible API and return normalized result."""
    try:
        from openai import (
            APIConnectionError,
            APIStatusError,
            AuthenticationError,
            OpenAI,
            OpenAIError,
            RateLimitError,
        )
    except ImportError as exc:
        raise RuntimeError("依赖错误：未安装 openai，请先执行 `pip install openai`。") from exc

    client = OpenAI(api_key=config.api_key, base_url=config.base_url)
    started_at = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=config.model,
            messages=[{"role": "user", "content": prompt}],
        )
    except APIConnectionError as exc:
        raise RuntimeError(f"[{config.provider}] 网络错误：无法连接 API。详情：{exc}") from exc
    except AuthenticationError as exc:
        raise RuntimeError(f"[{config.provider}] 认证错误：API Key 无效或权限不足。详情：{exc}") from exc
    except RateLimitError as exc:
        raise RuntimeError(f"[{config.provider}] 速率限制：请求过于频繁。详情：{exc}") from exc
    except APIStatusError as exc:
        raise RuntimeError(
            f"[{config.provider}] 接口状态错误：HTTP {exc.status_code}。详情：{exc}"
        ) from exc
    except OpenAIError as exc:
        raise RuntimeError(f"[{config.provider}] OpenAI SDK 错误：{exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"[{config.provider}] 未知错误：{exc}") from exc
    latency = time.perf_counter() - started_at

    usage = response.usage
    tokens: TokenUsage = {
        "prompt_tokens": _to_int(getattr(usage, "prompt_tokens", None)),
        "completion_tokens": _to_int(getattr(usage, "completion_tokens", None)),
        "total_tokens": _to_int(getattr(usage, "total_tokens", None)),
    }
    text: str = response.choices[0].message.content or ""
    return {"text": text, "tokens": tokens, "latency": latency}


def evaluate_quality(text: str) -> QualityMetrics:
    """Compute heuristic quality metrics for quick side-by-side comparison."""
    cleaned = text.strip()
    keywords = ("多Agent", "多智能体", "系统", "协作")
    keyword_hits = sum(1 for token in keywords if token in cleaned)
    sentence_marks = sum(cleaned.count(mark) for mark in ("。", "！", "？", "!", "?"))
    score = round(keyword_hits * 2.0 + min(len(cleaned), 120) / 60.0 + min(sentence_marks, 2), 2)
    return {
        "char_count": len(cleaned),
        "keyword_hits": keyword_hits,
        "sentence_marks": sentence_marks,
        "score": score,
    }


def print_provider_result(provider: str, result: LLMCallResult) -> None:
    """Print full result details for one provider."""
    print(f"\n[{provider}] 模型返回的完整文本：")
    print(result["text"])
    tokens = result["tokens"]
    print(
        "tokens："
        f"prompt_tokens={tokens['prompt_tokens']}, "
        f"completion_tokens={tokens['completion_tokens']}, "
        f"total_tokens={tokens['total_tokens']}"
    )
    print(f"请求耗时（秒）：{result['latency']:.3f}")


def compare_results(deepseek: LLMCallResult, qwen: LLMCallResult) -> None:
    """Compare quality, token consumption, and latency between two providers."""
    deepseek_quality = evaluate_quality(deepseek["text"])
    qwen_quality = evaluate_quality(qwen["text"])
    token_delta = deepseek["tokens"]["total_tokens"] - qwen["tokens"]["total_tokens"]
    latency_delta = deepseek["latency"] - qwen["latency"]

    print("\n=== 对比结果 ===")
    print("响应质量（启发式，仅用于快速比较）：")
    print(
        "DeepSeek: "
        f"score={deepseek_quality['score']}, "
        f"char_count={deepseek_quality['char_count']}, "
        f"keyword_hits={deepseek_quality['keyword_hits']}"
    )
    print(
        "Qwen: "
        f"score={qwen_quality['score']}, "
        f"char_count={qwen_quality['char_count']}, "
        f"keyword_hits={qwen_quality['keyword_hits']}"
    )
    print(
        "Token 总消耗对比："
        f"DeepSeek={deepseek['tokens']['total_tokens']}, "
        f"Qwen={qwen['tokens']['total_tokens']}, "
        f"差值(DeepSeek-Qwen)={token_delta}"
    )
    print(
        "延迟对比（秒）："
        f"DeepSeek={deepseek['latency']:.3f}, "
        f"Qwen={qwen['latency']:.3f}, "
        f"差值(DeepSeek-Qwen)={latency_delta:.3f}"
    )
    faster_provider = "DeepSeek" if deepseek["latency"] < qwen["latency"] else "Qwen"
    print(f"更快提供方：{faster_provider}")


def load_configs() -> list[LLMConfig]:
    """Load both provider configurations from environment variables."""
    deepseek_key = os.getenv("DEEPSEEK_API_KEY") or DEEPSEEK_HARDCODED_API_KEY
    qwen_key = os.getenv("DASHSCOPE_API_KEY") or QWEN_HARDCODED_API_KEY
    if not deepseek_key:
        raise RuntimeError("请设置环境变量 DEEPSEEK_API_KEY，或填写 DEEPSEEK_HARDCODED_API_KEY")
    if not qwen_key:
        raise RuntimeError("请设置环境变量 DASHSCOPE_API_KEY，或填写 QWEN_HARDCODED_API_KEY")

    return [
        LLMConfig(
            provider="DeepSeek",
            base_url=DEEPSEEK_BASE_URL,
            api_key=deepseek_key,
            model=DEEPSEEK_MODEL,
        ),
        LLMConfig(
            provider="Qwen",
            base_url=DASHSCOPE_BASE_URL,
            api_key=qwen_key,
            model=QWEN_MODEL,
        ),
    ]


def main() -> int:
    """Program entry point."""
    try:
        configs = load_configs()
    except RuntimeError as exc:
        print(f"配置错误：{exc}")
        print("LLM 切换验证失败")
        return 1

    results: dict[str, LLMCallResult] = {}
    for config in configs:
        print(f"\n正在调用 {config.provider}（model={config.model}）...")
        try:
            result = call_llm(config, TEST_PROMPT)
        except RuntimeError as exc:
            print(exc)
            print("LLM 切换验证失败")
            return 1
        results[config.provider] = result
        print_provider_result(config.provider, result)

    compare_results(results["DeepSeek"], results["Qwen"])
    print("LLM 切换验证通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
