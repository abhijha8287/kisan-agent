"""Server-sent events encoding for agent progress."""

import json
from collections.abc import AsyncIterator

from kisan_agent.agent.schemas import AgentEvent


def encode_event(event: AgentEvent) -> str:
    payload = json.dumps(event.data, ensure_ascii=False)
    return f"event: {event.type}\ndata: {payload}\n\n"


async def event_stream(events: AsyncIterator[AgentEvent]) -> AsyncIterator[str]:
    async for event in events:
        yield encode_event(event)
