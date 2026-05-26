from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from openai import APIError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError

from backend.config import get_settings

logger = logging.getLogger(__name__)

# Global concurrency limiter: max 5 concurrent LLM calls
_semaphore = asyncio.Semaphore(5)


@dataclass
class TokenStats:
    """Token 消耗统计"""
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_reasoning_tokens: int = 0
    total_elapsed_ms: float = 0.0
    errors: int = 0
    by_model: dict[str, dict[str, int]] = field(default_factory=dict)

    def record(self, model: str, input_tokens: int, output_tokens: int, reasoning_tokens: int, elapsed_ms: float) -> None:
        self.total_calls += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_reasoning_tokens += reasoning_tokens
        self.total_elapsed_ms += elapsed_ms
        if model not in self.by_model:
            self.by_model[model] = {"calls": 0, "input": 0, "output": 0, "reasoning": 0}
        self.by_model[model]["calls"] += 1
        self.by_model[model]["input"] += input_tokens
        self.by_model[model]["output"] += output_tokens
        self.by_model[model]["reasoning"] += reasoning_tokens

    def record_error(self) -> None:
        self.errors += 1

    def to_dict(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_reasoning_tokens": self.total_reasoning_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens + self.total_reasoning_tokens,
            "total_elapsed_ms": round(self.total_elapsed_ms, 1),
            "avg_elapsed_ms": round(self.total_elapsed_ms / max(self.total_calls, 1), 1),
            "errors": self.errors,
            "by_model": self.by_model,
        }


# 全局 token 统计
_token_stats = TokenStats()


def get_token_stats() -> TokenStats:
    """获取全局 token 统计"""
    return _token_stats


class LLMClient:
    """Async LiteLLM-compatible client with concurrency control and smart retry."""

    def __init__(self) -> None:
        settings = get_settings()
        self.default_model = settings.LITELLM_MODEL
        self.client = AsyncOpenAI(
            api_key=settings.LITELLM_API_KEY,
            base_url=settings.LITELLM_BASE_URL,
        )

    async def chat_completion(
        self,
        messages: Sequence[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> str:
        """Call chat completion with concurrency control, smart retry, and token tracking."""

        async with _semaphore:
            return await self._call_with_retry(messages, model, temperature, max_tokens)

    async def _call_with_retry(
        self,
        messages: Sequence[dict[str, str]],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> str:
        selected_model = model or self.default_model
        last_error: Exception | None = None

        for attempt in range(1, 4):
            start_time = time.perf_counter()
            try:
                response = await self.client.chat.completions.create(
                    model=selected_model,
                    messages=list(messages),  # type: ignore[arg-type]
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                usage = response.usage
                input_tokens = usage.prompt_tokens if usage else 0
                output_tokens = usage.completion_tokens if usage else 0
                reasoning_tokens = 0
                if usage and hasattr(usage, 'completion_tokens_details') and usage.completion_tokens_details:
                    reasoning_tokens = getattr(usage.completion_tokens_details, 'reasoning_tokens', 0) or 0

                _token_stats.record(selected_model, input_tokens, output_tokens, reasoning_tokens, elapsed_ms)

                logger.info(
                    "LLM call model=%s attempt=%s elapsed=%.0fms tokens=%d+%d+%d",
                    selected_model, attempt, elapsed_ms, input_tokens, output_tokens, reasoning_tokens,
                )

                msg = response.choices[0].message
                content = msg.content
                # 推理模型（如 mimo-v2.5-pro）可能把内容放在 reasoning_content 中
                if not content and hasattr(msg, "reasoning_content"):
                    content = msg.reasoning_content
                return content or ""
            except RateLimitError as error:
                # 429: rate limited — longer backoff with jitter
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                last_error = error
                _token_stats.record_error()
                logger.warning(
                    "LLM rate-limited model=%s attempt=%s elapsed=%.0fms",
                    selected_model, attempt, elapsed_ms,
                )
                if attempt < 3:
                    backoff = 2 ** (attempt + 1) + random.uniform(0, 1)
                    await asyncio.sleep(backoff)
            except APIStatusError as error:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                last_error = error
                _token_stats.record_error()
                # 4xx client errors (except 429): don't retry
                if 400 <= error.status_code < 500:
                    logger.error(
                        "LLM client error model=%s status=%s — not retrying",
                        selected_model, error.status_code,
                    )
                    raise
                # 5xx server errors: quick retry
                logger.warning(
                    "LLM server error model=%s attempt=%s status=%s elapsed=%.0fms",
                    selected_model, attempt, error.status_code, elapsed_ms,
                )
                if attempt < 3:
                    await asyncio.sleep(1.0 + random.uniform(0, 0.5))
            except (APIError, APITimeoutError) as error:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                last_error = error
                _token_stats.record_error()
                logger.warning(
                    "LLM call failed model=%s attempt=%s elapsed=%.0fms error=%s",
                    selected_model, attempt, elapsed_ms, error,
                )
                if attempt < 3:
                    await asyncio.sleep(2 ** (attempt - 1) + random.uniform(0, 0.5))

        assert last_error is not None
        raise last_error


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Return a process-local LLM client singleton."""

    global _client
    if _client is None:
        _client = LLMClient()
    return _client


async def chat_completion(
    messages: Sequence[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4000,
) -> str:
    """Convenience wrapper for the singleton LLM client."""

    return await get_llm_client().chat_completion(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
