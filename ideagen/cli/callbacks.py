from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional
import typer
from ideagen.utils.logging import setup_logging


def verbose_callback(value: bool) -> None:
    if value:
        setup_logging(level=logging.DEBUG)


def quiet_callback(value: bool) -> None:
    if value:
        setup_logging(level=logging.WARNING)
