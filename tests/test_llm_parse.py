import pytest
from backend.llm import parse_json


def test_plain():
    assert parse_json('{"a": 1}') == {"a": 1}


def test_fenced_with_chatter():
    assert parse_json('Sure!\n```json\n{"score": 7}\n```\nHope it helps') == {"score": 7}


def test_invalid():
    with pytest.raises(ValueError):
        parse_json("no json here")
