from __future__ import annotations
import logging
from unittest.mock import patch

from ideagen.cli.callbacks import verbose_callback, quiet_callback


def test_verbose_callback_sets_debug_level():
    with patch("ideagen.cli.callbacks.setup_logging") as mock_setup:
        verbose_callback(True)
        mock_setup.assert_called_once_with(level=logging.DEBUG)


def test_verbose_callback_false_is_noop():
    with patch("ideagen.cli.callbacks.setup_logging") as mock_setup:
        verbose_callback(False)
        mock_setup.assert_not_called()


def test_quiet_callback_sets_warning_level():
    with patch("ideagen.cli.callbacks.setup_logging") as mock_setup:
        quiet_callback(True)
        mock_setup.assert_called_once_with(level=logging.WARNING)


def test_quiet_callback_false_is_noop():
    with patch("ideagen.cli.callbacks.setup_logging") as mock_setup:
        quiet_callback(False)
        mock_setup.assert_not_called()
