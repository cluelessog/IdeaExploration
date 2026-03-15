"""Tests for ASCII-safe spinner selection in PipelineEventRenderer."""
from __future__ import annotations

import asyncio
import sys
from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console
from rich.progress import SpinnerColumn

from ideagen.cli.formatters import PipelineEventRenderer, _get_spinner_column
from ideagen.core.models import StageStarted, StageCompleted
from tests.conftest import _event_stream


def test_spinner_ascii_on_non_utf8():
    """When stdout encoding is cp1252, _get_spinner_column returns an ASCII spinner."""
    mock_stdout = type("MockStdout", (), {"encoding": "cp1252"})()
    with patch.object(sys, "stdout", mock_stdout):
        col = _get_spinner_column()
    assert isinstance(col, SpinnerColumn)
    # The "line" spinner uses only ASCII characters (-/|\\)
    assert col.spinner.name == "line"


def test_spinner_unicode_on_utf8():
    """When stdout encoding is utf-8, _get_spinner_column returns the default spinner."""
    mock_stdout = type("MockStdout", (), {"encoding": "utf-8"})()
    with patch.object(sys, "stdout", mock_stdout):
        col = _get_spinner_column()
    assert isinstance(col, SpinnerColumn)
    # Default spinner is "dots" (Unicode-based)
    assert col.spinner.name != "line"


def test_renderer_does_not_crash_ascii():
    """PipelineEventRenderer with ASCII spinner can process a basic event without error."""
    buf = StringIO()
    con = Console(file=buf, force_terminal=True, highlight=False)

    mock_stdout = type("MockStdout", (), {"encoding": "cp1252"})()
    with patch.object(sys, "stdout", mock_stdout):
        renderer = PipelineEventRenderer(console=con)

    events = _event_stream(
        StageStarted(stage="collect"),
        StageCompleted(stage="collect", duration_ms=50),
    )
    # Must not raise even on a simulated non-UTF-8 environment
    result = asyncio.run(renderer.render(events))
    assert result is None
