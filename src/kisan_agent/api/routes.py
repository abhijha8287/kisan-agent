from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from kisan_agent import __version__
from kisan_agent.agent.languages import LANGUAGE_NAMES, SUPPORTED_LANGUAGES
from kisan_agent.agent.pipeline import AdvisoryAgent
from kisan_agent.agent.schemas import Consultation, ImageInput
from kisan_agent.api.dependencies import get_agent, get_app_settings
from kisan_agent.api.sse import event_stream
from kisan_agent.core.config import Settings

ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/meta")
async def meta(settings: Annotated[Settings, Depends(get_app_settings)]) -> dict:
    return {
        "languages": [
            {"name": lang.name, "native_name": lang.native_name, "speech_code": lang.speech_code}
            for lang in SUPPORTED_LANGUAGES
        ],
        "models": {
            "fast": settings.model_fast,
            "vision": settings.model_vision,
            "reasoning": settings.model_reasoning,
        },
    }


@router.post("/consult")
async def consult(
    agent: Annotated[AdvisoryAgent, Depends(get_agent)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    question: Annotated[str, Form(min_length=3, max_length=1000)],
    language: Annotated[str, Form()] = "English",
    location: Annotated[str, Form(max_length=120)] = "",
    image: Annotated[UploadFile | None, File()] = None,
) -> StreamingResponse:
    if language not in LANGUAGE_NAMES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unsupported language: {language}"
        )

    consultation = Consultation(
        question=question.strip(),
        language=language,
        location=location.strip() or None,
        image=await _read_image(image, settings.max_image_bytes) if image else None,
    )
    return StreamingResponse(
        event_stream(agent.run(consultation)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _read_image(upload: UploadFile, max_bytes: int) -> ImageInput | None:
    if not upload.filename and not upload.size:
        return None
    if upload.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Photo must be a JPEG, PNG or WebP image."
        )
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"Photo is larger than {max_bytes // (1024 * 1024)} MB.",
        )
    if not data:
        return None
    return ImageInput(data=data, media_type=upload.content_type)
