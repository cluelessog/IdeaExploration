# IdeaGen Implementation Plan

**Created:** 2026-03-06
**Revised:** 2026-03-07 (Revision 4 -- stdin pipe, JSON extraction, CLI availability checks)
**Status:** APPROVED by Architect + Critic consensus
**Complexity:** HIGH
**Scope:** Greenfield Python project, ~48 files across 6 phases
**Python Version:** 3.11 minimum (required for stdlib `tomllib`)

---

## RALPLAN-DR Summary

### Principles (5)

1. **Library-First Architecture** -- Core logic is a standalone Python library. The CLI, scheduler, and future web/desktop layers are thin consumers. No business logic lives in the CLI layer.
2. **Provider Agnosticism** -- AI providers (Claude via CLI, optionally OpenAI, Gemini) and data sources (Reddit, HN, etc.) are behind abstract interfaces. Swapping or adding providers requires zero changes to core logic. Providers handle LLM communication ONLY; prompting logic lives in the core analysis pipeline.
3. **Structured Data Throughout** -- All internal data flows through Pydantic models. Ideas, analyses, scores, configs, and pipeline events are typed from creation to storage. No ad-hoc dicts. AI responses are validated via `Pydantic model_validate_json()`.
4. **Graceful Degradation** -- If a data source is unavailable (rate-limited, blocked, network error), the system continues with available sources and reports what was skipped. Never fail-all because one source fails.
5. **Progressive Complexity** -- The system works with zero config (sensible defaults, Claude via CLI, all 4 sources enabled by default since none need API keys). First run requires only an authenticated `claude` CLI session. All data sources use web scraping — no API keys or OAuth setup needed for any source.

### Decision Drivers (Top 3)

1. **Extensibility to Web/Desktop** -- The user explicitly wants API-ready service layer. Every architectural choice must ensure the core library works identically when called from CLI, REST API, or GUI.
2. **Data Source Reliability** -- All sources are scraped from public pages (no API keys needed). Scraping can be blocked or rate-limited, so the architecture must handle sources that may be temporarily unavailable. Polite scraping with delays and retries is essential.
3. **AI Provider Simplicity** -- The user is on Claude Code Max (unlimited usage, no per-token billing). The primary provider shells out to the `claude` CLI, avoiding SDK dependencies and API key management entirely. OpenAI and Gemini remain optional for users who want them.

### Viable Options

#### Option A: Monolithic Service Layer with Two-Tier AI Abstraction (SELECTED)

A single `IdeaGenService` orchestrates the pipeline: collect sources -> analyze gaps -> generate ideas -> score/rank -> store. Each stage is a composable step. AI providers are split into two layers: a low-level `AIProvider` (LLM communication only) and a high-level `AnalysisPipeline` (owns prompting logic and uses `AIProvider` for completions).

**Pros:**
- Simple mental model: one entry point for all modes (run/schedule/interactive)
- Easier to test end-to-end (mock the service, test the pipeline)
- Natural fit for CLI-first with future API wrapper
- Fewer moving parts for a greenfield project
- Two-tier AI split keeps prompts in one place (core) while providers stay thin and reusable
- Claude provider requires zero API keys -- just an authenticated `claude` CLI session

**Cons:**
- Service class may grow large over time (mitigate: decompose into stage-specific sub-services)
- Harder to parallelize stages independently (mitigate: async support from day one)

#### Option B: Event-Driven Pipeline with Message Queue

Each stage (collect, analyze, generate, score) is an independent worker. Stages communicate via an in-process event bus (or external queue for scale).

**Pros:**
- Maximum parallelism and stage independence
- Natural fit for distributed/cloud deployment
- Each stage independently testable and deployable

**Cons:**
- Massive overengineering for a CLI-first tool
- Adds infrastructure complexity (event bus, message serialization, error propagation)
- Debugging pipeline failures requires tracing across decoupled components
- **INVALIDATED:** The user specified CLI-first with future web extension, not a distributed system. The complexity cost vastly outweighs benefits at this stage. Can always refactor to event-driven later if scale demands it.

#### Option C: Plugin-Based Architecture with Entry Points

Every source, provider, and analyzer is a setuptools entry-point plugin. Third parties can add sources/providers by installing packages.

**Pros:**
- Maximum extensibility
- Clean separation via plugin contracts

**Cons:**
- Premature for a greenfield project with a known set of integrations
- Plugin discovery, lifecycle management, and error handling add significant complexity
- **PARTIALLY INVALIDATED:** The user specified a fixed set of sources and a primary CLI-based provider. Plugin architecture can be adopted later if community contributions become relevant. The abstract interface approach in Option A provides sufficient extensibility without plugin infrastructure overhead.

**Decision:** Option A with two-tier AI abstraction. The monolithic service with injected providers delivers the right balance of simplicity, testability, and extensibility. The `AIProvider` / `AnalysisPipeline` split keeps prompting logic centralized in core while providers remain thin LLM adapters.

---

## Resolved Decisions (Previously Open Questions)

These questions are now resolved with concrete decisions:

| Question | Decision | Rationale |
|----------|----------|-----------|
| LLM Interface | `claude` CLI subprocess (Claude Code Max plan, no API key needed) | User is on unlimited plan; `claude --output-format json` (via stdin pipe) avoids SDK dependency and API key management entirely |
| Cost tracking | Not needed (unlimited plan) | Claude Code Max has no per-token billing; optional providers (OpenAI/Gemini) are user's responsibility to monitor |
| TOML library | `tomllib` (stdlib 3.11+) + `tomli-w` for writing | Zero-dependency for reads; `tomli-w` only needed by CLI config commands |
| Dedup strategy | Fuzzy title match with `rapidfuzz` (threshold 0.85) | Good balance of accuracy vs cost; no LLM call needed for dedup |
| Scheduler | `APScheduler` (in-process) | Cross-platform (Windows/Mac/Linux) without system cron dependency |
| Python version | 3.11 minimum | Required for `tomllib`; broad enough adoption |
| Interactive REPL | Rich prompts (simple for v1) | Keep v1 simple; `prompt_toolkit` can be added later if needed |
| Scoring approach | Bundled with synthesis prompt; separate call for top-K refinement | Reduces API calls for bulk scoring; detailed analysis only for top ideas |
| Prompt customization | Fixed in code; optional override directory `~/.ideagen/prompts/` | Reliable defaults with escape hatch for power users |
| Config loading location | `IdeaGenConfig` Pydantic model in core; TOML loading in CLI layer | Core has no filesystem dependency; CLI handles I/O |
| Structured output | Prompt Claude to return JSON matching Pydantic schema; validate with `model_validate_json()` | No SDK-specific structured output features needed; works with any provider that returns text |
| Prompt delivery | Stdin pipe to `claude` CLI (not `-p` flag) | Avoids shell argument length limits on large prompts (>100KB) |
| JSON extraction | `extract_json()` utility strips markdown code fences before parsing | Claude sometimes wraps JSON in ` ```json ``` ` fences; utility handles this reliably |
| CLI availability | Startup check for `claude` CLI installed + authenticated | Clear error messages instead of cryptic subprocess exceptions |

---

## Context

IdeaGen is a greenfield Python CLI application that automates idea generation by combining trending data from multiple platforms with AI-powered analysis and synthesis. The system collects signals from Reddit, Hacker News, Product Hunt, and optionally Twitter/X, then uses LLMs to identify gaps, pain points, and opportunities, ultimately producing structured idea reports with market analysis, feasibility scores, and monetization strategies.

**Key API Constraints Discovered:**
- Reddit: Scraped via old.reddit.com (public HTML, no auth) or snscrape. Polite rate limiting required.
- Hacker News: Firebase REST API (free, no auth, no rate limit) — the only actual API used
- Product Hunt: Scraped via producthunt.com (public pages). May need Crawl4AI for JS-rendered content.
- Twitter/X: Scraped via snscrape (no auth, no API key) with ntscraper (Nitter) as fallback. All public data.
- Claude: Accessed via `claude` CLI subprocess; user is on Claude Code Max (unlimited usage); structured output via JSON prompting + Pydantic `model_validate_json()`

---

## Work Objectives

1. Build a Python library (`ideagen/`) that can be consumed by any interface (CLI, API, GUI)
2. Implement data source collectors with graceful degradation
3. Create a two-tier AI abstraction: thin `AIProvider` (LLM communication) + `AnalysisPipeline` (prompting logic)
4. Build a storage layer using SQLite for persistence with JSON export
5. Create a Typer-based CLI with `run`, `schedule`, and `interactive` subcommands
6. Implement configuration as a Pydantic model in core (TOML loading in CLI layer only)

---

## Guardrails

### Must Have
- All business logic in `ideagen/core/` -- zero business logic in CLI layer
- Pydantic models for all data structures (ideas, analyses, configs, pipeline events)
- Abstract base classes for data sources, AI providers, and storage backends
- SQLite storage with schema versioning
- All Pydantic models importable and validating in Phase 1 deliverable
- Async support for data collection (multiple sources in parallel)
- Structured output from AI providers via JSON prompting + Pydantic `model_validate_json()`
- `IdeaGenConfig` Pydantic model in core with no filesystem dependency; TOML loading in CLI only
- Error handling that never crashes the entire pipeline for a single source failure
- `AsyncIterator[PipelineEvent]` for progress reporting (not callbacks)
- Retry/backoff utility for all external API calls
- JSON schema included in prompts (generated via `Model.model_json_schema()`)

### Must NOT Have
- No web framework in initial implementation (no FastAPI/Flask yet -- just the service layer interface)
- No Docker/containerization in initial scope
- No paid API integrations for any data source — all sources use web scraping only
- No GUI code
- No database migrations framework (simple schema versioning is sufficient)
- No LangChain or heavy orchestration frameworks -- direct CLI subprocess / optional SDK usage only
- No filesystem I/O in core library (config loading, prompt file reading happens in CLI/consumer layer)
- No cost tracking or budget management (user is on unlimited plan)
- No `anthropic`, `openai`, or `google-genai` as required dependencies (Claude uses CLI subprocess; others are optional)

---

## Project Structure

```
ideagen/
  __init__.py                    # Package root, version
  __main__.py                    # python -m ideagen entry point

  # -- Core Library --
  core/
    __init__.py
    models.py                    # Pydantic models: Idea, MarketAnalysis, FeasibilityScore,
                                 #   PipelineEvent types (StageStarted, StageCompleted,
                                 #   SourceFailed, IdeaGenerated, PipelineComplete), etc.
    config.py                    # IdeaGenConfig Pydantic model ONLY (no file I/O)
    service.py                   # IdeaGenService: main orchestrator pipeline
                                 #   run() returns AsyncIterator[PipelineEvent]
                                 #   accepts CancellationToken for cooperative cancellation
    pipeline.py                  # AnalysisPipeline: owns prompting logic, uses AIProvider
                                 #   analyze(), synthesize(), score() -- prompt construction + parsing
    prompts.py                   # Prompt templates for analysis, synthesis, scoring
                                 #   (moved from providers/ -- prompts belong to core)
    wtp_segments.py              # Built-in WTP knowledge base: 22 high willingness-to-pay
                                 #   audience segments with scoring framework, emotional drivers,
                                 #   spending areas, and pain tolerance ratings
    dedup.py                     # Deduplication: fuzzy title match via rapidfuzz (local, no LLM)
    exceptions.py                # Custom exception hierarchy

  # -- Data Sources --
  sources/
    __init__.py
    base.py                      # Abstract base: DataSource protocol/ABC
    reddit.py                    # Reddit collector via web scraping (old.reddit.com / snscrape)
    hackernews.py                # HN collector via Firebase REST API (free, no auth)
    producthunt.py               # Product Hunt collector via web scraping (Crawl4AI / BeautifulSoup)
    twitter.py                   # Twitter/X collector via snscrape (no auth needed)
    registry.py                  # Source registry: discover and manage available sources

  # -- AI Providers (thin LLM adapters ONLY) --
  providers/
    __init__.py
    base.py                      # AIProvider ABC: async complete(system_prompt, user_prompt, response_type) -> T
                                 #   Handles LLM communication and structured output parsing ONLY
    claude.py                    # Claude provider via `claude` CLI subprocess
    openai_provider.py           # OpenAI provider (optional, requires `openai` package)
    gemini.py                    # Google Gemini provider (optional, requires `google-genai` package)
    registry.py                  # Provider registry: discover and manage available providers

  # -- Storage --
  storage/
    __init__.py
    base.py                      # StorageBackend ABC with pagination:
                                 #   search_ideas(query, offset, limit) -> list[Idea]
    sqlite.py                    # SQLite implementation
    json_export.py               # JSON file export for run mode output
    schema.py                    # Database schema definitions and versioning

  # -- CLI Layer --
  cli/
    __init__.py
    app.py                       # Typer app definition, top-level options
    config_loader.py             # TOML file loading -> IdeaGenConfig (filesystem I/O here)
    async_bridge.py              # asyncio.run() wrapper for Typer commands
    commands/
      __init__.py
      run.py                     # `ideagen run` -- single-shot batch generation
      schedule.py                # `ideagen schedule` -- APScheduler-based scheduling
      interactive.py             # `ideagen interactive` -- REPL-style refinement
      config_cmd.py              # `ideagen config` -- view/edit configuration
      history.py                 # `ideagen history` -- browse past runs
      sources_cmd.py             # `ideagen sources test` -- health check all scrapers
    formatters.py                # Rich-based output formatting for terminal
                                 #   Wraps AsyncIterator[PipelineEvent] with Rich progress
    callbacks.py                 # Typer callbacks for shared options (verbosity, config path)

  # -- Utilities --
  utils/
    __init__.py
    retry.py                     # Exponential backoff with jitter, configurable max retries
    rate_limiter.py              # Token bucket rate limiter for API calls
    async_helpers.py             # Async utilities for parallel source collection
    text.py                      # Text processing utilities (summarization, cleaning)
                                 #   Includes extract_json(): strips markdown code fences from LLM output
                                 #   before JSON parsing (handles ```json ... ``` wrapping)
    logging.py                   # Structured logging setup, library-level logger

# -- Project Root Files --
pyproject.toml                   # Project metadata, dependencies, entry points
                                 #   Uses >= minimum version constraints
README.md                        # Project documentation
config.example.toml              # Example configuration file
.gitignore                       # Includes .env, *.db, ideagen_output/

tests/
  __init__.py
  conftest.py                    # Shared fixtures (mock providers, sample data, temp configs)
  core/
    __init__.py
    test_models.py               # Phase 1 tests
    test_config.py               # Phase 1 tests
    test_pipeline.py             # Phase 3 tests (AnalysisPipeline)
    test_prompts.py              # Phase 3 tests
    test_dedup.py                # Phase 4 tests
    test_service.py              # Phase 4 tests (integration)
  sources/
    __init__.py
    test_hackernews.py           # Phase 2 tests
    test_reddit.py               # Phase 2 tests
    test_producthunt.py          # Phase 2 tests
  providers/
    __init__.py
    test_claude.py               # Phase 3 tests
    test_openai.py               # Phase 3 tests (optional provider)
    test_gemini.py               # Phase 3 tests (optional provider)
  storage/
    __init__.py
    test_sqlite.py               # Phase 4 tests
    test_json_export.py          # Phase 4 tests
  cli/
    __init__.py
    test_config_loader.py        # Phase 5 tests
    test_run.py                  # Phase 5 tests
    test_interactive.py          # Phase 5 tests
  integration/
    __init__.py
    test_pipeline_e2e.py         # Phase 6: full pipeline with mocked externals
    test_cli_e2e.py              # Phase 6: CLI via CliRunner
```

---

## Task Flow (6 Phases)

### Phase 1: Foundation and Core Models
**Dependencies:** None
**Deliverables:** Project skeleton, all Pydantic models, config model, abstract bases, utility foundations
**Phase Test Target:** `tests/core/test_models.py`, `tests/core/test_config.py` pass

**Tasks:**

1.1. **Initialize project structure with pyproject.toml**
   - Create `pyproject.toml` with metadata, `>= minimum` version constraints for dependencies:
     - Core: `pydantic>=2.0`, `httpx>=0.25`, `aiosqlite>=0.19`
     - Scraping: `beautifulsoup4>=4.12`, `snscrape>=0.7`, `crawl4ai>=0.3`
     - CLI: `typer>=0.9`, `rich>=13.0`
     - Utils: `rapidfuzz>=3.0`, `apscheduler>=3.10`, `tomli-w>=1.0`
   - Create `[project.optional-dependencies]` groups for optional AI providers:
     - `openai = ["openai>=1.0"]`
     - `gemini = ["google-genai>=1.0"]`
     - `all-providers = ["openai>=1.0", "google-genai>=1.0"]`
   - Note: `anthropic` is NOT a dependency -- Claude provider uses the `claude` CLI subprocess
   - Create `[project.scripts]` entry point: `ideagen = "ideagen.cli.app:main"`
   - Create all `__init__.py` files and package structure per project structure above
   - Create `config.example.toml`, `.gitignore`
   - **Acceptance:** `pip install -e .` succeeds; `ideagen --help` shows version; all packages importable; optional deps installable via `pip install -e ".[openai]"` or `pip install -e ".[all-providers]"`

1.2. **Define all Pydantic models in `core/models.py`**
   - `TrendingItem`: raw data from any source (title, url, score, source, timestamp, metadata)
   - `PainPoint`: extracted problem/complaint (description, frequency, severity, source_items)
   - `GapAnalysis`: identified market/feature gap (description, evidence, affected_audience)
   - `Idea`: full idea output (problem_statement, solution, domain, novelty_score, content_hash for dedup)
   - `MarketAnalysis`: audience, market_size_estimate, competitors, differentiation
   - `FeasibilityScore`: complexity (1-10), time_to_mvp, suggested_tech_stack, risks
   - `MonetizationAngle`: revenue_model, pricing_strategy, estimated_revenue_potential
   - `IdeaReport`: composite of Idea + MarketAnalysis + FeasibilityScore + MonetizationAngle + `target_segments: list[WTPSegment]` (which high-WTP audiences this idea serves) + `wtp_score: float` (composite WTP attractiveness score)
   - `RunResult`: collection of IdeaReports + metadata (timestamp, sources_used, config, content_hash for run dedup)
   - `Domain` enum: SOFTWARE_SAAS, BROAD_BUSINESS, CONTENT_MEDIA
   - `WTPSegment` enum/dataclass: 22 high willingness-to-pay audience segments with metadata:
     - Top 5 (score 4.3+): PARENTS, CHRONIC_HEALTH, ELDER_CARE, FITNESS, SMALL_BUSINESS
     - High WTP: PET_OWNERS, BRIDES_GROOMS, HOBBYISTS, CREATORS, HOMEOWNERS, CAREER_SEEKERS, NEURODIVERGENT, INVESTORS, FERTILITY, STUDENTS, LEGAL
     - Medium-High WTP: REMOTE_WORKERS, LIFE_TRANSITIONS, ANXIOUS_SAFETY, LUXURY_STATUS, IMMIGRANTS, KNOWLEDGE_WORKERS
     - Each segment has: `name`, `emotional_driver`, `spending_areas: list[str]`, `pain_tolerance` (1-5), `wtp_score` (weighted composite)
   - `WTPScoringCriteria`: 6 weighted dimensions — emotional_intensity (0.25), pain_frequency (0.20), price_insensitivity (0.20), market_size (0.15), accessibility (0.10), defensibility (0.10)
   - **Pipeline event types** (all inherit from `PipelineEvent` base):
     - `StageStarted(stage: str, metadata: dict)`
     - `StageCompleted(stage: str, duration_ms: int, metadata: dict)`
     - `SourceFailed(source: str, error: str)`
     - `IdeaGenerated(idea: Idea, index: int, total: int)`
     - `PipelineComplete(result: RunResult)`
   - `CancellationToken`: wrapper around `asyncio.Event` for cooperative cancellation
   - **Acceptance:** All models instantiate with valid data; validation rejects invalid data; JSON serialization round-trips cleanly; pipeline event types are importable and typed; CancellationToken can be set and checked; `IdeaReport.model_json_schema()` produces valid JSON schema suitable for prompt inclusion

1.3. **Define IdeaGenConfig Pydantic model in `core/config.py`**
   - Pydantic Settings model with sections: `sources`, `providers`, `storage`, `generation`
   - Provider config defaults to `claude` (CLI-based, no API key needed)
   - Optional environment variable overrides for non-Claude API keys (`OPENAI_API_KEY`, `GEMINI_API_KEY`, etc.)
   - Sensible defaults: Claude provider (CLI), all 4 sources enabled, SQLite storage, 10 ideas per run
   - Optional `proxy_url: str | None` for users in regions where scraping is blocked (passed to httpx/snscrape)
   - Optional `scrape_delay: float` per source (default 2.0s) for polite rate limiting
   - **NO file I/O in this module** -- this is a pure data model with defaults and validation
   - Config model accepts optional `prompt_override_dir: Path | None` for user prompt overrides
   - **Acceptance:** Config model instantiates with defaults (no API keys required for default Claude provider); env vars override values for optional providers; invalid config raises clear ValidationError; no filesystem imports in this module

1.4. **Create abstract base classes**
   - `sources/base.py`: `DataSource` ABC with `async collect(domain, limit) -> list[TrendingItem]`, `is_available() -> bool`, `name` property, `PARSER_VERSION: str` class constant (e.g., `"1.0"`) — bumped when scraper parsing logic changes, helps diagnose which scraper needs updating when HTML structure changes
   - `providers/base.py`: `AIProvider` ABC with single method: `async complete(system_prompt: str | None, user_prompt: str, response_type: type[T]) -> T` -- handles LLM communication and structured output parsing ONLY. The provider constructs the appropriate request, gets text/JSON back, and validates with `Pydantic model_validate_json()`. Generic type parameter `T` is bound to `BaseModel`.
   - `storage/base.py`: `StorageBackend` ABC with `save_run(RunResult)`, `get_runs(filters)`, `get_idea(id)`, `search_ideas(query, offset=0, limit=50) -> list[Idea]` (paginated)
   - `core/exceptions.py`: `IdeaGenError`, `SourceUnavailableError`, `ProviderError`, `ConfigError`, `StorageError`
   - **Acceptance:** ABCs enforce method signatures; concrete classes that miss methods fail at instantiation; `AIProvider` has only `complete()` method with the new signature; `StorageBackend.search_ideas` accepts offset/limit

1.5. **Implement cross-cutting utilities**
   - `utils/retry.py`: Exponential backoff with jitter, configurable max retries (default 3), configurable base delay (default 1s), max delay cap (default 60s). Decorator `@with_retry(max_retries=3, base_delay=1.0)` for async functions.
   - `utils/logging.py`: Structured logging setup using Python `logging` module. Library-level logger (`ideagen`). Structured formatter that outputs JSON in production, human-readable in dev. `setup_logging(level, format)` function for CLI to call.
   - `utils/text.py`: Include `extract_json(text: str) -> str` utility that strips markdown code fences (` ```json ... ``` `) from LLM output before JSON parsing. Also handles bare ``` fences, leading/trailing whitespace, and multiple JSON blocks (returns first valid one).
   - **Acceptance:** Retry decorator retries on exception with exponential backoff; logging outputs structured format; `extract_json()` correctly strips markdown fences and returns clean JSON string

---

### Phase 2: Data Source Collectors
**Dependencies:** Phase 1
**Deliverables:** Working scrapers for HN, Reddit, Product Hunt, and Twitter/X — all without login or API keys
**Phase Test Target:** `tests/sources/test_hackernews.py`, `tests/sources/test_reddit.py`, `tests/sources/test_producthunt.py` pass

**Tasks:**

2.1. **Implement Hacker News collector (`sources/hackernews.py`)**
   - Fetch top/best/show/ask stories from Firebase REST API via `httpx` (free, no auth, no rate limit)
   - Extract title, URL, score, comment count, timestamp
   - Filter by domain relevance using keyword matching
   - No login or API key required
   - Uses `@with_retry` decorator for network resilience
   - **Acceptance:** Returns list of TrendingItems from live HN API; handles network errors; filters by domain keywords; zero config needed
   - **Tests:** `tests/sources/test_hackernews.py` -- mock httpx responses, test filtering, test error handling

2.2. **Implement Reddit collector via web scraping (`sources/reddit.py`)**
   - **Scrape old.reddit.com** (simpler HTML, no JavaScript required) via `httpx` + `BeautifulSoup`
   - Alternatively use `snscrape` library which supports Reddit without auth
   - Scrape configurable subreddits per domain (e.g., r/SaaS, r/startups, r/Entrepreneur for SOFTWARE_SAAS)
   - Default subreddit mappings per domain in config
   - Extract: post title, URL, score, comment count, flair, timestamp
   - **No login, no OAuth, no API key required** — scrapes public pages only
   - Rate limit scraping to be polite (1 request per 2 seconds, configurable)
   - Uses `@with_retry` decorator for network resilience
   - Handle anti-scraping: rotate User-Agent, respect robots.txt crawl delay
   - **Acceptance:** Returns TrendingItems from configured subreddits; no credentials needed; polite rate limiting; handles 429/503 responses with backoff
   - **Tests:** `tests/sources/test_reddit.py` -- mock HTML responses, test parsing, test rate limiting

2.3. **Implement Product Hunt collector via web scraping (`sources/producthunt.py`)**
   - **Scrape producthunt.com** via `Crawl4AI` (outputs clean markdown, handles JS rendering) or `httpx` + `BeautifulSoup` for static pages
   - Fetch today's/this week's featured products from the homepage and topic pages
   - Extract: product name, tagline, description, upvote count, topics/tags, maker info
   - **No login or API key required** — scrapes public product listings
   - Rate limit scraping (1 request per 3 seconds)
   - Uses `@with_retry` decorator for network resilience
   - **Acceptance:** Returns TrendingItems from Product Hunt; no credentials needed; extracts product metadata accurately; handles page structure changes gracefully
   - **Tests:** `tests/sources/test_producthunt.py` -- mock HTML responses, test parsing, test error handling

2.4. **Implement Twitter/X collector via scraping and source registry (`sources/twitter.py`, `sources/registry.py`)**
   - **Scrape Twitter/X using `snscrape`** — no API key, no login, no auth required
   - `snscrape` supports: hashtag search, user tweets, keyword search, trending topics
   - Collect trending tech/business discussions, pain point threads, product complaints
   - Configurable search queries per domain (e.g., "SaaS pain point", "startup idea", "I wish there was")
   - Extract: tweet text, author, engagement (likes/retweets/replies), timestamp, hashtags
   - **No login required** — snscrape accesses public data without authentication
   - Rate limit to avoid detection (configurable delay between requests)
   - **Fallback:** If snscrape fails, try `ntscraper` (Nitter-based) as backup
   - Source registry: auto-discover all sources (all enabled by default since none need credentials)
   - `registry.get_available_sources()` returns all sources (no credential check needed)
   - **Acceptance:** Twitter collector returns real trending items; no API key needed; snscrape fallback to ntscraper works; registry returns all 4 sources by default
   - **Tests:** `tests/sources/test_twitter.py` -- mock snscrape output, test query construction, test fallback

2.5. **Implement rate limiter utility (`utils/rate_limiter.py`)**
   - Token bucket algorithm with configurable rate and burst
   - Per-source rate limit configuration
   - Async-compatible (works with asyncio)
   - **Acceptance:** Rate limiter throttles requests to configured QPM; burst handling works; async await integration

---

### Phase 3: AI Provider Layer (Two-Tier)
**Dependencies:** Phase 1 (models)
**Deliverables:** Thin AI providers (Claude CLI + optional OpenAI/Gemini), AnalysisPipeline with prompt system, provider registry
**Phase Test Target:** `tests/providers/test_claude.py`, `tests/providers/test_openai.py`, `tests/providers/test_gemini.py`, `tests/core/test_pipeline.py`, `tests/core/test_prompts.py` pass

**Tasks:**

3.1. **Build prompt template system (`core/prompts.py`)**
   - Prompt templates for each pipeline stage (f-string or Jinja2):
     - `analyze_trends`: Given trending items, extract pain points and complaints
     - `identify_gaps`: Given pain points across sources, identify market/feature gaps
     - `synthesize_ideas`: Given gaps + domain + target WTP segment(s), generate novel idea proposals (includes initial scoring). When segment is specified, prompts include segment metadata (emotional drivers, spending areas, pain tolerance) to focus idea generation on high-WTP audiences.
     - `refine_top_ideas`: Given top-K ideas, produce detailed feasibility + market analysis + monetization. Includes WTP segment scoring — ideas targeting known high-WTP segments get boosted.
   - Templates include domain context, WTP segment data (from built-in knowledge base), and structured output instructions with JSON schema (generated via `Model.model_json_schema()`)
   - Each prompt explicitly instructs the LLM to return valid JSON matching the provided schema
   - **WTP Knowledge Base integration:** Prompts inject relevant segment data (emotional drivers, spending patterns, pain tolerance) so the LLM generates ideas calibrated to audiences that actually spend money. See `.omc/research/high-wtp-segments.md` for full research.
   - Support optional override: if `~/.ideagen/prompts/{template_name}.txt` exists, use it instead of built-in
   - Prompt loader function that checks override dir first, falls back to built-in
   - **Acceptance:** Templates render correctly with sample data; output instructions include valid JSON schema matching Pydantic models; override directory is checked if configured; missing override falls back to built-in

3.2. **Implement Claude provider via CLI subprocess (`providers/claude.py`)**
   - Shell out to `claude` CLI via `asyncio.create_subprocess_exec()` for async
   - **Prompt delivery via stdin pipe** (not `-p` flag) to avoid shell argument length limits on large prompts:
     - `echo <prompt> | claude --output-format json` (conceptually)
     - In code: `proc = await asyncio.create_subprocess_exec("claude", "--output-format", "json", stdin=PIPE, stdout=PIPE, stderr=PIPE)` then `stdout, stderr = await proc.communicate(input=prompt_bytes)`
   - **Startup check:** On first use, verify `claude` CLI is installed (`shutil.which("claude")`) and authenticated (run `claude --version` or similar). If missing, raise `ProviderError("Claude CLI not found. Install Claude Code: https://docs.anthropic.com/en/docs/claude-code")`. If not authenticated, raise `ProviderError("Claude CLI not authenticated. Run 'claude' to log in.")`.
   - The `async complete(system_prompt, user_prompt, response_type)` method:
     1. Constructs the full prompt (system + user + JSON schema instructions)
     2. Pipes prompt to `claude` CLI via stdin
     3. Extracts JSON from stdout using `extract_json()` utility (strips markdown code fences if present)
     4. Validates with `response_type.model_validate_json(raw_json)` and returns the typed model
   - Auth is handled by the user's existing Claude Code session -- no API keys needed
   - Support configurable model via `--model` flag if the CLI supports it
   - Handle subprocess errors (non-zero exit, timeout) AND parse errors (`ValidationError`, malformed JSON) via `@with_retry` -- retries on both subprocess failures and JSON validation failures
   - **Acceptance:** Returns validated Pydantic models from Claude CLI output; handles subprocess errors without crashing; no API key configuration required; JSON output parses and validates correctly; clear error if `claude` CLI not installed or not authenticated; large prompts (>100KB) work via stdin pipe
   - **Tests:** `tests/providers/test_claude.py` -- mock subprocess calls, test JSON parsing, test markdown fence stripping, test error handling, test retry on malformed output, test missing CLI error message, test large prompt via stdin

3.3. **Implement OpenAI provider (optional) (`providers/openai_provider.py`)**
   - Use `openai` SDK with structured output / JSON mode (requires `pip install ideagen[openai]`)
   - Implement `async complete(system_prompt, user_prompt, response_type) -> T` method
   - Include JSON schema in prompt; validate response with `model_validate_json()`
   - Support configurable model (gpt-4o, gpt-4o-mini, etc.)
   - Guard import: `try: import openai except ImportError: raise ConfigError("Install openai: pip install ideagen[openai]")`
   - **Acceptance:** Returns validated Pydantic models; model is configurable; clear error if openai package not installed
   - **Tests:** `tests/providers/test_openai.py` -- mock openai SDK

3.4. **Implement Gemini provider (optional) (`providers/gemini.py`)**
   - Use `google-genai` SDK (requires `pip install ideagen[gemini]`)
   - Implement `async complete(system_prompt, user_prompt, response_type) -> T` method
   - Include JSON schema in prompt; validate response with `model_validate_json()`
   - Support configurable model (gemini-2.0-flash, gemini-2.5-pro, etc.)
   - Guard import: `try: import google.genai except ImportError: raise ConfigError("Install google-genai: pip install ideagen[gemini]")`
   - **Acceptance:** Returns validated Pydantic models; model is configurable; clear error if google-genai package not installed
   - **Tests:** `tests/providers/test_gemini.py` -- mock google-genai SDK

3.5. **Build AnalysisPipeline and provider registry (`core/pipeline.py`, `providers/registry.py`)**
   - `AnalysisPipeline` class in `core/pipeline.py`:
     - Constructor takes `AIProvider` instance and optional prompt override dir
     - `async analyze(items: list[TrendingItem]) -> list[PainPoint]` -- constructs prompt from template (including JSON schema), calls `provider.complete()`
     - `async synthesize(gaps: list[GapAnalysis], domain: Domain) -> list[Idea]` -- constructs prompt, calls `provider.complete()`
     - `async score(ideas: list[Idea]) -> list[IdeaReport]` -- bulk scoring bundled in prompt; separate detailed call for top-K
     - All prompting logic lives HERE, not in providers
     - The `IdeaReport` composite model can be used as-is in prompts (no need to decompose for structured output)
   - `providers/registry.py`: Select provider based on config. `get_provider(name, config) -> AIProvider`. Default is `claude` (CLI-based). For `openai`/`gemini`, check that the optional package is installed and API key is present. Fallback chain if primary fails.
   - **Acceptance:** AnalysisPipeline calls provider.complete() with correct prompts including JSON schema; prompt construction is testable independently of LLM; provider registry defaults to Claude CLI; optional providers require both package and API key; missing optional package returns clear error
   - **Tests:** `tests/core/test_pipeline.py` -- mock AIProvider, verify prompt construction and response parsing

---

### Phase 4: Core Pipeline, Dedup, and Storage
**Dependencies:** Phases 1-3
**Deliverables:** Working end-to-end pipeline with event streaming, dedup, SQLite storage, JSON export
**Phase Test Target:** `tests/core/test_dedup.py`, `tests/core/test_service.py`, `tests/storage/test_sqlite.py`, `tests/storage/test_json_export.py` pass

**Tasks:**

4.1. **Implement deduplication module (`core/dedup.py`)**
   - Fuzzy title match using `rapidfuzz` with configurable threshold (default 0.85)
   - `deduplicate(items: list[TrendingItem]) -> list[TrendingItem]` -- removes near-duplicates across sources
   - Merge metadata from duplicate items (keep highest score, union of sources)
   - Content hash generation for `Idea` and `RunResult` models (for run dedup detection)
   - **This is local string matching ONLY -- no LLM calls**
   - **Acceptance:** Near-identical titles from different sources are merged; threshold is configurable; content hashes are deterministic; no external API calls
   - **Tests:** `tests/core/test_dedup.py` -- test fuzzy matching, threshold behavior, metadata merging, hash generation

4.2. **Implement IdeaGenService orchestrator (`core/service.py`)**
   - Pipeline: collect -> dedup -> analyze -> synthesize -> score -> store
   - `async run(config, cancellation_token?, dry_run=False, cached=False) -> AsyncIterator[PipelineEvent]`:
     - Yields `StageStarted` / `StageCompleted` events at each stage
     - Yields `SourceFailed` if a source errors (pipeline continues)
     - Yields `IdeaGenerated` for each idea produced
     - Yields `PipelineComplete` with final `RunResult`
     - Checks `CancellationToken` between stages for cooperative cancellation
   - **`--dry-run` mode:** Runs collect + dedup stages only. Displays what sources were scraped, how many items found, what prompts WOULD be sent to Claude — but makes zero LLM calls. Useful for debugging scrapers and previewing pipeline behavior.
   - **`--cached` mode:** Skips collect stage entirely. Loads the most recent scrape data from SQLite (raw `TrendingItem`s from last run). Re-runs dedup + all LLM stages with fresh prompts. Useful when sources are down or for iterating on prompt quality without re-scraping.
   - Async execution: collect from all sources in parallel via `asyncio.gather(return_exceptions=True)`
   - Accept domain filter, source filter, segment filter, idea count, provider selection
   - Dedup runs BEFORE AI analysis (local, cheap) -- AI clustering is part of AnalysisPipeline.analyze()
   - If ALL sources return zero items after dedup, abort with clear message ("No trending data found") instead of sending empty prompts
   - **Acceptance:** Full pipeline runs end-to-end; events yield at each stage; partial source failures don't halt pipeline; cancellation token stops pipeline between stages; dry-run shows plan without LLM calls; cached mode reuses last scrape data; zero-item abort works
   - **Tests:** `tests/core/test_service.py` -- mock sources + pipeline, verify event sequence, test cancellation, test partial failure, test dry-run mode, test cached mode, test zero-item abort

4.3. **Implement SQLite storage (`storage/sqlite.py`)**
   - Schema: `runs` table (id, timestamp, config_snapshot, domain, content_hash), `ideas` table (id, run_id, all IdeaReport fields as JSON + indexed fields, content_hash), `scrape_cache` table (id, run_id, source, items_json, scraped_at) — stores raw TrendingItems per source for `--cached` mode
   - CRUD operations: save run, list runs, get ideas by run, search ideas by keyword
   - **Paginated search:** `search_ideas(query, offset=0, limit=50) -> list[Idea]`
   - Schema versioning via a `schema_version` table
   - Use aiosqlite for async compatibility
   - Default database location: `~/.ideagen/ideagen.db`
   - Run dedup detection: warn if content_hash matches a previous run
   - **Acceptance:** Runs and ideas persist across CLI invocations; search returns paginated results; schema version tracked; async operations work; duplicate run detection works
   - **Tests:** `tests/storage/test_sqlite.py` -- test CRUD, pagination, schema versioning, content hash dedup

4.4. **Implement JSON export (`storage/json_export.py`)**
   - Export RunResult to pretty-printed JSON file
   - Export individual IdeaReport to JSON
   - Configurable output directory (default: `./ideagen_output/`)
   - **Acceptance:** JSON files are valid, human-readable, and contain all model fields; output directory is configurable
   - **Tests:** `tests/storage/test_json_export.py` -- test export format, directory creation

---

### Phase 5: CLI Layer
**Dependencies:** Phase 4
**Deliverables:** Complete CLI with all subcommands, config loading, async bridge
**Phase Test Target:** `tests/cli/test_config_loader.py`, `tests/cli/test_run.py`, `tests/cli/test_interactive.py` pass

**Tasks:**

5.1. **Build CLI skeleton, config loader, and async bridge (`cli/app.py`, `cli/config_loader.py`, `cli/async_bridge.py`, `cli/formatters.py`, `cli/callbacks.py`)**
   - `cli/config_loader.py`: Load TOML file using `tomllib` (read) and `tomli-w` (write). Default path: `~/.ideagen/config.toml`, overridable via `--config`. Returns `IdeaGenConfig` instance. For optional providers (OpenAI/Gemini), documents that API keys should be set via env vars.
   - `cli/async_bridge.py`: `def run_async(coro)` wrapper using `asyncio.run()`. All Typer commands that call async service methods use this bridge. Handles `KeyboardInterrupt` -> sets CancellationToken.
   - `cli/app.py`: Typer app with `--config`, `--verbose`, `--quiet`, `--version` global options
   - `cli/formatters.py`: Rich-based formatters: idea cards, score bars, tables. `PipelineEventRenderer` class that consumes `AsyncIterator[PipelineEvent]` and renders Rich progress display (spinners, stage transitions, idea count).
   - `cli/callbacks.py`: Shared callbacks for config loading and provider initialization
   - **Acceptance:** `ideagen --help` shows all commands; `--version` prints version; Rich formatting renders correctly; config loads from TOML into IdeaGenConfig; async bridge properly wraps coroutines; Ctrl+C triggers cooperative cancellation
   - **Tests:** `tests/cli/test_config_loader.py` -- test TOML parsing, env var overrides, missing file defaults

5.2. **Implement `run` command (`cli/commands/run.py`)**
   - Options: `--domain`, `--segment` (target WTP audience, e.g. `parents`, `pet_owners`, `small_business`; multiple allowed), `--sources`, `--provider`, `--count`, `--output` (file path), `--format` (json/table/markdown), `--dry-run` (show pipeline plan without executing LLM calls), `--cached` (reuse last scrape data, only re-run LLM stages)
   - Uses async bridge to call `IdeaGenService.run()`
   - Consumes `AsyncIterator[PipelineEvent]` via `PipelineEventRenderer` for live progress
   - Saves to storage and optionally exports to file
   - **Acceptance:** `ideagen run --domain software` produces idea reports; output saves to file; Rich progress shown during execution via event stream; all options work

5.3. **Implement `schedule` command (`cli/commands/schedule.py`)**
   - Uses APScheduler (in-process) for cross-platform scheduling
   - Subcommands: `schedule add` (create schedule), `schedule list` (view schedules), `schedule remove` (delete schedule)
   - Store schedule metadata in SQLite
   - Support daily and weekly frequencies with configurable time
   - **Acceptance:** `schedule add --daily --time 09:00` creates a schedule; `schedule list` shows active schedules; `schedule remove` cleans up; works on Windows/Mac/Linux

5.4. **Implement `interactive` command (`cli/commands/interactive.py`)**
   - REPL loop using Rich Prompt (simple for v1)
   - Steps: (1) run generation, (2) display summary table, (3) user selects idea to drill into, (4) refine/expand/pivot options, (5) export selected ideas
   - Commands within REPL: `list`, `detail <id>`, `refine <id>`, `similar <id>`, `export`, `new`, `quit`
   - Uses async bridge for AI calls within REPL
   - **Acceptance:** Interactive session starts; ideas display in table; selecting an idea shows full detail; refine generates variations; export saves selected ideas

5.5. **Implement `config`, `history`, and `sources` commands (`cli/commands/config_cmd.py`, `cli/commands/history.py`, `cli/commands/sources_cmd.py`)**
   - `config show`: display current configuration (redact any optional provider API keys)
   - `config init`: create default config file interactively (uses `tomli-w` for writing)
   - `config set <key> <value>`: update individual config values
   - `history list [--offset N --limit N]`: show past runs with summary (paginated)
   - `history show <run_id>`: display full results of a past run
   - `history export <run_id>`: export past run to file
   - `history prune --older-than 30d`: delete old runs to manage DB size
   - `sources test`: health check that pings all 4 sources and reports status (✓ working / ✗ blocked / ⚠ slow). Useful for debugging when a scraper breaks.
   - **Acceptance:** Config commands read/write TOML file correctly; optional provider API keys are redacted in display; history commands use paginated queries; `history prune` deletes runs older than threshold; `sources test` reports live status of each source

---

### Phase 6: Integration/E2E Tests, Polish, and Documentation
**Dependencies:** Phases 1-5
**Deliverables:** Integration test suite, E2E tests, README, example configs
**Note:** Unit tests for each module are written in their respective phases (co-located). This phase covers integration/E2E tests and documentation ONLY.

**Tasks:**

6.1. **Write integration tests (`tests/integration/test_pipeline_e2e.py`)**
   - Test full IdeaGenService pipeline with all mocked external dependencies (sources + AI provider)
   - Verify complete event sequence: StageStarted -> StageCompleted for each stage -> PipelineComplete
   - Test cancellation mid-pipeline
   - Test partial source failure (one source errors, pipeline continues)
   - Test run deduplication detection
   - **Acceptance:** Full pipeline produces valid RunResult with expected event sequence; cancellation works; degradation works

6.2. **Write CLI E2E tests (`tests/integration/test_cli_e2e.py`)**
   - Test CLI commands via Typer's CliRunner
   - Test `run` command with various option combinations
   - Test `config init` creates valid TOML
   - Test `history list` with pagination options
   - Test error display for missing `claude` CLI, unavailable optional providers
   - **Acceptance:** CLI commands produce expected output; error messages are user-friendly; exit codes are correct

6.3. **Write README and documentation**
   - Installation instructions (pip install, Python 3.11+ requirement)
   - Quick start guide (first run with minimal config: just an authenticated `claude` CLI session -- no API keys needed)
   - Configuration reference (all TOML sections, env var overrides for optional providers)
   - Optional provider setup guide (how to install and configure OpenAI/Gemini)
   - Data source info: how scraping works, rate limiting, what to do if a source is blocked
   - Architecture overview: two-tier AI abstraction, pipeline events, library-first design
   - **Acceptance:** New user can install and run first generation following README alone with just `claude` CLI authenticated; optional provider setup is clearly documented

---

## Success Criteria

1. `pip install -e .` installs the project with all dependencies (Python 3.11+); no AI SDK packages required for default usage
2. `ideagen run --domain software` produces at least 5 idea reports with all fields populated (problem, solution, market analysis, feasibility, monetization) using Claude CLI subprocess
3. `ideagen run` works with only an authenticated `claude` CLI session and no other configuration (HN source, Claude CLI provider, all defaults)
4. `ideagen run --segment parents --segment pet_owners` generates ideas specifically targeting high-WTP audiences with segment-aware scoring
5. Adding a new AI provider requires only: (a) new file in `providers/`, (b) implement `AIProvider.complete()`, (c) add to registry -- NO changes to prompting logic
6. Adding a new data source requires only: (a) new file in `sources/`, (b) implement `DataSource` ABC, (c) add to config
7. Ideas persist in SQLite and can be retrieved via `ideagen history` with pagination
8. Interactive mode allows drilling into and refining generated ideas
9. Pipeline completes successfully even if 1 or more sources fail, emitting `SourceFailed` events
10. All unit tests pass in their respective phases; integration/E2E tests pass in Phase 6; >80% overall coverage
11. `CancellationToken` (Ctrl+C in CLI) stops the pipeline cooperatively between stages
12. Optional providers (OpenAI, Gemini) can be installed and used via `pip install ideagen[openai]` / `pip install ideagen[gemini]`

---

## ADR: Architecture Decision Record

**Decision:** Monolithic service layer with two-tier AI abstraction, Claude CLI subprocess as primary provider, and event-driven progress reporting (Option A, refined)

**Drivers:**
1. CLI-first with future web/desktop extensibility -- service returns `AsyncIterator[PipelineEvent]`, consumable by any interface
2. Data source unreliability requires graceful degradation -- `SourceFailed` events + pipeline continuation
3. Claude Code Max plan eliminates API key management and cost concerns -- `claude` CLI subprocess is the simplest, most reliable path

**Alternatives Considered:**
- Event-driven pipeline with message queue (Option B): Invalidated due to overengineering for CLI-first scope
- Plugin-based architecture (Option C): Partially invalidated; abstract interfaces provide sufficient extensibility without plugin infrastructure
- Anthropic Python SDK for Claude: Invalidated because user is on Claude Code Max with unlimited usage; the `claude` CLI is already authenticated, requires no API key management, and avoids an SDK dependency entirely. Subprocess approach is simpler and aligns with the user's existing workflow.
- Direct SDK usage for all providers: Replaced with CLI subprocess for Claude (primary) and optional SDK installs for OpenAI/Gemini. This keeps the default install lightweight with zero AI SDK dependencies.

**Why Chosen:** The two-tier split (`AIProvider` for LLM calls, `AnalysisPipeline` for prompting) keeps providers thin and interchangeable while centralizing prompt logic. The Claude CLI subprocess provider is the simplest possible implementation -- no SDK, no API keys, no token tracking. `AsyncIterator[PipelineEvent]` is more composable than callbacks -- any consumer (CLI, API, GUI) can process events in their own way. Structured output is achieved via JSON schema in prompts + Pydantic `model_validate_json()`, which works identically across all providers.

**Key Architectural Decisions:**
- `AIProvider.complete(system_prompt, user_prompt, response_type)` is the ONLY provider interface method -- providers are thin LLM adapters
- Claude provider shells out to `claude` CLI subprocess -- no SDK dependency, no API key needed
- OpenAI and Gemini are optional providers installed via extras (`pip install ideagen[openai]`)
- Structured output via JSON schema in prompts + `model_validate_json()` -- works with any provider, no SDK-specific features needed
- `AnalysisPipeline` owns all prompt construction and response parsing -- single place to change prompting logic
- `IdeaGenService.run()` returns `AsyncIterator[PipelineEvent]` -- not callbacks, not return value
- `IdeaGenConfig` is a pure Pydantic model in core -- TOML loading is CLI-layer responsibility
- Deduplication is local fuzzy matching (`rapidfuzz`) -- separate from AI clustering in `AnalysisPipeline`
- Pagination in `StorageBackend.search_ideas(query, offset, limit)` -- prepared for large datasets
- `CancellationToken` (wrapping `asyncio.Event`) for cooperative pipeline cancellation
- No cost tracking -- user is on Claude Code Max (unlimited); optional provider costs are user's responsibility

**Consequences:**
- IdeaGenService may need decomposition if it grows beyond ~300 lines
- Async support is required from day one (already planned)
- Adding a new analysis step requires changes to `AnalysisPipeline` and `core/prompts.py` (but NOT to any provider)
- `rapidfuzz` is a compiled dependency -- may need build tools on some platforms
- `APScheduler` runs in-process -- schedule persists only while process runs (acceptable for CLI; future daemon mode could address this)
- Claude CLI subprocess introduces a process-spawn overhead per LLM call (acceptable for batch pipeline; may need optimization for interactive REPL with rapid iterations)
- If user switches away from Claude Code Max, they would need to either configure an optional provider with API key or adapt the CLI provider

**Follow-ups:**
- Phase 7 (future): FastAPI service layer wrapping IdeaGenService -- consumes `AsyncIterator[PipelineEvent]` via SSE
- Phase 8 (future): Additional scraping sources (IndieHackers, GitHub Trending, LinkedIn posts, Google Trends)
- Phase 9 (future): Plugin entry points if community contribution becomes relevant
- Phase 10 (future): Prompt versioning and A/B testing infrastructure
- Phase 11 (future): Consider `claude-code-sdk` Python package as alternative to raw subprocess if it matures
