from __future__ import annotations

import logging

from ideagen.core.models import Domain
from ideagen.sources.base import DataSource
from ideagen.sources.hackernews import HackerNewsSource
from ideagen.sources.producthunt import ProductHuntSource
from ideagen.sources.reddit import RedditSource
from ideagen.sources.twitter import TwitterSource

logger = logging.getLogger("ideagen")

_DEFAULT_SOURCES: dict[str, type[DataSource]] = {
    "hackernews": HackerNewsSource,
    "reddit": RedditSource,
    "producthunt": ProductHuntSource,
    "twitter": TwitterSource,
}


def get_all_sources(**kwargs) -> dict[str, DataSource]:
    """Instantiate all registered sources."""
    return {
        name: cls(**{k: v for k, v in kwargs.items() if k in cls.__init__.__code__.co_varnames})
        for name, cls in _DEFAULT_SOURCES.items()
    }


def get_sources_by_names(names: list[str], **kwargs) -> dict[str, DataSource]:
    """Instantiate only the named sources."""
    sources: dict[str, DataSource] = {}
    for name in names:
        cls = _DEFAULT_SOURCES.get(name)
        if cls:
            sources[name] = cls()
        else:
            logger.warning(f"Unknown source: {name}")
    return sources


def get_available_source_names() -> list[str]:
    return list(_DEFAULT_SOURCES.keys())
