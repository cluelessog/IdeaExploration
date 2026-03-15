from __future__ import annotations

import inspect
import logging
from typing import TYPE_CHECKING

from ideagen.core.models import Domain
from ideagen.sources.base import DataSource
from ideagen.sources.hackernews import HackerNewsSource
from ideagen.sources.producthunt import ProductHuntSource
from ideagen.sources.reddit import RedditSource
from ideagen.sources.twitter import TwitterSource

if TYPE_CHECKING:
    from ideagen.core.config import SourceConfig

logger = logging.getLogger("ideagen")

_DEFAULT_SOURCES: dict[str, type[DataSource]] = {
    "hackernews": HackerNewsSource,
    "reddit": RedditSource,
    "producthunt": ProductHuntSource,
    "twitter": TwitterSource,
}


def _kwargs_for_source(cls: type[DataSource], source_config: "SourceConfig") -> dict:
    """Build constructor kwargs from SourceConfig, filtered to what the constructor accepts."""
    sig = inspect.signature(cls.__init__)
    params = set(sig.parameters.keys()) - {"self"}

    kwargs: dict = {}
    if "scrape_delay" in params:
        kwargs["scrape_delay"] = source_config.scrape_delay
    if "subreddits" in params and source_config.reddit_subreddits:
        kwargs["subreddits"] = source_config.reddit_subreddits
    return kwargs


def get_all_sources(**kwargs) -> dict[str, DataSource]:
    """Instantiate all registered sources."""
    return {
        name: cls(**{k: v for k, v in kwargs.items() if k in cls.__init__.__code__.co_varnames})
        for name, cls in _DEFAULT_SOURCES.items()
    }


def get_sources_by_names(
    names: list[str],
    source_config: "SourceConfig | None" = None,
    **kwargs,
) -> dict[str, DataSource]:
    """Instantiate only the named sources, forwarding SourceConfig fields to constructors."""
    sources: dict[str, DataSource] = {}
    for name in names:
        cls = _DEFAULT_SOURCES.get(name)
        if cls:
            ctor_kwargs = _kwargs_for_source(cls, source_config) if source_config is not None else {}
            sources[name] = cls(**ctor_kwargs)
        else:
            logger.warning(f"Unknown source: {name}")
    return sources


def get_available_source_names() -> list[str]:
    return list(_DEFAULT_SOURCES.keys())
