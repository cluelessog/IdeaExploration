"""Tests for IdeaGenConfig and sub-configs in ideagen/core/config.py."""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from ideagen.core.config import (
    GenerationConfig,
    IdeaGenConfig,
    ProviderConfig,
    SourceConfig,
    StorageConfig,
)


# ---------------------------------------------------------------------------
# IdeaGenConfig – top-level instantiation
# ---------------------------------------------------------------------------


class TestIdeaGenConfigDefaults:
    def test_instantiates_with_no_arguments(self):
        config = IdeaGenConfig()
        assert config is not None

    def test_default_provider_is_claude(self):
        config = IdeaGenConfig()
        assert config.providers.default == "claude"

    def test_default_sources_contains_all_four_enabled(self):
        config = IdeaGenConfig()
        assert set(config.sources.enabled) == {
            "hackernews",
            "reddit",
            "producthunt",
            "twitter",
        }

    def test_default_ideas_per_run_is_ten(self):
        config = IdeaGenConfig()
        assert config.generation.ideas_per_run == 10

    def test_default_prompt_override_dir_is_none(self):
        config = IdeaGenConfig()
        assert config.prompt_override_dir is None

    def test_sub_configs_are_correct_types(self):
        config = IdeaGenConfig()
        assert isinstance(config.sources, SourceConfig)
        assert isinstance(config.providers, ProviderConfig)
        assert isinstance(config.storage, StorageConfig)
        assert isinstance(config.generation, GenerationConfig)


# ---------------------------------------------------------------------------
# SourceConfig defaults
# ---------------------------------------------------------------------------


class TestSourceConfigDefaults:
    def test_default_scrape_delay(self):
        cfg = SourceConfig()
        assert cfg.scrape_delay == 2.0

    def test_default_proxy_url_is_none(self):
        cfg = SourceConfig()
        assert cfg.proxy_url is None

    def test_default_reddit_subreddits(self):
        cfg = SourceConfig()
        assert set(cfg.reddit_subreddits) == {"SaaS", "startups", "Entrepreneur", "smallbusiness"}


# ---------------------------------------------------------------------------
# ProviderConfig defaults
# ---------------------------------------------------------------------------


class TestProviderConfigDefaults:
    def test_default_provider_is_claude(self):
        cfg = ProviderConfig()
        assert cfg.default == "claude"

    def test_default_openai_api_key_is_none(self):
        cfg = ProviderConfig()
        assert cfg.openai_api_key is None

    def test_default_gemini_api_key_is_none(self):
        cfg = ProviderConfig()
        assert cfg.gemini_api_key is None

    def test_default_model_override_is_none(self):
        cfg = ProviderConfig()
        assert cfg.model is None


# ---------------------------------------------------------------------------
# StorageConfig defaults
# ---------------------------------------------------------------------------


class TestStorageConfigDefaults:
    def test_default_database_path(self):
        cfg = StorageConfig()
        assert cfg.database_path == "~/.ideagen/ideagen.db"

    def test_default_output_dir(self):
        cfg = StorageConfig()
        assert cfg.output_dir == "./ideagen_output"


# ---------------------------------------------------------------------------
# GenerationConfig defaults
# ---------------------------------------------------------------------------


class TestGenerationConfigDefaults:
    def test_default_ideas_per_run(self):
        cfg = GenerationConfig()
        assert cfg.ideas_per_run == 10

    def test_default_domain(self):
        cfg = GenerationConfig()
        assert cfg.domain == "software"

    def test_default_target_segments_is_empty_list(self):
        cfg = GenerationConfig()
        assert cfg.target_segments == []

    def test_default_dedup_threshold(self):
        cfg = GenerationConfig()
        assert cfg.dedup_threshold == 0.85


# ---------------------------------------------------------------------------
# Custom value overrides
# ---------------------------------------------------------------------------


class TestIdeaGenConfigCustomValues:
    def test_custom_ideas_per_run(self):
        config = IdeaGenConfig(generation=GenerationConfig(ideas_per_run=25))
        assert config.generation.ideas_per_run == 25

    def test_custom_default_provider(self):
        config = IdeaGenConfig(providers=ProviderConfig(default="openai"))
        assert config.providers.default == "openai"

    def test_custom_enabled_sources(self):
        config = IdeaGenConfig(sources=SourceConfig(enabled=["hackernews"]))
        assert config.sources.enabled == ["hackernews"]

    def test_custom_scrape_delay(self):
        config = IdeaGenConfig(sources=SourceConfig(scrape_delay=5.0))
        assert config.sources.scrape_delay == 5.0

    def test_custom_dedup_threshold(self):
        config = IdeaGenConfig(generation=GenerationConfig(dedup_threshold=0.9))
        assert config.generation.dedup_threshold == 0.9


# ---------------------------------------------------------------------------
# prompt_override_dir accepts Path or None
# ---------------------------------------------------------------------------


class TestPromptOverrideDir:
    def test_accepts_none(self):
        config = IdeaGenConfig(prompt_override_dir=None)
        assert config.prompt_override_dir is None

    def test_accepts_path_object(self, tmp_path: Path):
        config = IdeaGenConfig(prompt_override_dir=tmp_path)
        assert config.prompt_override_dir == tmp_path

    def test_accepts_path_string_coerced_to_path(self, tmp_path: Path):
        config = IdeaGenConfig(prompt_override_dir=str(tmp_path))
        assert isinstance(config.prompt_override_dir, Path)

    def test_stored_prompt_override_dir_is_path_type(self, tmp_path: Path):
        config = IdeaGenConfig(prompt_override_dir=tmp_path)
        assert isinstance(config.prompt_override_dir, Path)


# ---------------------------------------------------------------------------
# No filesystem side-effects in the config module itself
# ---------------------------------------------------------------------------


class TestConfigModuleHasNoFilesystemImports:
    def test_config_module_does_not_import_os(self):
        import ideagen.core.config as config_module

        source = inspect.getsource(config_module)
        assert "import os" not in source

    def test_config_module_does_not_import_open_builtin_directly(self):
        """open() calls signal side-effectful reads at import time."""
        import ideagen.core.config as config_module

        source = inspect.getsource(config_module)
        # 'open(' would indicate a direct call; 'Path.open' is also suspicious
        assert "open(" not in source

    def test_config_module_does_not_import_glob(self):
        import ideagen.core.config as config_module

        source = inspect.getsource(config_module)
        assert "import glob" not in source

    def test_config_module_does_not_import_shutil(self):
        import ideagen.core.config as config_module

        source = inspect.getsource(config_module)
        assert "import shutil" not in source
