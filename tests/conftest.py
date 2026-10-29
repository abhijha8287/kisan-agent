import json

import pytest

from kisan_agent.agent.pipeline import AdvisoryAgent, ModelRoster
from tests.fakes import FakeChatModel, FakeSearch

MODELS = ModelRoster(fast="fast-model", vision="vision-model", reasoning="reasoning-model")

DIAGNOSIS_JSON = json.dumps(
    {
        "is_plant": True,
        "crop": "Tomato",
        "condition": "Early blight",
        "confidence": "High",
        "symptoms": ["concentric brown rings on lower leaves"],
        "notes": "Check older leaves for target-like lesions.",
    }
)

INTAKE_JSON = json.dumps(
    {
        "crop": "Tomato",
        "concern": "Brown spots spreading on tomato leaves",
        "queries": {
            "treatment": "tomato early blight treatment",
            "market": "tomato mandi price Nashik 2026",
            "weather": "Nashik weather forecast next week 2026",
        },
    }
)


@pytest.fixture
def chat_model() -> FakeChatModel:
    return FakeChatModel(
        {
            MODELS.vision: f"```json\n{DIAGNOSIS_JSON}\n```",
            MODELS.fast: f"<think>planning</think>{INTAKE_JSON}",
        }
    )


@pytest.fixture
def search() -> FakeSearch:
    return FakeSearch()


@pytest.fixture
def agent(chat_model: FakeChatModel, search: FakeSearch) -> AdvisoryAgent:
    return AdvisoryAgent(llm=chat_model, search=search, models=MODELS)
