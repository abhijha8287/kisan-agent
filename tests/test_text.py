import pytest

from kisan_agent.core.text import ReasoningFilter, extract_json_object, strip_reasoning


def test_strip_reasoning_removes_think_blocks():
    assert strip_reasoning("<think>hmm</think>\nAnswer") == "Answer"


def test_strip_reasoning_handles_orphan_closing_tag():
    assert strip_reasoning("reasoning text</think>Answer") == "Answer"


def test_extract_json_object_from_fenced_block():
    assert extract_json_object('Here:\n```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_object_ignores_trailing_text():
    assert extract_json_object('{"a": {"b": 2}} and more {') == {"a": {"b": 2}}


@pytest.mark.parametrize("raw", ["no json here", "[1, 2]", '{"a": '])
def test_extract_json_object_rejects_invalid(raw):
    with pytest.raises(ValueError):
        extract_json_object(raw)


def test_reasoning_filter_handles_tags_split_across_chunks():
    stream = ["Hel", "lo <thi", "nk>secret", " plan</th", "ink> world"]
    reasoning = ReasoningFilter()
    out = "".join(reasoning.feed(chunk) for chunk in stream) + reasoning.flush()
    assert out == "Hello  world"


def test_reasoning_filter_passes_plain_text_and_lone_angle_brackets():
    reasoning = ReasoningFilter()
    out = reasoning.feed("dose < 2 ml") + reasoning.feed(" per litre <") + reasoning.flush()
    assert out == "dose < 2 ml per litre <"
