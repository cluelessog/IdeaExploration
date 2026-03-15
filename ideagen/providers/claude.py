from __future__ import annotations
import asyncio
import json
import logging
import shutil
from typing import TypeVar
from pydantic import BaseModel, ValidationError
from ideagen.providers.base import AIProvider
from ideagen.core.exceptions import ProviderError, ProviderTimeoutError
from ideagen.utils.text import extract_json
from ideagen.utils.retry import with_retry

logger = logging.getLogger("ideagen")
T = TypeVar("T", bound=BaseModel)


class ClaudeProvider(AIProvider):
    """AI provider that shells out to the `claude` CLI subprocess."""

    def __init__(self, model: str | None = None, timeout: float = 300.0):
        self._model = model
        self._timeout = timeout
        self._verified = False

    async def _verify_cli(self) -> None:
        """Check that claude CLI is installed and accessible."""
        if self._verified:
            return

        if not shutil.which("claude"):
            raise ProviderError(
                "Claude CLI not found. Install Claude Code: "
                "https://docs.anthropic.com/en/docs/claude-code"
            )

        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10.0)
            if proc.returncode != 0:
                raise ProviderError("Claude CLI failed version check. Run 'claude' to log in.")
        except asyncio.TimeoutError:
            raise ProviderError("Claude CLI timed out during verification.")
        except FileNotFoundError:
            raise ProviderError("Claude CLI not found.")

        self._verified = True

    @with_retry(max_retries=2, base_delay=2.0, retryable_exceptions=(ProviderError, ValidationError), non_retryable_exceptions=(ProviderTimeoutError,))
    async def complete(
        self,
        user_prompt: str,
        response_type: type[T],
        system_prompt: str | None = None,
    ) -> T:
        await self._verify_cli()

        # Build the full prompt — schema is already embedded by prompts.py (single source of truth)
        parts = []
        if system_prompt:
            parts.append(system_prompt)
        parts.append(user_prompt)
        full_prompt = "\n\n".join(parts)

        # Build command
        cmd = ["claude", "--output-format", "json", "-p"]
        if self._model:
            cmd.extend(["--model", self._model])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=full_prompt.encode("utf-8")),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except (ProcessLookupError, OSError):
                pass
            raise ProviderTimeoutError(f"Claude CLI timed out after {self._timeout}s")
        except Exception as e:
            raise ProviderError(f"Claude CLI subprocess error: {e}")

        if proc.returncode != 0:
            stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
            stdout_text = stdout_bytes.decode("utf-8", errors="replace").strip()

            # Claude CLI often puts structured errors in stdout JSON
            error_detail = stderr_text
            try:
                envelope = json.loads(stdout_text)
                if isinstance(envelope, dict):
                    if envelope.get("is_error"):
                        error_detail = envelope.get("result", envelope.get("error", stdout_text))
                    elif "error" in envelope:
                        error_detail = envelope["error"]
            except (json.JSONDecodeError, KeyError):
                # If stdout isn't parseable JSON, combine both if available
                if stdout_text and not stderr_text:
                    error_detail = stdout_text
                elif stdout_text and stderr_text:
                    error_detail = f"{stderr_text} | stdout: {stdout_text[:200]}"

            raise ProviderError(
                f"Claude CLI exited with code {proc.returncode}: {error_detail[:500]}"
            )

        stdout_text = stdout_bytes.decode("utf-8")

        # Claude --output-format json wraps response in a JSON envelope
        # Extract the actual content
        try:
            envelope = json.loads(stdout_text)
            # The claude CLI JSON output has a "result" field with the text
            if isinstance(envelope, dict) and "result" in envelope:
                raw_text = envelope["result"]
            elif isinstance(envelope, dict) and "content" in envelope:
                raw_text = envelope["content"]
            else:
                raw_text = stdout_text
        except json.JSONDecodeError:
            raw_text = stdout_text

        # Extract JSON from the response (strips markdown fences if present)
        try:
            raw_json = extract_json(raw_text)
        except ValueError as e:
            raise ProviderError(f"Failed to extract JSON from Claude response: {e}")

        # Validate and return typed model
        try:
            return response_type.model_validate_json(raw_json)
        except ValidationError:
            raise  # Let retry handle this
