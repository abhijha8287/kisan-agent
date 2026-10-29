"""In-memory stand-ins for Token Factory and Tavily, so tests never hit the network."""

from collections.abc import AsyncIterator
from typing import Any

from kisan_agent.integrations.tavily import SearchHit


class FakeChatModel:
    def __init__(
        self,
        responses: dict[str, str],
        stream_chunks: list[str] | None = None,
        fail_models: set[str] | None = None,
    ) -> None:
        self.responses = responses
        self.stream_chunks = stream_chunks or ["## Diagnosis\n", "Early blight [1]."]
        self.fail_models = fail_models or set()
        self.calls: list[tuple[str, list[dict]]] = []

    async def complete(self, model: str, messages: list[dict], **kwargs: Any) -> str:
        self.calls.append((model, messages))
        if model in self.fail_models:
            raise RuntimeError(f"{model} unavailable")
        return self.responses[model]

    async def stream(self, model: str, messages: list[dict], **kwargs: Any) -> AsyncIterator[str]:
        self.calls.append((model, messages))
        if model in self.fail_models:
            raise RuntimeError(f"{model} unavailable")
        for chunk in self.stream_chunks:
            yield chunk


class FakeSearch:
    def __init__(self, fail_queries: set[str] | None = None) -> None:
        self.fail_queries = fail_queries or set()
        self.queries: list[str] = []

    async def search(self, query: str, **kwargs: Any) -> list[SearchHit]:
        self.queries.append(query)
        if query in self.fail_queries:
            raise RuntimeError("search failed")
        slug = query.replace(" ", "-")
        return [
            SearchHit(
                title=f"Result for {query}", url=f"https://example.org/{slug}", content="x" * 900
            ),
            SearchHit(title="Shared page", url="https://example.org/shared", content="shared"),
        ]
