from __future__ import annotations
from pathlib import Path
import pytest
from ideagen.cli.config_loader import load_config, save_config
from ideagen.core.config import IdeaGenConfig


def test_load_config_returns_defaults_when_file_missing(tmp_path: Path) -> None:
    """load_config returns a default IdeaGenConfig when the file does not exist."""
    missing = tmp_path / "nonexistent.toml"
    config = load_config(missing)
    assert isinstance(config, IdeaGenConfig)
    assert config == IdeaGenConfig()


def test_load_config_parses_valid_toml(tmp_path: Path) -> None:
    """load_config correctly parses a TOML file with overridden values."""
    toml_content = b"""
[sources]
enabled = ["hackernews", "reddit"]
scrape_delay = 3.5

[providers]
default = "openai"

[storage]
database_path = "/tmp/test.db"

[generation]
ideas_per_run = 5
"""
    config_file = tmp_path / "config.toml"
    config_file.write_bytes(toml_content)

    config = load_config(config_file)

    assert isinstance(config, IdeaGenConfig)
    assert config.sources.enabled == ["hackernews", "reddit"]
    assert config.sources.scrape_delay == 3.5
    assert config.providers.default == "openai"
    assert config.storage.database_path == "/tmp/test.db"
    assert config.generation.ideas_per_run == 5


def test_save_config_writes_valid_toml(tmp_path: Path) -> None:
    """save_config writes a TOML file that can be read back."""
    config = IdeaGenConfig()
    output_path = tmp_path / "out" / "config.toml"

    returned_path = save_config(config, output_path)

    assert returned_path == output_path
    assert output_path.exists()
    # File should be non-empty
    assert output_path.stat().st_size > 0


def test_save_config_creates_parent_directories(tmp_path: Path) -> None:
    """save_config creates intermediate directories if they don't exist."""
    deep_path = tmp_path / "a" / "b" / "c" / "config.toml"
    assert not deep_path.parent.exists()

    save_config(IdeaGenConfig(), deep_path)

    assert deep_path.exists()


def test_round_trip_save_then_load(tmp_path: Path) -> None:
    """Saving then loading a config returns an equivalent IdeaGenConfig."""
    original = IdeaGenConfig()
    # Modify a few fields to ensure non-default values survive the round-trip
    original.sources.scrape_delay = 4.2
    original.generation.ideas_per_run = 7
    original.providers.default = "gemini"

    config_file = tmp_path / "config.toml"
    save_config(original, config_file)
    loaded = load_config(config_file)

    assert loaded.sources.scrape_delay == pytest.approx(4.2)
    assert loaded.generation.ideas_per_run == 7
    assert loaded.providers.default == "gemini"
    # Full equality check
    assert loaded == original
