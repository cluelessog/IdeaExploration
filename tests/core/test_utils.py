"""Tests for utility modules and core supporting components.

Covers:
- ideagen/utils/text.py        – extract_json
- ideagen/utils/retry.py       – with_retry decorator
- ideagen/utils/logging.py     – setup_logging / JSONFormatter
- ideagen/core/wtp_segments.py – WTP segment knowledge base helpers
- ideagen/core/exceptions.py   – exception hierarchy
"""
from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideagen.core.exceptions import (
    ConfigError,
    IdeaGenError,
    ProviderError,
    SourceUnavailableError,
    StorageError,
)
from ideagen.core.wtp_segments import (
    WTP_SEGMENTS,
    format_segments_for_prompt,
    get_segment,
    get_segments_by_ids,
    get_top_segments,
)
from ideagen.utils.logging import JSONFormatter, setup_logging
from ideagen.utils.retry import with_retry
from ideagen.utils.text import extract_json


# ===========================================================================
# extract_json
# ===========================================================================


class TestExtractJsonFencedBlocks:
    def test_strips_json_fenced_block(self):
        text = '```json\n{"key": "value"}\n```'
        result = extract_json(text)
        assert json.loads(result) == {"key": "value"}

    def test_strips_bare_fenced_block(self):
        text = '```\n{"key": "value"}\n```'
        result = extract_json(text)
        assert json.loads(result) == {"key": "value"}

    def test_strips_fenced_block_with_array(self):
        text = '```json\n[1, 2, 3]\n```'
        result = extract_json(text)
        assert json.loads(result) == [1, 2, 3]

    def test_strips_fenced_block_ignoring_surrounding_whitespace(self):
        text = '  \n```json\n  {"a": 1}  \n```\n  '
        result = extract_json(text)
        assert json.loads(result) == {"a": 1}


class TestExtractJsonRawInput:
    def test_handles_raw_json_object(self):
        raw = '{"hello": "world"}'
        result = extract_json(raw)
        assert json.loads(result) == {"hello": "world"}

    def test_handles_raw_json_array(self):
        raw = '[{"id": 1}, {"id": 2}]'
        result = extract_json(raw)
        assert json.loads(result) == [{"id": 1}, {"id": 2}]

    def test_handles_raw_json_with_leading_whitespace(self):
        raw = '   {"x": true}   '
        result = extract_json(raw)
        assert json.loads(result) is not None


class TestExtractJsonEmbeddedInText:
    def test_extracts_json_object_embedded_in_prose(self):
        text = 'Here is the result: {"status": "ok"} — done.'
        result = extract_json(text)
        assert json.loads(result) == {"status": "ok"}

    def test_extracts_json_array_embedded_in_prose(self):
        text = 'Response: [1, 2, 3] end.'
        result = extract_json(text)
        assert json.loads(result) == [1, 2, 3]


class TestExtractJsonErrors:
    def test_raises_value_error_for_plain_text(self):
        with pytest.raises(ValueError):
            extract_json("this is not JSON at all")

    def test_raises_value_error_for_empty_string(self):
        with pytest.raises(ValueError):
            extract_json("")

    def test_raises_value_error_for_malformed_fenced_block(self):
        with pytest.raises(ValueError):
            extract_json("```json\nnot valid json\n```")

    def test_raises_value_error_for_numbers_only(self):
        # A bare integer is valid JSON, but test deliberately malformed content
        with pytest.raises(ValueError):
            extract_json("no json {broken: here}")


# ===========================================================================
# with_retry
# ===========================================================================


class TestWithRetry:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt_without_retrying(self):
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.01)
        async def succeeds():
            nonlocal call_count
            call_count += 1
            return "ok"

        with patch("ideagen.utils.retry.asyncio.sleep", new_callable=AsyncMock):
            result = await succeeds()

        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_exception_and_succeeds_on_nth_attempt(self):
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.01)
        async def fails_twice_then_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient")
            return "success"

        with patch("ideagen.utils.retry.asyncio.sleep", new_callable=AsyncMock):
            result = await fails_twice_then_succeeds()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_all_retries_exhausted(self):
        @with_retry(max_retries=2, base_delay=0.01)
        async def always_fails():
            raise RuntimeError("permanent")

        with patch("ideagen.utils.retry.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="permanent"):
                await always_fails()

    @pytest.mark.asyncio
    async def test_respects_max_retries_attempt_count(self):
        call_count = 0

        @with_retry(max_retries=2, base_delay=0.01)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        with patch("ideagen.utils.retry.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ValueError):
                await always_fails()

        # initial attempt + 2 retries = 3 total calls
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retryable_exceptions_filter_does_not_retry_excluded_exception(self):
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.01, retryable_exceptions=(ValueError,))
        async def raises_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("not retryable")

        with patch("ideagen.utils.retry.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(TypeError):
                await raises_type_error()

        # Should not retry — only 1 call
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retryable_exceptions_filter_retries_matching_exception(self):
        call_count = 0

        @with_retry(max_retries=2, base_delay=0.01, retryable_exceptions=(ValueError,))
        async def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("retryable")

        with patch("ideagen.utils.retry.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ValueError):
                await raises_value_error()

        assert call_count == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    async def test_sleep_is_called_between_retries(self):
        @with_retry(max_retries=2, base_delay=0.01)
        async def always_fails():
            raise ValueError("fail")

        with patch("ideagen.utils.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ValueError):
                await always_fails()

        assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_preserves_decorated_function_name(self):
        @with_retry(max_retries=1, base_delay=0.01)
        async def my_named_function():
            return "value"

        assert my_named_function.__name__ == "my_named_function"

    @pytest.mark.asyncio
    async def test_zero_retries_raises_immediately_on_failure(self):
        call_count = 0

        @with_retry(max_retries=0, base_delay=0.01)
        async def fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("immediate")

        with patch("ideagen.utils.retry.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ValueError):
                await fails()

        assert call_count == 1


# ===========================================================================
# setup_logging / JSONFormatter
# ===========================================================================


class TestSetupLogging:
    def setup_method(self):
        """Remove all handlers from the ideagen logger before each test."""
        logger = logging.getLogger("ideagen")
        logger.handlers.clear()

    def test_creates_ideagen_logger(self):
        setup_logging()
        logger = logging.getLogger("ideagen")
        assert logger is not None

    def test_logger_has_at_least_one_handler_after_setup(self):
        setup_logging()
        logger = logging.getLogger("ideagen")
        assert len(logger.handlers) >= 1

    def test_setup_logging_is_idempotent_does_not_add_duplicate_handlers(self):
        setup_logging()
        setup_logging()
        logger = logging.getLogger("ideagen")
        assert len(logger.handlers) == 1

    def test_default_log_level_is_info(self):
        setup_logging()
        logger = logging.getLogger("ideagen")
        assert logger.level == logging.INFO

    def test_custom_log_level_is_applied(self):
        setup_logging(level=logging.DEBUG)
        logger = logging.getLogger("ideagen")
        assert logger.level == logging.DEBUG


class TestJSONFormatter:
    def _make_record(self, message: str, level: int = logging.INFO) -> logging.LogRecord:
        return logging.LogRecord(
            name="ideagen",
            level=level,
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )

    def test_json_formatter_output_is_valid_json(self):
        formatter = JSONFormatter()
        record = self._make_record("test message")
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_json_output_contains_timestamp_key(self):
        formatter = JSONFormatter()
        record = self._make_record("msg")
        parsed = json.loads(formatter.format(record))
        assert "timestamp" in parsed

    def test_json_output_contains_level_key(self):
        formatter = JSONFormatter()
        record = self._make_record("msg", level=logging.WARNING)
        parsed = json.loads(formatter.format(record))
        assert parsed["level"] == "WARNING"

    def test_json_output_contains_logger_name(self):
        formatter = JSONFormatter()
        record = self._make_record("msg")
        parsed = json.loads(formatter.format(record))
        assert parsed["logger"] == "ideagen"

    def test_json_output_contains_message(self):
        formatter = JSONFormatter()
        record = self._make_record("hello world")
        parsed = json.loads(formatter.format(record))
        assert parsed["message"] == "hello world"

    def test_json_output_includes_exception_when_present(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("oops")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="ideagen",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="error occurred",
            args=(),
            exc_info=exc_info,
        )
        parsed = json.loads(formatter.format(record))
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]

    def test_json_formatter_used_when_json_format_true(self):
        logger = logging.getLogger("ideagen")
        logger.handlers.clear()  # Reset so setup_logging can re-add
        setup_logging(json_format=True)
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)


# ===========================================================================
# WTP Segments
# ===========================================================================


class TestWTPSegmentsLoaded:
    def test_exactly_22_segments_loaded(self):
        assert len(WTP_SEGMENTS) == 22

    def test_all_segment_ids_are_strings(self):
        for seg_id in WTP_SEGMENTS:
            assert isinstance(seg_id, str)

    def test_all_segments_have_non_empty_name(self):
        for seg in WTP_SEGMENTS.values():
            assert seg.name.strip() != ""

    def test_all_segments_have_wtp_score(self):
        for seg in WTP_SEGMENTS.values():
            assert isinstance(seg.wtp_score, float)

    def test_all_segments_have_at_least_one_spending_area(self):
        for seg in WTP_SEGMENTS.values():
            assert len(seg.spending_areas) >= 1


class TestGetSegment:
    def test_returns_correct_segment_for_known_id(self):
        seg = get_segment("parents")
        assert seg is not None
        assert seg.id == "parents"
        assert "parents" in seg.name.lower() or seg.id == "parents"

    def test_returns_none_for_unknown_segment_id(self):
        result = get_segment("nonexistent_segment_xyz")
        assert result is None

    def test_returns_segment_with_matching_wtp_score_for_parents(self):
        seg = get_segment("parents")
        assert seg.wtp_score == 4.65

    def test_returns_segment_with_matching_pain_tolerance_for_parents(self):
        seg = get_segment("parents")
        assert seg.pain_tolerance == 5.0


class TestGetTopSegments:
    def test_returns_sorted_list_by_wtp_score_descending(self):
        top = get_top_segments(n=5)
        scores = [s.wtp_score for s in top]
        assert scores == sorted(scores, reverse=True)

    def test_returns_correct_number_of_segments(self):
        top = get_top_segments(n=3)
        assert len(top) == 3

    def test_default_n_returns_five_segments(self):
        top = get_top_segments()
        assert len(top) == 5

    def test_top_segment_has_highest_wtp_score(self):
        top = get_top_segments(n=1)
        all_scores = [s.wtp_score for s in WTP_SEGMENTS.values()]
        assert top[0].wtp_score == max(all_scores)

    def test_returns_all_22_when_n_equals_22(self):
        top = get_top_segments(n=22)
        assert len(top) == 22


class TestGetSegmentsByIds:
    def test_returns_segments_for_valid_ids(self):
        result = get_segments_by_ids(["parents", "pet_owners"])
        assert len(result) == 2
        ids = {s.id for s in result}
        assert ids == {"parents", "pet_owners"}

    def test_skips_unknown_ids(self):
        result = get_segments_by_ids(["parents", "unknown_xyz"])
        assert len(result) == 1
        assert result[0].id == "parents"

    def test_returns_empty_list_for_all_unknown_ids(self):
        result = get_segments_by_ids(["nope", "also_nope"])
        assert result == []

    def test_returns_empty_list_for_empty_input(self):
        result = get_segments_by_ids([])
        assert result == []

    def test_preserves_order_of_requested_ids(self):
        result = get_segments_by_ids(["pet_owners", "parents"])
        assert result[0].id == "pet_owners"
        assert result[1].id == "parents"


class TestFormatSegmentsForPrompt:
    def test_returns_a_string(self):
        segments = get_segments_by_ids(["parents"])
        result = format_segments_for_prompt(segments)
        assert isinstance(result, str)

    def test_output_contains_segment_name(self):
        segments = get_segments_by_ids(["parents"])
        result = format_segments_for_prompt(segments)
        assert "Parents" in result

    def test_output_contains_wtp_score(self):
        segments = get_segments_by_ids(["parents"])
        result = format_segments_for_prompt(segments)
        assert "4.65" in result

    def test_output_contains_emotional_driver(self):
        segments = get_segments_by_ids(["parents"])
        result = format_segments_for_prompt(segments)
        assert "Fear" in result or "guilt" in result or "desire" in result

    def test_output_contains_spending_areas(self):
        segments = get_segments_by_ids(["parents"])
        result = format_segments_for_prompt(segments)
        assert "education" in result

    def test_output_contains_all_segments_when_multiple_passed(self):
        segments = get_segments_by_ids(["parents", "pet_owners"])
        result = format_segments_for_prompt(segments)
        assert "Parents" in result
        assert "Pet" in result

    def test_returns_string_for_empty_segment_list(self):
        result = format_segments_for_prompt([])
        assert isinstance(result, str)


# ===========================================================================
# Exceptions
# ===========================================================================


class TestExceptionHierarchy:
    def test_idea_gen_error_is_exception_subclass(self):
        assert issubclass(IdeaGenError, Exception)

    def test_source_unavailable_error_is_idea_gen_error_subclass(self):
        assert issubclass(SourceUnavailableError, IdeaGenError)

    def test_provider_error_is_idea_gen_error_subclass(self):
        assert issubclass(ProviderError, IdeaGenError)

    def test_config_error_is_idea_gen_error_subclass(self):
        assert issubclass(ConfigError, IdeaGenError)

    def test_storage_error_is_idea_gen_error_subclass(self):
        assert issubclass(StorageError, IdeaGenError)

    def test_idea_gen_error_can_be_raised_and_caught(self):
        with pytest.raises(IdeaGenError):
            raise IdeaGenError("base error")

    def test_source_unavailable_error_caught_as_idea_gen_error(self):
        with pytest.raises(IdeaGenError):
            raise SourceUnavailableError("source down")

    def test_provider_error_caught_as_idea_gen_error(self):
        with pytest.raises(IdeaGenError):
            raise ProviderError("provider failed")

    def test_config_error_caught_as_idea_gen_error(self):
        with pytest.raises(IdeaGenError):
            raise ConfigError("bad config")

    def test_storage_error_caught_as_idea_gen_error(self):
        with pytest.raises(IdeaGenError):
            raise StorageError("storage failed")

    def test_all_exception_classes_support_message_argument(self):
        for exc_class in (
            IdeaGenError,
            SourceUnavailableError,
            ProviderError,
            ConfigError,
            StorageError,
        ):
            exc = exc_class("test message")
            assert str(exc) == "test message"
