from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from typing import Any

from openai import APIError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError

from backend.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Async LiteLLM-compatible client."""

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
        """Call chat completion with retry and timing logs."""

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
                elapsed = time.perf_counter() - start_time
                logger.info(
                    "LLM call succeeded model=%s attempt=%s elapsed=%.2fs",
                    selected_model,
                    attempt,
                    elapsed,
                )
                return response.choices[0].message.content or ""
            except (APIError, APIStatusError, APITimeoutError, RateLimitError) as error:
                elapsed = time.perf_counter() - start_time
                last_error = error
                logger.warning(
                    "LLM call failed model=%s attempt=%s elapsed=%.2fs error=%s",
                    selected_model,
                    attempt,
                    elapsed,
                    error,
                )
                if attempt < 3:
                    await asyncio.sleep(2 ** (attempt - 1))

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
