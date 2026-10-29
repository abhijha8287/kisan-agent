"""System prompts and message builders for each pipeline stage."""

import json

from kisan_agent.agent.schemas import Consultation, Diagnosis, Intake, Source

DIAGNOSE_SYSTEM = """\
You are a plant pathologist examining a photo sent by a smallholder farmer.
Base the diagnosis only on what is visible, and use the confidence field to express doubt.

Respond with a single JSON object and nothing else:
{
  "is_plant": true or false,
  "crop": "crop name, or null if unclear",
  "condition": "the specific name of the most likely disease, pest or deficiency (for example 'Early blight'), 'healthy', or 'uncertain'",
  "confidence": "low" | "medium" | "high",
  "symptoms": ["short description of each visible symptom"],
  "notes": "one sentence on what would confirm the diagnosis"
}"""

UNDERSTAND_SYSTEM = """\
You are the intake step of an agricultural advisory service for smallholder farmers.
The farmer may write in any language. Work out what they need and plan web searches
that will give an advisor current, local facts.

Respond with a single JSON object and nothing else:
{
  "crop": "crop name in English, or null",
  "concern": "one sentence in English describing the farmer's problem",
  "queries": {
    "treatment": "search query for recommended treatment or management, in English",
    "market": "search query for the current mandi or market price of the crop near the location, or null if no crop is known",
    "weather": "search query for the weather forecast for the coming week at the location, or null if no location is given"
  }
}

Keep each query under 15 words. Include the location and the current year in the
market and weather queries."""

ADVISE_SYSTEM = """\
You are KisanAgent, a practical field advisor for smallholder farmers.

Write the whole answer in {language}, in plain words a farmer with little formal
schooling understands. Use these markdown sections, with headings translated into {language}:

## Diagnosis
## What to do now
## Cost and market
## Weather watch
## When to get expert help

Rules:
- Under "What to do now", give numbered steps. For any chemical, give the active
  ingredient, dose per litre of water, and timing, and remind the farmer to read the
  label and wear gloves and a mask. Prefer low-cost and integrated pest management
  options first.
- State prices, weather and scheme details only if they appear in the research notes,
  and cite them with the note number in square brackets, like [2]. Quote prices only for
  the farmer's own crop, never for other produce listed on the same page. If the notes have
  no usable price or forecast, say so plainly instead of estimating.
- Tie the advice together: for example, delay spraying if rain is forecast, or suggest
  harvesting early if prices are high and the crop is at risk.
- If the photo diagnosis has low confidence or the image is not a plant, say what
  photo would help and give only safe, general advice.
- Keep it under 350 words. No preamble, no closing pleasantries."""


def diagnose_messages(consultation: Consultation) -> list[dict]:
    assert consultation.image is not None
    return [
        {"role": "system", "content": DIAGNOSE_SYSTEM},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"Farmer's question: {consultation.question}"},
                {"type": "image_url", "image_url": {"url": consultation.image.data_url}},
            ],
        },
    ]


def understand_messages(
    consultation: Consultation, diagnosis: Diagnosis | None, year: int
) -> list[dict]:
    lines = [
        f"Question: {consultation.question}",
        f"Location: {consultation.location or 'not given'}",
        f"Current year: {year}",
    ]
    if diagnosis is not None:
        lines.append(f"Photo diagnosis: {diagnosis.model_dump_json()}")
    return [
        {"role": "system", "content": UNDERSTAND_SYSTEM},
        {"role": "user", "content": "\n".join(lines)},
    ]


def advise_messages(
    consultation: Consultation,
    intake: Intake,
    diagnosis: Diagnosis | None,
    sources: list[Source],
) -> list[dict]:
    notes = "\n\n".join(
        f"[{source.id}] ({source.topic}) {source.title}\n{source.url}\n{source.snippet}"
        for source in sources
    )
    context = {
        "question": consultation.question,
        "location": consultation.location or "not given",
        "crop": intake.crop,
        "concern": intake.concern,
        "photo_diagnosis": diagnosis.model_dump() if diagnosis else "no photo provided",
    }
    return [
        {"role": "system", "content": ADVISE_SYSTEM.format(language=consultation.language)},
        {
            "role": "user",
            "content": (
                f"Farmer context:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
                f"Research notes:\n{notes or 'No research results were found.'}"
            ),
        },
    ]
