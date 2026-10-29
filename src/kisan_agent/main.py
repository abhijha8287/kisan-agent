"""Application factory. Run with `uvicorn kisan_agent.main:create_app --factory`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from kisan_agent import __version__
from kisan_agent.agent.pipeline import AdvisoryAgent, ModelRoster
from kisan_agent.api.routes import router
from kisan_agent.core.config import Settings, get_settings
from kisan_agent.core.logging import configure_logging
from kisan_agent.integrations.tavily import TavilyClient
from kisan_agent.integrations.token_factory import TokenFactoryClient


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        llm = TokenFactoryClient(
            api_key=settings.nebius_api_key.get_secret_value(),
            base_url=settings.nebius_base_url,
            timeout_s=settings.request_timeout_s,
        )
        search = TavilyClient(
            api_key=(
                settings.tavily_api_key.get_secret_value() if settings.tavily_api_key else None
            ),
            timeout_s=settings.request_timeout_s,
        )
        app.state.agent = AdvisoryAgent(
            llm=llm,
            search=search,
            models=ModelRoster(
                fast=settings.model_fast,
                vision=settings.model_vision,
                reasoning=settings.model_reasoning,
            ),
            results_per_query=settings.search_results_per_query,
        )
        try:
            yield
        finally:
            await llm.aclose()
            await search.aclose()

    app = FastAPI(title="KisanAgent", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.include_router(router, prefix="/api")
    app.mount("/", StaticFiles(directory=settings.web_dir, html=True), name="web")
    return app
