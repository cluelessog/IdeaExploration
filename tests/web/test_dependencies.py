"""Tests for dependencies module (lifespan, reset, singletons)."""
from __future__ import annotations

import pytest

from ideagen.core.config import IdeaGenConfig
from ideagen.storage.sqlite import SQLiteStorage
from ideagen.web import dependencies


class TestConfigure:
    def test_configure_sets_config(self):
        dependencies.reset()
        cfg = IdeaGenConfig()
        dependencies.configure(config=cfg)
        assert dependencies.get_config() is cfg
        dependencies.reset()

    def test_configure_sets_storage(self):
        dependencies.reset()
        storage = SQLiteStorage(db_path=":memory:")
        dependencies.configure(storage=storage)
        assert dependencies.get_storage() is storage
        dependencies.reset()


class TestGetConfig:
    def test_returns_default_config_when_not_configured(self):
        dependencies.reset()
        cfg = dependencies.get_config()
        assert isinstance(cfg, IdeaGenConfig)
        dependencies.reset()


class TestGetTemplates:
    def test_returns_templates_instance(self):
        dependencies.reset()
        t1 = dependencies.get_templates()
        t2 = dependencies.get_templates()
        assert t1 is t2
        dependencies.reset()


class TestReset:
    def test_reset_clears_all(self):
        dependencies.reset()
        cfg = IdeaGenConfig()
        dependencies.configure(config=cfg)
        dependencies.reset()
        # After reset, get_config returns a new default config
        new_cfg = dependencies.get_config()
        assert new_cfg is not cfg
        dependencies.reset()
