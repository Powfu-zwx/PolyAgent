"""DeepSeek API verification script using the OpenAI Python SDK."""

from __future__ import annotations

import os
import time
from typing import Optional

BASE_URL: str = "https://api.deepseek.com"
MODEL: str = "deepseek-chat"
PROMPT: str = "请用一句话介绍什么是多Agent系统"
HARDCODED_API_KEY: str = "sk-4c06530e91264ade825c3dc69337cbd7"


def _to_int(value: Optional[int]) -> int:
    """Convert an optional integer to a concrete integer."""
    return int(value) if value is not None else 0


def run_api_check() -> bool:
    """Run a single DeepSeek API request and print verification details."""
    try:
        from openai import (
            APIConnectionError,
            APIStatusError,
            AuthenticationError,
            OpenAI,
            OpenAIError,
            RateLimitError,
        )
    except ImportError:
        print("依赖错误：未安装 openai，请先执行 `pip install openai`。")
        return False

    api_key: Optional[str] = os.getenv("DEEPSEEK_API_KEY") or HARDCODED_API_KEY
    if not api_key:
        print("错误：请设置环境变量 DEEPSEEK_API_KEY，或在 HARDCODED_API_KEY 中填写。")
        return False

    client = OpenAI(api_key=api_key, base_url=BASE_URL)

    started_at = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": PROMPT}],
        )
    except APIConnectionError as exc:
        print(f"网络错误：无法连接 DeepSeek API。详情：{exc}")
        return False
    except AuthenticationError as exc:
        print(f"认证错误：API Key 无效或权限不足。详情：{exc}")
        return False
    except RateLimitError as exc:
        print(f"速率限制：请求过于频繁，请稍后重试。详情：{exc}")
        return False
    except APIStatusError as exc:
        print(f"接口状态错误：HTTP {exc.status_code}。详情：{exc}")
        return False
    except OpenAIError as exc:
        print(f"OpenAI SDK 错误：{exc}")
        return False
    except Exception as exc:  # pragma: no cover - unexpected runtime issue
        print(f"未知错误：{exc}")
        return False
    elapsed_seconds = time.perf_counter() - started_at

    text: str = response.choices[0].message.content or ""
    usage = response.usage
    prompt_tokens: int = _to_int(getattr(usage, "prompt_tokens", None))
    completion_tokens: int = _to_int(getattr(usage, "completion_tokens", None))
    total_tokens: int = _to_int(getattr(usage, "total_tokens", None))

    print("模型返回的完整文本：")
    print(text)
    print(
        "本次请求消耗的 tokens："
        f"prompt_tokens={prompt_tokens}, "
        f"completion_tokens={completion_tokens}, "
        f"total_tokens={total_tokens}"
    )
    print(f"请求耗时（秒）：{elapsed_seconds:.3f}")
    return True


def main() -> int:
    """Program entry point."""
    ok = run_api_check()
    print("API 验证通过" if ok else "API 验证失败")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
