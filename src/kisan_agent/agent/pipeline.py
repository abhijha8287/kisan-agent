"""The advisory pipeline: diagnose -> understand -> research -> advise.

Each stage is routed to the model best suited to it and reports progress as events,
so the UI can show which model did what and how long it took.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from kisan_agent.agent import prompts
from kisan_agent.agent.schemas import (
    AgentEvent,
    Consultation,
    Diagnosis,
    Intake,
    SearchPlan,
    Source,
    SourceTopic,
    StepName,
    StepStatus,
)
from kisan_agent.core.text import extract_json_object
from kisan_agent.integrations.tavily import SearchHit

logger = logging.getLogger(__name__)

SNIPPET_CHARS = 600


class ChatModel(Protocol):
    async def complete(self, model: str, messages: list[dict], **kwargs: Any) -> str: ...

    def stream(self, model: str, messages: list[dict], **kwargs: Any) -> AsyncIterator[str]: ...


class WebSearch(Protocol):
    async def search(self, query: str, **kwargs: Any) -> list[SearchHit]: ...


@dataclass(frozen=True)
class ModelRoster:
    fast: str
    vision: str
    reasoning: str


class AdvisoryAgent:
    def __init__(
        self,
        llm: ChatModel,
        search: WebSearch,
        models: ModelRoster,
        results_per_query: int = 4,
    ) -> None:
        self._llm = llm
        self._search = search
        self._models = models
        self._results_per_query = results_per_query

    async def run(self, consultation: Consultation) -> AsyncIterator[AgentEvent]:
        started = time.perf_counter()

        diagnosis: Diagnosis | None = None
        if consultation.image is None:
            yield _step("diagnose", "skipped", detail="No photo provided")
        else:
            yield _step("diagnose", "running", model=self._models.vision)
            t0 = time.perf_counter()
            try:
                diagnosis = await self._diagnose(consultation)
            except Exception:
                logger.exception("Photo diagnosis failed")
                yield _step(
                    "diagnose",
                    "failed",
                    model=self._models.vision,
                    detail="Could not read the photo. Continuing with the question only.",
                    elapsed_ms=_ms_since(t0),
                )
            else:
                yield _step(
                    "diagnose",
                    "done",
                    model=self._models.vision,
                    detail=f"{diagnosis.condition} ({diagnosis.confidence} confidence)",
                    elapsed_ms=_ms_since(t0),
                )
                yield AgentEvent("diagnosis", diagnosis.model_dump())

        yield _step("understand", "running", model=self._models.fast)
        t0 = time.perf_counter()
        try:
            intake = await self._understand(consultation, diagnosis)
            yield _step(
                "understand",
                "done",
                model=self._models.fast,
                detail=intake.concern,
                elapsed_ms=_ms_since(t0),
            )
        except Exception:
            logger.exception("Intake failed; falling back to the raw question")
            intake = _fallback_intake(consultation, diagnosis)
            yield _step(
                "understand",
                "failed",
                model=self._models.fast,
                detail="Used the question as written.",
                elapsed_ms=_ms_since(t0),
            )
        yield AgentEvent("intake", intake.model_dump())

        yield _step("research", "running", model="Tavily")
        t0 = time.perf_counter()
        sources = await self._research(intake.queries)
        yield _step(
            "research",
            "done" if sources else "failed",
            model="Tavily",
            detail=f"{len(sources)} sources found" if sources else "No sources found",
            elapsed_ms=_ms_since(t0),
        )
        yield AgentEvent("sources", {"sources": [s.model_dump() for s in sources]})

        yield _step("advise", "running", model=self._models.reasoning)
        t0 = time.perf_counter()
        try:
            messages = prompts.advise_messages(consultation, intake, diagnosis, sources)
            async for text in self._llm.stream(self._models.reasoning, messages):
                yield AgentEvent("token", {"text": text})
        except Exception:
            logger.exception("Advice generation failed")
            yield _step("advise", "failed", model=self._models.reasoning, elapsed_ms=_ms_since(t0))
            yield AgentEvent(
                "error", {"message": "The advisor model did not respond. Please try again."}
            )
            return
        yield _step("advise", "done", model=self._models.reasoning, elapsed_ms=_ms_since(t0))
        yield AgentEvent("done", {"elapsed_ms": _ms_since(started)})

    async def _diagnose(self, consultation: Consultation) -> Diagnosis:
        raw = await self._llm.complete(
            self._models.vision, prompts.diagnose_messages(consultation), max_tokens=4096
        )
        return Diagnosis.model_validate(extract_json_object(raw))

    async def _understand(self, consultation: Consultation, diagnosis: Diagnosis | None) -> Intake:
        messages = prompts.understand_messages(consultation, diagnosis, date.today().year)
        raw = await self._llm.complete(self._models.fast, messages, max_tokens=2048)
        return Intake.model_validate(extract_json_object(raw))

    async def _research(self, plan: SearchPlan) -> list[Source]:
        jobs: list[tuple[SourceTopic, str]] = [
            (topic, query)
            for topic, query in (
                ("treatment", plan.treatment),
                ("market", plan.market),
                ("weather", plan.weather),
            )
            if query
        ]
        results = await asyncio.gather(
            *(self._search.search(query, max_results=self._results_per_query) for _, query in jobs),
            return_exceptions=True,
        )

        sources: list[Source] = []
        seen: set[str] = set()
        for (topic, query), result in zip(jobs, results, strict=True):
            if isinstance(result, BaseException):
                logger.warning("Search failed for %r: %s", query, result)
                continue
            for hit in result:
                if hit.url in seen:
                    continue
                seen.add(hit.url)
                sources.append(
                    Source(
                        id=len(sources) + 1,
                        topic=topic,
                        title=hit.title or hit.url,
                        url=hit.url,
                        snippet=hit.content[:SNIPPET_CHARS],
                    )
                )
        return sources


def _fallback_intake(consultation: Consultation, diagnosis: Diagnosis | None) -> Intake:
    crop = diagnosis.crop if diagnosis else None
    subject = " ".join(filter(None, [crop, diagnosis.condition if diagnosis else None]))
    location = consultation.location
    return Intake(
        crop=crop,
        concern=consultation.question,
        queries=SearchPlan(
            treatment=f"{subject or consultation.question} treatment for farmers",
            market=f"{crop} mandi price {location}" if crop and location else None,
            weather=f"weather forecast next 7 days {location}" if location else None,
        ),
    )


def _step(
    name: StepName,
    status: StepStatus,
    *,
    model: str | None = None,
    detail: str | None = None,
    elapsed_ms: int | None = None,
) -> AgentEvent:
    return AgentEvent(
        "step",
        {
            "name": name,
            "status": status,
            "model": model,
            "detail": detail,
            "elapsed_ms": elapsed_ms,
        },
    )


def _ms_since(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)
