"""Tests for abstract base classes in ideagen sources, providers, and storage.

Covers:
- ideagen/sources/base.py   – DataSource ABC
- ideagen/providers/base.py – AIProvider ABC
- ideagen/storage/base.py   – StorageBackend ABC
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from ideagen.core.models import Domain, IdeaReport, RunResult, TrendingItem
from ideagen.providers.base import AIProvider
from ideagen.sources.base import DataSource
from ideagen.storage.base import StorageBackend


# ===========================================================================
# DataSource ABC
# ===========================================================================


class TestDataSourceCannotBeInstantiatedDirectly:
    def test_direct_instantiation_raises_type_error(self):
        with pytest.raises(TypeError):
            DataSource()  # type: ignore[abstract]


class TestDataSourceConcreteSubclass:
    def test_concrete_subclass_with_all_methods_instantiates(self):
        class ConcreteSource(DataSource):
            @property
            def name(self) -> str:
                return "concrete"

            async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]:
                return []

            async def is_available(self) -> bool:
                return True

        source = ConcreteSource()
        assert source is not None

    def test_concrete_subclass_exposes_name_property(self):
        class ConcreteSource(DataSource):
            @property
            def name(self) -> str:
                return "my_source"

            async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]:
                return []

            async def is_available(self) -> bool:
                return True

        source = ConcreteSource()
        assert source.name == "my_source"

    def test_concrete_subclass_has_parser_version_class_attribute(self):
        class ConcreteSource(DataSource):
            @property
            def name(self) -> str:
                return "v_source"

            async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]:
                return []

            async def is_available(self) -> bool:
                return True

        assert ConcreteSource.PARSER_VERSION == "1.0"

    def test_subclass_missing_name_property_raises_on_instantiation(self):
        class MissingName(DataSource):
            async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]:
                return []

            async def is_available(self) -> bool:
                return True

        with pytest.raises(TypeError):
            MissingName()  # type: ignore[abstract]

    def test_subclass_missing_collect_raises_on_instantiation(self):
        class MissingCollect(DataSource):
            @property
            def name(self) -> str:
                return "incomplete"

            async def is_available(self) -> bool:
                return True

        with pytest.raises(TypeError):
            MissingCollect()  # type: ignore[abstract]

    def test_subclass_missing_is_available_raises_on_instantiation(self):
        class MissingIsAvailable(DataSource):
            @property
            def name(self) -> str:
                return "incomplete"

            async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]:
                return []

        with pytest.raises(TypeError):
            MissingIsAvailable()  # type: ignore[abstract]

    def test_subclass_missing_all_abstract_methods_raises_on_instantiation(self):
        class EmptySubclass(DataSource):
            pass

        with pytest.raises(TypeError):
            EmptySubclass()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_collect_is_awaitable_on_concrete_subclass(self):
        class ConcreteSource(DataSource):
            @property
            def name(self) -> str:
                return "async_source"

            async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]:
                return []

            async def is_available(self) -> bool:
                return True

        source = ConcreteSource()
        result = await source.collect(domain=Domain.SOFTWARE_SAAS)
        assert result == []

    @pytest.mark.asyncio
    async def test_is_available_is_awaitable_on_concrete_subclass(self):
        class ConcreteSource(DataSource):
            @property
            def name(self) -> str:
                return "async_source"

            async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]:
                return []

            async def is_available(self) -> bool:
                return True

        source = ConcreteSource()
        available = await source.is_available()
        assert available is True


# ===========================================================================
# AIProvider ABC
# ===========================================================================


class TestAIProviderCannotBeInstantiatedDirectly:
    def test_direct_instantiation_raises_type_error(self):
        with pytest.raises(TypeError):
            AIProvider()  # type: ignore[abstract]


class TestAIProviderConcreteSubclass:
    def test_concrete_subclass_with_complete_method_instantiates(self):
        class ConcreteProvider(AIProvider):
            async def complete(
                self,
                user_prompt: str,
                response_type: type,
                system_prompt: str | None = None,
            ):
                return response_type()

        provider = ConcreteProvider()
        assert provider is not None

    def test_subclass_missing_complete_raises_on_instantiation(self):
        class MissingComplete(AIProvider):
            pass

        with pytest.raises(TypeError):
            MissingComplete()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_complete_is_awaitable_on_concrete_subclass(self):
        class SimpleModel(BaseModel):
            value: str = "default"

        class ConcreteProvider(AIProvider):
            async def complete(
                self,
                user_prompt: str,
                response_type: type,
                system_prompt: str | None = None,
            ):
                return response_type()

        provider = ConcreteProvider()
        result = await provider.complete("prompt", SimpleModel)
        assert isinstance(result, SimpleModel)

    @pytest.mark.asyncio
    async def test_complete_receives_system_prompt_argument(self):
        received: dict = {}

        class ConcreteProvider(AIProvider):
            async def complete(
                self,
                user_prompt: str,
                response_type: type,
                system_prompt: str | None = None,
            ):
                received["system_prompt"] = system_prompt
                return response_type()

        class SimpleModel(BaseModel):
            value: str = "x"

        provider = ConcreteProvider()
        await provider.complete("prompt", SimpleModel, system_prompt="be helpful")
        assert received["system_prompt"] == "be helpful"

    @pytest.mark.asyncio
    async def test_complete_system_prompt_defaults_to_none(self):
        received: dict = {}

        class ConcreteProvider(AIProvider):
            async def complete(
                self,
                user_prompt: str,
                response_type: type,
                system_prompt: str | None = None,
            ):
                received["system_prompt"] = system_prompt
                return response_type()

        class SimpleModel(BaseModel):
            value: str = "x"

        provider = ConcreteProvider()
        await provider.complete("prompt", SimpleModel)
        assert received["system_prompt"] is None


# ===========================================================================
# StorageBackend ABC
# ===========================================================================


class TestStorageBackendCannotBeInstantiatedDirectly:
    def test_direct_instantiation_raises_type_error(self):
        with pytest.raises(TypeError):
            StorageBackend()  # type: ignore[abstract]


class TestStorageBackendConcreteSubclass:
    def _make_concrete(self) -> type:
        class ConcreteStorage(StorageBackend):
            async def save_run(self, result: RunResult) -> str:
                return "run-id-123"

            async def get_runs(
                self, offset: int = 0, limit: int = 20, **filters: Any
            ) -> list[dict]:
                return []

            async def get_idea(self, idea_id: str) -> IdeaReport | None:
                return None

            async def search_ideas(
                self, query: str, offset: int = 0, limit: int = 50
            ) -> list[IdeaReport]:
                return []

            async def get_run_detail(self, run_id_prefix: str) -> dict | None:
                return None

            async def save_scrape_cache(self, batch_id: str, source: str, items: list) -> None:
                pass

            async def load_latest_scrape_cache(self, source_names: list[str] | None = None) -> list:
                return []

            async def find_runs_by_content_hash(self, content_hash: str, exclude_id: str | None = None) -> list[dict]:
                return []

            async def find_runs_by_prefix(self, prefix: str) -> list[dict]:
                return []

        return ConcreteStorage

    def test_concrete_subclass_with_all_methods_instantiates(self):
        cls = self._make_concrete()
        backend = cls()
        assert backend is not None

    def test_subclass_missing_save_run_raises_on_instantiation(self):
        class MissingSaveRun(StorageBackend):
            async def get_runs(
                self, offset: int = 0, limit: int = 20, **filters: Any
            ) -> list[dict]:
                return []

            async def get_idea(self, idea_id: str) -> IdeaReport | None:
                return None

            async def search_ideas(
                self, query: str, offset: int = 0, limit: int = 50
            ) -> list[IdeaReport]:
                return []

        with pytest.raises(TypeError):
            MissingSaveRun()  # type: ignore[abstract]

    def test_subclass_missing_get_runs_raises_on_instantiation(self):
        class MissingGetRuns(StorageBackend):
            async def save_run(self, result: RunResult) -> str:
                return "id"

            async def get_idea(self, idea_id: str) -> IdeaReport | None:
                return None

            async def search_ideas(
                self, query: str, offset: int = 0, limit: int = 50
            ) -> list[IdeaReport]:
                return []

        with pytest.raises(TypeError):
            MissingGetRuns()  # type: ignore[abstract]

    def test_subclass_missing_get_idea_raises_on_instantiation(self):
        class MissingGetIdea(StorageBackend):
            async def save_run(self, result: RunResult) -> str:
                return "id"

            async def get_runs(
                self, offset: int = 0, limit: int = 20, **filters: Any
            ) -> list[dict]:
                return []

            async def search_ideas(
                self, query: str, offset: int = 0, limit: int = 50
            ) -> list[IdeaReport]:
                return []

        with pytest.raises(TypeError):
            MissingGetIdea()  # type: ignore[abstract]

    def test_subclass_missing_search_ideas_raises_on_instantiation(self):
        class MissingSearchIdeas(StorageBackend):
            async def save_run(self, result: RunResult) -> str:
                return "id"

            async def get_runs(
                self, offset: int = 0, limit: int = 20, **filters: Any
            ) -> list[dict]:
                return []

            async def get_idea(self, idea_id: str) -> IdeaReport | None:
                return None

        with pytest.raises(TypeError):
            MissingSearchIdeas()  # type: ignore[abstract]

    def test_subclass_missing_all_methods_raises_on_instantiation(self):
        class EmptySubclass(StorageBackend):
            pass

        with pytest.raises(TypeError):
            EmptySubclass()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_save_run_is_awaitable_and_returns_string(self):
        from datetime import datetime

        cls = self._make_concrete()
        backend = cls()

        run = RunResult(
            ideas=[],
            sources_used=["hackernews"],
            domain=Domain.SOFTWARE_SAAS,
            timestamp=datetime.now(),
        )
        result = await backend.save_run(run)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_get_runs_is_awaitable_and_returns_list(self):
        cls = self._make_concrete()
        backend = cls()
        result = await backend.get_runs()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_idea_is_awaitable_and_returns_none_for_unknown_id(self):
        cls = self._make_concrete()
        backend = cls()
        result = await backend.get_idea("unknown-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_search_ideas_is_awaitable_and_returns_list(self):
        cls = self._make_concrete()
        backend = cls()
        result = await backend.search_ideas("test query")
        assert isinstance(result, list)
