"""Client for Nebius Token Factory, which exposes an OpenAI-compatible API."""

from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from kisan_agent.core.text import ReasoningFilter, strip_reasoning

Message = dict[str, Any]


class TokenFactoryClient:
    def __init__(self, api_key: str, base_url: str, timeout_s: float) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout_s)

    async def complete(
        self,
        model: str,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return strip_reasoning(response.choices[0].message.content or "")

    async def stream(
        self,
        model: str,
        messages: list[Message],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        reasoning = ReasoningFilter()
        async for chunk in response:
            if not chunk.choices:
                continue
            text = reasoning.feed(chunk.choices[0].delta.content or "")
            if text:
                yield text
        tail = reasoning.flush()
        if tail:
            yield tail

    async def aclose(self) -> None:
        await self._client.close()
