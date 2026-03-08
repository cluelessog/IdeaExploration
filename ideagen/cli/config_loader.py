from __future__ import annotations
import logging
import tomllib
from pathlib import Path
from ideagen.core.config import IdeaGenConfig

logger = logging.getLogger("ideagen")

DEFAULT_CONFIG_PATH = Path("~/.ideagen/config.toml")


def load_config(config_path: Path | None = None) -> IdeaGenConfig:
    """Load config from TOML file, falling back to defaults."""
    path = (config_path or DEFAULT_CONFIG_PATH).expanduser()

    if not path.exists():
        logger.debug(f"No config file at {path}, using defaults")
        return IdeaGenConfig()

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return IdeaGenConfig(**data)
    except Exception as e:
        logger.warning(f"Failed to load config from {path}: {e}. Using defaults.")
        return IdeaGenConfig()


def _strip_none(obj: object) -> object:
    """Recursively remove None values from dicts (TOML can't serialize None)."""
    if isinstance(obj, dict):
        return {k: _strip_none(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_none(v) for v in obj]
    return obj


def save_config(config: IdeaGenConfig, config_path: Path | None = None) -> Path:
    """Save config to TOML file."""
    import tomli_w

    path = (config_path or DEFAULT_CONFIG_PATH).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = _strip_none(config.model_dump(mode="json"))
    with open(path, "wb") as f:
        tomli_w.dump(data, f)

    return path
