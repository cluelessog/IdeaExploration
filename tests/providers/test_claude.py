"""Tests for ClaudeProvider subprocess integration."""
from __future__ import annotations
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError

from ideagen.core.exceptions import ProviderError
from ideagen.providers.claude import ClaudeProvider


class SimpleResponse(BaseModel):
    value: str
    count: int


def _make_process(stdout: bytes, stderr: bytes = b"", returncode: int = 0) -> MagicMock:
    """Build a mock asyncio subprocess."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


def _json_envelope(content: str) -> bytes:
    """Wrap content in a claude CLI JSON envelope."""
    return json.dumps({"result": content}).encode("utf-8")


@pytest.fixture
def provider() -> ClaudeProvider:
    p = ClaudeProvider(model="claude-3-5-sonnet-20241022", timeout=30.0)
    p._verified = True  # Skip CLI verification in unit tests
    return p


@pytest.fixture
def provider_no_model() -> ClaudeProvider:
    p = ClaudeProvider()
    p._verified = True
    return p


# ---------------------------------------------------------------------------
# _verify_cli
# ---------------------------------------------------------------------------

class TestVerifyCli:
    @pytest.mark.asyncio
    async def test_skips_when_already_verified(self):
        p = ClaudeProvider()
        p._verified = True
        # Should not raise even without claude installed
        await p._verify_cli()

    @pytest.mark.asyncio
    async def test_raises_when_cli_missing(self):
        p = ClaudeProvider()
        with patch("shutil.which", return_value=None):
            with pytest.raises(ProviderError, match="Claude CLI not found"):
                await p._verify_cli()

    @pytest.mark.asyncio
    async def test_raises_on_nonzero_version(self):
        p = ClaudeProvider()
        version_proc = _make_process(b"", b"error", returncode=1)
        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=version_proc)):
                with pytest.raises(ProviderError, match="failed version check"):
                    await p._verify_cli()

    @pytest.mark.asyncio
    async def test_raises_on_timeout(self):
        p = ClaudeProvider()

        async def slow_communicate():
            await asyncio.sleep(100)

        version_proc = MagicMock()
        version_proc.communicate = slow_communicate

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=version_proc)):
                with patch("asyncio.wait_for", AsyncMock(side_effect=asyncio.TimeoutError)):
                    with pytest.raises(ProviderError, match="timed out during verification"):
                        await p._verify_cli()

    @pytest.mark.asyncio
    async def test_sets_verified_on_success(self):
        p = ClaudeProvider()
        version_proc = _make_process(b"claude 1.0.0", returncode=0)
        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=version_proc)):
                await p._verify_cli()
        assert p._verified is True


# ---------------------------------------------------------------------------
# complete — happy paths
# ---------------------------------------------------------------------------

class TestCompleteSuccess:
    @pytest.mark.asyncio
    async def test_valid_json_response(self, provider: ClaudeProvider):
        payload = json.dumps({"value": "hello", "count": 42})
        proc = _make_process(_json_envelope(payload))

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            result = await provider.complete("test prompt", SimpleResponse)

        assert result.value == "hello"
        assert result.count == 42

    @pytest.mark.asyncio
    async def test_markdown_fence_stripped(self, provider: ClaudeProvider):
        fenced = "```json\n{\"value\": \"world\", \"count\": 7}\n```"
        proc = _make_process(_json_envelope(fenced))

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            result = await provider.complete("test", SimpleResponse)

        assert result.value == "world"
        assert result.count == 7

    @pytest.mark.asyncio
    async def test_content_field_envelope(self, provider: ClaudeProvider):
        """Provider also handles 'content' key in envelope."""
        payload = json.dumps({"value": "via_content", "count": 1})
        envelope = json.dumps({"content": payload}).encode("utf-8")
        proc = _make_process(envelope)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            result = await provider.complete("test", SimpleResponse)

        assert result.value == "via_content"

    @pytest.mark.asyncio
    async def test_raw_json_fallback(self, provider: ClaudeProvider):
        """If stdout is not a JSON envelope, treat as raw JSON."""
        payload = json.dumps({"value": "raw", "count": 99}).encode("utf-8")
        proc = _make_process(payload)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            result = await provider.complete("test", SimpleResponse)

        assert result.value == "raw"

    @pytest.mark.asyncio
    async def test_no_model_flag_omitted(self, provider_no_model: ClaudeProvider):
        """When no model is set, --model flag should not appear in command."""
        payload = json.dumps({"value": "ok", "count": 0})
        proc = _make_process(_json_envelope(payload))

        captured_cmd: list[list[str]] = []

        async def fake_exec(*args, **kwargs):
            captured_cmd.append(list(args))
            return proc

        with patch("asyncio.create_subprocess_exec", fake_exec):
            await provider_no_model.complete("test", SimpleResponse)

        cmd = captured_cmd[0]
        assert "--model" not in cmd

    @pytest.mark.asyncio
    async def test_model_flag_included(self, provider: ClaudeProvider):
        """When model is set, --model flag should appear in command."""
        payload = json.dumps({"value": "ok", "count": 0})
        proc = _make_process(_json_envelope(payload))

        captured_cmd: list[list[str]] = []

        async def fake_exec(*args, **kwargs):
            captured_cmd.append(list(args))
            return proc

        with patch("asyncio.create_subprocess_exec", fake_exec):
            await provider.complete("test", SimpleResponse)

        cmd = captured_cmd[0]
        assert "--model" in cmd
        assert "claude-3-5-sonnet-20241022" in cmd

    @pytest.mark.asyncio
    async def test_system_prompt_included_in_stdin(self, provider: ClaudeProvider):
        payload = json.dumps({"value": "ok", "count": 0})
        proc = _make_process(_json_envelope(payload))

        captured_input: list[bytes] = []
        original_communicate = proc.communicate

        async def capturing_communicate(input=None):
            if input:
                captured_input.append(input)
            return await original_communicate()

        proc.communicate = capturing_communicate

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            await provider.complete("my user prompt", SimpleResponse, system_prompt="my system")

        assert captured_input, "communicate was not called with input"
        text = captured_input[0].decode("utf-8")
        assert "my system" in text
        assert "my user prompt" in text


# ---------------------------------------------------------------------------
# complete — error paths
# ---------------------------------------------------------------------------

class TestCompleteErrors:
    @pytest.mark.asyncio
    async def test_nonzero_exit_code_raises(self, provider: ClaudeProvider):
        proc = _make_process(b"", stderr=b"auth error", returncode=1)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            with pytest.raises(ProviderError, match="exited with code 1"):
                await provider.complete("test", SimpleResponse)

    @pytest.mark.asyncio
    async def test_timeout_raises_provider_error(self, provider: ClaudeProvider):
        proc = MagicMock()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            with patch("asyncio.wait_for", AsyncMock(side_effect=asyncio.TimeoutError)):
                with pytest.raises(ProviderError, match="timed out after"):
                    await provider.complete("test", SimpleResponse)

    @pytest.mark.asyncio
    async def test_subprocess_exception_wrapped(self, provider: ClaudeProvider):
        with patch(
            "asyncio.create_subprocess_exec",
            AsyncMock(side_effect=OSError("permission denied")),
        ):
            with pytest.raises(ProviderError, match="subprocess error"):
                await provider.complete("test", SimpleResponse)

    @pytest.mark.asyncio
    async def test_malformed_json_raises_provider_error(self, provider: ClaudeProvider):
        proc = _make_process(_json_envelope("not valid json at all <<<"))

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            with pytest.raises((ProviderError, ValidationError)):
                await provider.complete("test", SimpleResponse)

    @pytest.mark.asyncio
    async def test_validation_error_propagates(self, provider: ClaudeProvider):
        """Missing required field triggers ValidationError (retried by decorator)."""
        payload = json.dumps({"value": "only_value_no_count"})
        proc = _make_process(_json_envelope(payload))

        # Patch retry to not actually sleep, just re-raise after exhaustion
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            with pytest.raises((ValidationError, ProviderError)):
                await provider.complete("test", SimpleResponse)


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------

class TestRetry:
    @pytest.mark.asyncio
    async def test_retries_on_provider_error(self, provider: ClaudeProvider):
        """Provider retries up to max_retries on ProviderError, then raises."""
        call_count = 0

        async def fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise OSError("boom")

        with patch("asyncio.create_subprocess_exec", fake_exec):
            with patch("asyncio.sleep", AsyncMock()):  # Speed up retries
                with pytest.raises(ProviderError):
                    await provider.complete("test", SimpleResponse)

        # 1 initial attempt + 2 retries = 3 total
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_succeeds_on_second_attempt(self, provider: ClaudeProvider):
        """Provider succeeds if second attempt returns valid JSON."""
        payload = json.dumps({"value": "retry_ok", "count": 2})
        good_proc = _make_process(_json_envelope(payload))

        attempt = 0

        async def fake_exec(*args, **kwargs):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise OSError("first attempt fails")
            return good_proc

        with patch("asyncio.create_subprocess_exec", fake_exec):
            with patch("asyncio.sleep", AsyncMock()):
                result = await provider.complete("test", SimpleResponse)

        assert result.value == "retry_ok"
        assert attempt == 2
