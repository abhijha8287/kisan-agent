from fastapi import Request

from kisan_agent.agent.pipeline import AdvisoryAgent
from kisan_agent.core.config import Settings


def get_agent(request: Request) -> AdvisoryAgent:
    return request.app.state.agent


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings
