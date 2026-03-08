from __future__ import annotations

SCHEMA_VERSION = 1

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    domain TEXT NOT NULL,
    config_snapshot TEXT NOT NULL DEFAULT '{}',
    content_hash TEXT NOT NULL DEFAULT '',
    total_items_scraped INTEGER NOT NULL DEFAULT 0,
    total_after_dedup INTEGER NOT NULL DEFAULT 0,
    sources_used TEXT NOT NULL DEFAULT '[]',
    ideas_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ideas (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    title TEXT NOT NULL,
    problem_statement TEXT NOT NULL,
    solution TEXT NOT NULL,
    domain TEXT NOT NULL,
    novelty_score REAL NOT NULL DEFAULT 0.0,
    content_hash TEXT NOT NULL DEFAULT '',
    report_json TEXT NOT NULL,
    wtp_score REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE INDEX IF NOT EXISTS idx_ideas_run_id ON ideas(run_id);
CREATE INDEX IF NOT EXISTS idx_ideas_domain ON ideas(domain);
CREATE INDEX IF NOT EXISTS idx_ideas_title ON ideas(title);
CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp);

CREATE TABLE IF NOT EXISTS scrape_cache (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    source TEXT NOT NULL,
    items_json TEXT NOT NULL,
    scraped_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);
"""
