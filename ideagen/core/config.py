from __future__ import annotations
from pathlib import Path
from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    enabled: list[str] = Field(default=["hackernews", "reddit", "producthunt", "twitter"])
    scrape_delay: float = 2.0
    proxy_url: str | None = None
    reddit_subreddits: list[str] = Field(default=["SaaS", "startups", "Entrepreneur", "smallbusiness"])


class ProviderConfig(BaseModel):
    default: str = "claude"
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    model: str | None = None  # Override model for the provider


class StorageConfig(BaseModel):
    database_path: str = "~/.ideagen/ideagen.db"
    output_dir: str = "./ideagen_output"


class GenerationConfig(BaseModel):
    ideas_per_run: int = 10
    domain: str = "software"
    target_segments: list[str] = Field(default_factory=list)
    dedup_threshold: float = 0.85


class IdeaGenConfig(BaseModel):
    sources: SourceConfig = Field(default_factory=SourceConfig)
    providers: ProviderConfig = Field(default_factory=ProviderConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    prompt_override_dir: Path | None = None
