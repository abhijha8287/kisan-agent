"""Helpers for cleaning up raw model output."""

import json
import re
from typing import Any

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def strip_reasoning(text: str) -> str:
    """Remove `<think>...</think>` blocks that reasoning models may emit before the answer."""
    text = _THINK_BLOCK.sub("", text)
    # A response cut off mid-reasoning leaves an unclosed tag; nothing after it is an answer.
    if "<think>" in text:
        text = text.split("<think>", 1)[0]
    # Some templates emit only the closing tag.
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    return text.strip()


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse the first JSON object found in a model response.

    Raises ValueError if no valid object is present.
    """
    cleaned = _FENCE.sub("", strip_reasoning(text)).strip()
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("No JSON object in model response")

    decoder = json.JSONDecoder()
    try:
        value, _ = decoder.raw_decode(cleaned[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON in model response: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Model response JSON is not an object")
    return value


class ReasoningFilter:
    """Drops `<think>` sections from a token stream while passing the answer through.

    Tags can be split across chunks, so a short tail is held back until it can be classified.
    """

    _OPEN = "<think>"
    _CLOSE = "</think>"

    def __init__(self) -> None:
        self._buffer = ""
        self._in_reasoning = False

    def feed(self, chunk: str) -> str:
        self._buffer += chunk
        out: list[str] = []
        while True:
            tag = self._CLOSE if self._in_reasoning else self._OPEN
            idx = self._buffer.find(tag)
            if idx != -1:
                if not self._in_reasoning:
                    out.append(self._buffer[:idx])
                self._buffer = self._buffer[idx + len(tag) :]
                self._in_reasoning = not self._in_reasoning
                continue

            # Keep any suffix that could be the start of the tag we are waiting for.
            split = len(self._buffer) - _partial_suffix(self._buffer, tag)
            emit, self._buffer = self._buffer[:split], self._buffer[split:]
            if not self._in_reasoning:
                out.append(emit)
            return "".join(out)

    def flush(self) -> str:
        rest, self._buffer = self._buffer, ""
        return "" if self._in_reasoning else rest


def _partial_suffix(text: str, tag: str) -> int:
    for size in range(min(len(tag) - 1, len(text)), 0, -1):
        if tag.startswith(text[-size:]):
            return size
    return 0
