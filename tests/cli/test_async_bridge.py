"""Tests for ideagen.cli.async_bridge.run_async."""
from __future__ import annotations

import asyncio
import signal
import sys
from unittest.mock import MagicMock, patch

import pytest

from ideagen.cli.async_bridge import run_async
from ideagen.core.models import CancellationToken


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _raise_keyboard_interrupt():
    raise KeyboardInterrupt


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_run_async_returns_coroutine_result() -> None:
    """run_async returns the value produced by the coroutine."""
    async def coro():
        return 42

    assert run_async(coro()) == 42


def test_run_async_without_cancellation_token() -> None:
    """run_async works correctly without a cancellation token."""
    async def coro():
        return "hello"

    result = run_async(coro())
    assert result == "hello"


def test_run_async_keyboard_interrupt_with_token() -> None:
    """run_async returns None and cancels the token on KeyboardInterrupt."""
    token = CancellationToken()

    result = run_async(_raise_keyboard_interrupt(), cancellation_token=token)

    assert result is None
    assert token.is_cancelled


def test_run_async_keyboard_interrupt_without_token() -> None:
    """run_async returns None on KeyboardInterrupt when no token is provided."""
    result = run_async(_raise_keyboard_interrupt())
    assert result is None


def test_run_async_closes_loop() -> None:
    """run_async always closes the event loop after completion."""
    mock_loop = MagicMock()
    mock_loop.run_until_complete.return_value = 99
    mock_loop.add_signal_handler = MagicMock()

    async def simple():
        return 99

    with patch("asyncio.new_event_loop", return_value=mock_loop):
        result = run_async(simple())

    mock_loop.close.assert_called_once()
    assert result == 99


def test_run_async_with_token_on_non_win32() -> None:
    """run_async registers SIGINT handler when platform is not win32 and token is provided."""
    mock_loop = MagicMock()
    mock_loop.run_until_complete.return_value = "done"

    token = CancellationToken()

    async def simple():
        return "done"

    with patch("asyncio.new_event_loop", return_value=mock_loop), \
         patch("ideagen.cli.async_bridge.sys") as mock_sys:
        mock_sys.platform = "linux"
        result = run_async(simple(), cancellation_token=token)

    mock_loop.add_signal_handler.assert_called_once()
    registered_signum = mock_loop.add_signal_handler.call_args[0][0]
    assert registered_signum == signal.SIGINT
    assert result == "done"
