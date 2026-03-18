"""Tests for the NL interpreter core module."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideagen.core.exceptions import ProviderError
from ideagen.core.nl_interpreter import NLAction, NLInterpreter, _SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# NLAction model tests
# ---------------------------------------------------------------------------


def test_nl_action_valid():
    action = NLAction(
        command="run",
        args={"domain": "software"},
        explanation="Run idea generation for software domain",
        confidence=0.95,
    )
    assert action.command == "run"
    assert action.args == {"domain": "software"}
    assert action.confidence == 0.95


def test_nl_action_default_args():
    action = NLAction(command="sources_list", args={}, explanation="List sources", confidence=0.9)
    assert action.args == {}


def test_nl_action_confidence_bounds():
    with pytest.raises(Exception):
        NLAction(command="run", args={}, explanation="test", confidence=1.5)
    with pytest.raises(Exception):
        NLAction(command="run", args={}, explanation="test", confidence=-0.1)


# ---------------------------------------------------------------------------
# NLInterpreter tests (mocked subprocess)
# ---------------------------------------------------------------------------


def _make_claude_response(action_dict: dict) -> bytes:
    """Build a Claude CLI JSON envelope containing the action."""
    envelope = {"result": json.dumps(action_dict)}
    return json.dumps(envelope).encode("utf-8")


@pytest.fixture
def interpreter():
    return NLInterpreter(timeout=10.0)


async def test_interpret_run_command(interpreter):
    action_dict = {
        "command": "run",
        "args": {"domain": "software", "source": ["hackernews"]},
        "explanation": "Run idea generation for software from HackerNews",
        "confidence": 0.95,
    }
    stdout = _make_claude_response(action_dict)

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(stdout, b""))
    mock_proc.returncode = 0

    with (
        patch("shutil.which", return_value="/usr/bin/claude"),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        result = await interpreter.interpret("find software ideas from hackernews")

    assert result.command == "run"
    assert result.args["domain"] == "software"
    assert result.confidence == 0.95


async def test_interpret_history_show(interpreter):
    action_dict = {
        "command": "history_show",
        "args": {"run_id": "latest"},
        "explanation": "Show the most recent run",
        "confidence": 0.9,
    }
    stdout = _make_claude_response(action_dict)

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(stdout, b""))
    mock_proc.returncode = 0

    with (
        patch("shutil.which", return_value="/usr/bin/claude"),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        result = await interpreter.interpret("show my last run")

    assert result.command == "history_show"
    assert result.args["run_id"] == "latest"


async def test_interpret_sources_list(interpreter):
    action_dict = {
        "command": "sources_list",
        "args": {},
        "explanation": "List available data sources",
        "confidence": 0.95,
    }
    stdout = _make_claude_response(action_dict)

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(stdout, b""))
    mock_proc.returncode = 0

    with (
        patch("shutil.which", return_value="/usr/bin/claude"),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        result = await interpreter.interpret("what sources are available?")

    assert result.command == "sources_list"
    assert result.confidence >= 0.9


async def test_interpret_config_show(interpreter):
    action_dict = {
        "command": "config_show",
        "args": {},
        "explanation": "Show current configuration",
        "confidence": 0.9,
    }
    stdout = _make_claude_response(action_dict)

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(stdout, b""))
    mock_proc.returncode = 0

    with (
        patch("shutil.which", return_value="/usr/bin/claude"),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        result = await interpreter.interpret("show my config")

    assert result.command == "config_show"


async def test_interpret_compare(interpreter):
    action_dict = {
        "command": "compare",
        "args": {"run1": "latest", "run2": "previous"},
        "explanation": "Compare the last two runs",
        "confidence": 0.85,
    }
    stdout = _make_claude_response(action_dict)

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(stdout, b""))
    mock_proc.returncode = 0

    with (
        patch("shutil.which", return_value="/usr/bin/claude"),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        result = await interpreter.interpret("compare my last two runs")

    assert result.command == "compare"
    assert result.args["run1"] == "latest"
    assert result.args["run2"] == "previous"


async def test_interpret_no_claude_cli(interpreter):
    with patch("shutil.which", return_value=None):
        with pytest.raises(ProviderError, match="Claude CLI not found"):
            await interpreter.interpret("test query")


async def test_interpret_cli_failure(interpreter):
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b"some error"))
    mock_proc.returncode = 1

    with (
        patch("shutil.which", return_value="/usr/bin/claude"),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        with pytest.raises(ProviderError, match="exited with code 1"):
            await interpreter.interpret("test query")


async def test_interpret_invalid_json_response(interpreter):
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"not json at all", b""))
    mock_proc.returncode = 0

    with (
        patch("shutil.which", return_value="/usr/bin/claude"),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        with pytest.raises(ProviderError, match="Failed to parse"):
            await interpreter.interpret("test query")


async def test_interpret_markdown_fenced_response(interpreter):
    """Claude sometimes wraps JSON in markdown code fences."""
    action_dict = {
        "command": "run",
        "args": {"domain": "business"},
        "explanation": "Run business ideas",
        "confidence": 0.8,
    }
    # Simulate raw text with markdown fences (not inside envelope)
    fenced = f"```json\n{json.dumps(action_dict)}\n```"
    envelope = {"result": fenced}
    stdout = json.dumps(envelope).encode("utf-8")

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(stdout, b""))
    mock_proc.returncode = 0

    with (
        patch("shutil.which", return_value="/usr/bin/claude"),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        result = await interpreter.interpret("find business ideas")

    assert result.command == "run"
    assert result.args["domain"] == "business"


async def test_interpret_run_with_segment(interpreter):
    action_dict = {
        "command": "run",
        "args": {"domain": "business", "segment": ["parents"]},
        "explanation": "Run business idea generation targeting parents",
        "confidence": 0.9,
    }
    stdout = _make_claude_response(action_dict)

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(stdout, b""))
    mock_proc.returncode = 0

    with (
        patch("shutil.which", return_value="/usr/bin/claude"),
        patch("asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        result = await interpreter.interpret("find business ideas targeting parents")

    assert result.command == "run"
    assert "parents" in result.args["segment"]


def test_system_prompt_contains_commands():
    """Verify the system prompt includes all expected commands."""
    assert "run" in _SYSTEM_PROMPT
    assert "history_list" in _SYSTEM_PROMPT
    assert "history_show" in _SYSTEM_PROMPT
    assert "sources_list" in _SYSTEM_PROMPT
    assert "config_show" in _SYSTEM_PROMPT
    assert "compare" in _SYSTEM_PROMPT
    assert "hackernews" in _SYSTEM_PROMPT
    assert "parents" in _SYSTEM_PROMPT


def test_system_prompt_contains_segment_ids():
    """Verify all 22 segment IDs are referenced in the prompt."""
    assert "parents" in _SYSTEM_PROMPT
    assert "pet_owners" in _SYSTEM_PROMPT
    assert "small_business" in _SYSTEM_PROMPT
    assert "knowledge_workers" in _SYSTEM_PROMPT
