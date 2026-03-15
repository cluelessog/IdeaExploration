"""Tests for ideagen.utils.text."""
from __future__ import annotations

import pytest

from ideagen.utils.text import extract_json


# ---------------------------------------------------------------------------
# Existing behaviour (fast-path: fenced blocks, raw JSON, shallow regex)
# ---------------------------------------------------------------------------


def test_extract_json_fenced_block():
    text = '```json\n{"key": "value"}\n```'
    assert extract_json(text) == '{"key": "value"}'


def test_extract_json_bare_fence():
    text = '```\n{"key": "value"}\n```'
    assert extract_json(text) == '{"key": "value"}'


def test_extract_json_raw():
    assert extract_json('{"key": "value"}') == '{"key": "value"}'


def test_extract_json_no_json_raises():
    with pytest.raises(ValueError, match="No valid JSON found"):
        extract_json("just plain text with no JSON at all")


# ---------------------------------------------------------------------------
# New: deeply nested JSON (bracket-scan fallback)
# ---------------------------------------------------------------------------


def test_extract_deeply_nested_json():
    """3+ levels of nesting that the old regex cannot match."""
    payload = '{"a": {"b": {"c": 1}}}'
    text = f"Here is the result:\n{payload}\nDone."
    result = extract_json(text)
    assert result == payload


def test_extract_json_with_prose_before_after():
    """JSON embedded between arbitrary prose should still be extracted."""
    payload = '{"status": "ok", "data": {"count": 42, "items": ["x", "y"]}}'
    text = f"Sure, here is the output: {payload} Hope that helps!"
    result = extract_json(text)
    assert result == payload


def test_extract_json_array_in_text():
    """JSON array embedded in mixed content."""
    payload = '[{"id": 1, "name": "foo"}, {"id": 2, "name": "bar"}]'
    text = f"Results follow:\n{payload}\nEnd of results."
    result = extract_json(text)
    assert result == payload


def test_extract_json_string_with_braces():
    """Strings containing literal braces must not confuse the bracket scanner."""
    payload = '{"key": "value with {braces} inside"}'
    text = f"Output: {payload}"
    result = extract_json(text)
    assert result == payload


def test_extract_deeply_nested_four_levels():
    """4 levels of nesting."""
    payload = '{"l1": {"l2": {"l3": {"l4": "deep"}}}}'
    text = f"Response: {payload}"
    result = extract_json(text)
    assert result == payload
