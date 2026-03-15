"""Tests for ideagen.cli.async_bridge.run_async."""
from __future__ import annotations

import asyncio
import signal
import sys
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from ideagen.cli.async_bridge import run_async
from ideagen.core.models import CancellationToken, PipelineComplete
from tests.conftest import make_run


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


# ---------------------------------------------------------------------------
# Async generator cleanup tests (Audit Finding #3)
# ---------------------------------------------------------------------------


def test_run_async_calls_shutdown_asyncgens() -> None:
    """run_async calls loop.shutdown_asyncgens() before loop.close() in the finally block."""
    mock_loop = MagicMock()
    mock_loop.run_until_complete.return_value = "ok"

    async def simple():
        return "ok"

    with patch("asyncio.new_event_loop", return_value=mock_loop):
        run_async(simple())

    # shutdown_asyncgens must be called, and close must come after it
    mock_loop.run_until_complete.assert_called()
    calls = mock_loop.run_until_complete.call_args_list
    # The last run_until_complete call (in finally) should be shutdown_asyncgens
    assert len(calls) >= 2, "Expected at least 2 run_until_complete calls (coro + shutdown_asyncgens)"
    mock_loop.close.assert_called_once()


class _SpyAsyncGen:
    """Wraps an async generator and tracks whether aclose() was called."""

    def __init__(self, inner):
        self._inner = inner
        self.aclose_called = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self._inner.__anext__()

    async def aclose(self):
        self.aclose_called = True
        return await self._inner.aclose()


async def test_consume_pipeline_closes_generator_async() -> None:
    """_consume_pipeline closes the generator after PipelineComplete is received."""
    from ideagen.cli.commands.run import _consume_pipeline_for_test

    async def gen():
        yield PipelineComplete(result=make_run())

    spy = _SpyAsyncGen(gen())
    await _consume_pipeline_for_test(spy)

    assert spy.aclose_called, "aclose() was not called after PipelineComplete"


async def test_consume_pipeline_closes_on_early_return_async() -> None:
    """_consume_pipeline closes the generator even if it ends without PipelineComplete."""
    from ideagen.cli.commands.run import _consume_pipeline_for_test

    async def gen():
        yield object()  # not a PipelineComplete, just exhaust

    spy = _SpyAsyncGen(gen())
    result = await _consume_pipeline_for_test(spy)

    assert result is None
    assert spy.aclose_called, "aclose() was not called after generator exhaustion"


async def test_consume_pipeline_closes_on_keyboard_interrupt_async() -> None:
    """_consume_pipeline closes the generator on KeyboardInterrupt (Ctrl+C path)."""
    from ideagen.cli.commands.run import _consume_pipeline_for_test

    async def gen():
        raise KeyboardInterrupt
        yield  # make it an async generator

    spy = _SpyAsyncGen(gen())

    with pytest.raises(KeyboardInterrupt):
        await _consume_pipeline_for_test(spy)

    assert spy.aclose_called, "aclose() was not called after KeyboardInterrupt"
