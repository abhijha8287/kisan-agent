from kisan_agent.agent.pipeline import AdvisoryAgent
from kisan_agent.agent.schemas import AgentEvent, Consultation, ImageInput
from tests.conftest import MODELS
from tests.fakes import FakeChatModel, FakeSearch

PHOTO = ImageInput(data=b"\xff\xd8fake-jpeg", media_type="image/jpeg")


async def collect(agent: AdvisoryAgent, consultation: Consultation) -> list[AgentEvent]:
    return [event async for event in agent.run(consultation)]


def steps(events: list[AgentEvent]) -> dict[str, str]:
    """Final status of each pipeline step."""
    return {e.data["name"]: e.data["status"] for e in events if e.type == "step"}


async def test_full_consultation_routes_each_stage_to_its_model(agent, chat_model, search):
    events = await collect(
        agent,
        Consultation(question="Brown spots?", language="Hindi", location="Nashik", image=PHOTO),
    )

    assert steps(events) == {
        "diagnose": "done",
        "understand": "done",
        "research": "done",
        "advise": "done",
    }
    assert [model for model, _ in chat_model.calls] == [
        MODELS.vision,
        MODELS.fast,
        MODELS.reasoning,
    ]
    assert len(search.queries) == 3

    diagnosis = next(e for e in events if e.type == "diagnosis").data
    assert diagnosis["condition"] == "Early blight"
    assert diagnosis["confidence"] == "high"

    sources = next(e for e in events if e.type == "sources").data["sources"]
    assert [s["id"] for s in sources] == list(range(1, len(sources) + 1))
    assert len({s["url"] for s in sources}) == len(sources), "duplicate URLs should be merged"
    assert all(len(s["snippet"]) <= 600 for s in sources)

    advice = "".join(e.data["text"] for e in events if e.type == "token")
    assert "Early blight" in advice
    assert events[-1].type == "done"


async def test_advice_prompt_uses_requested_language_and_numbered_notes(agent, chat_model):
    await collect(agent, Consultation(question="Brown spots?", language="Marathi", location="Pune"))

    _, messages = chat_model.calls[-1]
    assert "Marathi" in messages[0]["content"]
    assert "[1]" in messages[1]["content"]


async def test_without_photo_diagnosis_is_skipped(agent, chat_model):
    events = await collect(agent, Consultation(question="When to sow wheat?", language="English"))

    assert steps(events)["diagnose"] == "skipped"
    assert MODELS.vision not in [model for model, _ in chat_model.calls]
    assert not any(e.type == "diagnosis" for e in events)


async def test_failed_vision_and_intake_fall_back_without_stopping(search):
    llm = FakeChatModel({}, fail_models={MODELS.vision, MODELS.fast})
    agent = AdvisoryAgent(llm=llm, search=search, models=MODELS)

    events = await collect(
        agent,
        Consultation(question="Leaves curling", language="English", location="Indore", image=PHOTO),
    )

    status = steps(events)
    assert status["diagnose"] == "failed"
    assert status["understand"] == "failed"
    assert status["advise"] == "done"
    assert search.queries, "fallback intake should still produce search queries"
    assert events[-1].type == "done"


async def test_partial_search_failure_keeps_other_results(chat_model):
    search = FakeSearch(fail_queries={"tomato mandi price Nashik 2026"})
    agent = AdvisoryAgent(llm=chat_model, search=search, models=MODELS)

    events = await collect(
        agent, Consultation(question="Spots", language="English", location="Nashik")
    )

    sources = next(e for e in events if e.type == "sources").data["sources"]
    assert sources
    assert {s["topic"] for s in sources} == {"treatment", "weather"}


async def test_reasoning_failure_emits_error(search, chat_model):
    chat_model.fail_models = {MODELS.reasoning}
    agent = AdvisoryAgent(llm=chat_model, search=search, models=MODELS)

    events = await collect(agent, Consultation(question="Spots", language="English"))

    assert steps(events)["advise"] == "failed"
    assert events[-1].type == "error"
