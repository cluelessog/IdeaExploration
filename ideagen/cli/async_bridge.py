from __future__ import annotations
import asyncio
import signal
import sys
from typing import Any, Coroutine
from ideagen.core.models import CancellationToken


def run_async(coro: Coroutine[Any, Any, Any], cancellation_token: CancellationToken | None = None) -> Any:
    """Run an async coroutine from sync Typer commands.

    Handles KeyboardInterrupt by setting the cancellation token.
    """
    loop = asyncio.new_event_loop()

    def handle_interrupt():
        if cancellation_token:
            cancellation_token.cancel()

    try:
        if sys.platform != "win32" and cancellation_token:
            loop.add_signal_handler(signal.SIGINT, handle_interrupt)
        return loop.run_until_complete(coro)
    except KeyboardInterrupt:
        if cancellation_token:
            cancellation_token.cancel()
        return None
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
