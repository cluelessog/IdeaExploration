# IdeaGen

Automated idea generation from trending data. Scrapes Hacker News, Reddit, Product Hunt, and Twitter/X — then uses AI to identify pain points, market gaps, and generate business ideas targeting high willingness-to-pay audience segments.

## Quick Start

```bash
# Install (Python 3.11+ required)
pip install -e .

# Verify
ideagen --help

# Run idea generation (requires claude CLI installed and authenticated)
ideagen run --domain software

# Dry run (no AI calls, just shows what would be scraped)
ideagen run --dry-run

# Target specific audience segments
ideagen run --segment parents --segment pet_owners
```

## Requirements

- **Python 3.11+**
- **Claude CLI** installed and authenticated (`claude` must be on PATH)
  - Uses Claude Code Max plan via subprocess — no API key needed
  - Install: https://docs.anthropic.com/en/docs/claude-code

## Features

- **4 data sources** — all web scraping, no API keys needed:
  - Hacker News (Firebase REST API)
  - Reddit (old.reddit.com scraping)
  - Product Hunt (producthunt.com scraping)
  - Twitter/X (snscrape + ntscraper fallback)

- **22 built-in WTP segments** — audience categories with high willingness to pay:
  - Parents, Pet Owners, Small Business Owners, Remote Workers, Chronic Health, Elder Care, Brides, Homeowners, Fitness Enthusiasts, Freelancers, Students, Gamers, Investors, Travelers, New Parents, Career Changers, Hobbyists, Content Creators, Solo Entrepreneurs, Senior Citizens, ADHD/Neurodivergent, Sustainability-Focused

- **AI-powered pipeline**: collect → dedup → analyze → synthesize → refine → store

- **Multiple output modes**: single-shot, scheduled, interactive REPL

## Commands

```bash
ideagen run                    # Full pipeline: scrape + AI analysis
ideagen run --dry-run          # Preview without AI calls
ideagen run --cached           # Reuse last scrape, re-run AI only
ideagen run --domain health    # Focus on specific domain
ideagen run --count 20         # Generate 20 ideas (default: 10)
ideagen run --segment parents  # Target specific WTP segments

ideagen sources list           # Show available data sources
ideagen sources test           # Test connectivity to all sources

ideagen config init            # Create config file
ideagen config show            # Show current config

ideagen history list           # Browse past runs
ideagen history show <id>      # View a specific run
ideagen history prune --older-than 30d  # Clean old runs

ideagen schedule add --daily --time 09:00  # Schedule daily runs
ideagen schedule list          # Show active schedules

ideagen interactive            # Start interactive REPL
```

## Configuration

```bash
ideagen config init  # Creates ~/.ideagen/config.toml
```

Example `config.toml`:

```toml
[providers]
default = "claude"

[sources]
enabled = ["hackernews", "reddit", "producthunt", "twitter"]
scrape_delay = 2.0
reddit_subreddits = ["SaaS", "startups", "Entrepreneur", "smallbusiness"]

[generation]
ideas_per_run = 10
dedup_threshold = 0.85
target_segments = ["parents", "pet_owners", "small_business"]

[storage]
database_path = "~/.ideagen/ideagen.db"
```

## Alternative AI Providers

Claude CLI is the default (no API key needed with Max plan). Optional providers:

```bash
# OpenAI
pip install -e ".[openai]"
# Set provider.name = "openai" and provider.api_key in config

# Gemini
pip install -e ".[gemini]"
# Set provider.name = "gemini" and provider.api_key in config
```

## Architecture

Library-first design — all core logic is reusable without the CLI:

```
ideagen/
├── core/           # Models, config, pipeline, prompts, dedup, service
│   ├── models.py       # Pydantic v2 data structures
│   ├── config.py       # Pure config (no filesystem I/O)
│   ├── pipeline.py     # AI analysis pipeline (prompt logic)
│   ├── prompts.py      # Prompt templates with JSON schema
│   ├── service.py      # IdeaGenService orchestrator
│   ├── dedup.py        # Fuzzy dedup via rapidfuzz
│   └── wtp_segments.py # 22 WTP audience segments
├── sources/        # Data collectors (web scraping only)
├── providers/      # AI provider adapters (Claude, OpenAI, Gemini)
├── storage/        # SQLite persistence + JSON export
├── cli/            # Typer CLI (thin layer, no business logic)
└── utils/          # Retry, text extraction, logging, rate limiter
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=ideagen --cov-report=term-missing
```

## License

MIT
