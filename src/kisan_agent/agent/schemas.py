"""Domain models passed between the pipeline stages."""

import base64
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


@dataclass(frozen=True)
class ImageInput:
    data: bytes
    media_type: str

    @property
    def data_url(self) -> str:
        return f"data:{self.media_type};base64,{base64.b64encode(self.data).decode()}"


@dataclass(frozen=True)
class Consultation:
    question: str
    language: str
    location: str | None = None
    image: ImageInput | None = None


class Diagnosis(BaseModel):
    is_plant: bool = True
    crop: str | None = None
    condition: str = "uncertain"
    confidence: Literal["low", "medium", "high"] = "low"
    symptoms: list[str] = Field(default_factory=list)
    notes: str = ""

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalise_confidence(cls, value: Any) -> str:
        value = str(value).strip().lower()
        return value if value in {"low", "medium", "high"} else "low"


class SearchPlan(BaseModel):
    treatment: str | None = None
    market: str | None = None
    weather: str | None = None


class Intake(BaseModel):
    crop: str | None = None
    concern: str
    queries: SearchPlan


SourceTopic = Literal["treatment", "market", "weather"]


class Source(BaseModel):
    id: int
    topic: SourceTopic
    title: str
    url: str
    snippet: str


EventType = Literal["step", "diagnosis", "intake", "sources", "token", "done", "error"]
StepName = Literal["diagnose", "understand", "research", "advise"]
StepStatus = Literal["running", "done", "skipped", "failed"]


@dataclass(frozen=True)
class AgentEvent:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
