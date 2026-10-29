"""Minimal async client for the Tavily search API."""

from dataclasses import dataclass
from typing import Literal

import httpx

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    content: str


class TavilyClient:
    def __init__(self, api_key: str | None, timeout_s: float) -> None:
        # Without a key, Tavily serves search in a rate-limited keyless mode.
        headers = (
            {"Authorization": f"Bearer {api_key}"}
            if api_key
            else {"X-Tavily-Access-Mode": "keyless"}
        )
        self._http = httpx.AsyncClient(timeout=timeout_s, headers=headers)

    async def search(
        self,
        query: str,
        *,
        max_results: int = 4,
        topic: Literal["general", "news"] = "general",
    ) -> list[SearchHit]:
        response = await self._http.post(
            TAVILY_SEARCH_URL,
            json={
                "query": query,
                "max_results": max_results,
                "topic": topic,
                "search_depth": "basic",
            },
        )
        response.raise_for_status()
        return [
            SearchHit(title=item.get("title", ""), url=item["url"], content=item.get("content", ""))
            for item in response.json().get("results", [])
            if item.get("url")
        ]

    async def aclose(self) -> None:
        await self._http.aclose()
