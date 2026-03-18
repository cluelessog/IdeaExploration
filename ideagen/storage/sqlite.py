from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
import aiosqlite
from ideagen.core.models import RunResult, IdeaReport, TrendingItem
from ideagen.storage.base import StorageBackend
from ideagen.storage.schema import CREATE_TABLES, SCHEMA_VERSION

logger = logging.getLogger("ideagen")


class SQLiteStorage(StorageBackend):
    """SQLite-based storage backend using aiosqlite."""

    def __init__(self, db_path: str = "~/.ideagen/ideagen.db"):
        raw = str(db_path)
        self._is_memory = raw == ":memory:"
        self._db_path = Path(raw).expanduser() if not self._is_memory else Path(raw)
        self._initialized = False
        # Persistent connection held for :memory: databases so data is not lost
        # between method calls (each aiosqlite.connect(":memory:") creates a
        # separate, empty, in-process database).
        self._conn: aiosqlite.Connection | None = None

    async def _ensure_db(self) -> aiosqlite.Connection:
        """Create database and tables if they don't exist."""
        if self._is_memory:
            if self._conn is None:
                self._conn = await aiosqlite.connect(":memory:")
                self._conn.row_factory = aiosqlite.Row
            db = self._conn
        else:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            db = await aiosqlite.connect(str(self._db_path))
            db.row_factory = aiosqlite.Row

        if not self._initialized:
            # Enable WAL mode for concurrent read safety (file-backed DBs only)
            if not self._is_memory:
                await db.execute("PRAGMA journal_mode=WAL")
            await db.executescript(CREATE_TABLES)
            # Check/set schema version
            cursor = await db.execute("SELECT version FROM schema_version LIMIT 1")
            row = await cursor.fetchone()
            if row is None:
                await db.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            await db.commit()
            self._initialized = True

        return db

    async def _release_db(self, db: aiosqlite.Connection) -> None:
        """Close the connection unless it is the persistent :memory: connection."""
        if not self._is_memory:
            await db.close()

    async def close(self) -> None:
        """Close the persistent connection (only relevant for :memory: databases)."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            self._initialized = False

    async def save_run(self, result: RunResult) -> str:
        run_id = str(uuid.uuid4())
        db = await self._ensure_db()
        try:
            await db.execute(
                """INSERT INTO runs (id, timestamp, domain, config_snapshot, content_hash,
                   total_items_scraped, total_after_dedup, sources_used, ideas_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    result.timestamp.isoformat(),
                    result.domain.value,
                    json.dumps(result.config_snapshot),
                    result.content_hash,
                    result.total_items_scraped,
                    result.total_after_dedup,
                    json.dumps(result.sources_used),
                    len(result.ideas),
                ),
            )

            for report in result.ideas:
                idea_id = str(uuid.uuid4())
                await db.execute(
                    """INSERT INTO ideas (id, run_id, title, problem_statement, solution,
                       domain, novelty_score, content_hash, report_json, wtp_score, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        idea_id,
                        run_id,
                        report.idea.title,
                        report.idea.problem_statement,
                        report.idea.solution,
                        report.idea.domain.value,
                        report.idea.novelty_score,
                        report.idea.content_hash,
                        report.model_dump_json(),
                        report.wtp_score,
                        report.generated_at.isoformat(),
                    ),
                )

            await db.commit()
            return run_id
        finally:
            await self._release_db(db)

    async def get_runs(self, offset: int = 0, limit: int = 20, **filters: Any) -> list[dict]:
        db = await self._ensure_db()
        try:
            query = "SELECT * FROM runs ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            cursor = await db.execute(query, (limit, offset))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            await self._release_db(db)

    async def get_run_detail(self, run_id_prefix: str) -> dict | None:
        """Get full run details including ideas by ID prefix."""
        db = await self._ensure_db()
        try:
            cursor = await db.execute(
                "SELECT * FROM runs WHERE id LIKE ? ORDER BY timestamp DESC LIMIT 1",
                (f"{run_id_prefix}%",),
            )
            run_row = await cursor.fetchone()
            if run_row is None:
                return None

            run = dict(run_row)
            cursor = await db.execute(
                "SELECT report_json FROM ideas WHERE run_id = ? ORDER BY wtp_score DESC",
                (run["id"],),
            )
            idea_rows = await cursor.fetchall()
            run["ideas"] = [
                IdeaReport.model_validate_json(row[0]) for row in idea_rows
            ]
            return run
        finally:
            await self._release_db(db)

    async def get_idea(self, idea_id: str) -> IdeaReport | None:
        db = await self._ensure_db()
        try:
            cursor = await db.execute("SELECT report_json FROM ideas WHERE id = ?", (idea_id,))
            row = await cursor.fetchone()
            if row is None:
                return None
            return IdeaReport.model_validate_json(row[0])
        finally:
            await self._release_db(db)

    async def search_ideas(self, query: str, offset: int = 0, limit: int = 50) -> list[IdeaReport]:
        db = await self._ensure_db()
        try:
            cursor = await db.execute(
                """SELECT report_json FROM ideas
                   WHERE title LIKE ? OR problem_statement LIKE ? OR solution LIKE ?
                   ORDER BY wtp_score DESC
                   LIMIT ? OFFSET ?""",
                (f"%{query}%", f"%{query}%", f"%{query}%", limit, offset),
            )
            rows = await cursor.fetchall()
            return [IdeaReport.model_validate_json(row[0]) for row in rows]
        finally:
            await self._release_db(db)

    async def find_runs_by_content_hash(self, content_hash: str, exclude_id: str | None = None) -> list[dict]:
        """Find runs with the same content hash, optionally excluding one."""
        db = await self._ensure_db()
        try:
            if exclude_id:
                cursor = await db.execute(
                    "SELECT id, timestamp FROM runs WHERE content_hash = ? AND id != ? ORDER BY timestamp DESC LIMIT 5",
                    (content_hash, exclude_id),
                )
            else:
                cursor = await db.execute(
                    "SELECT id, timestamp FROM runs WHERE content_hash = ? ORDER BY timestamp DESC LIMIT 5",
                    (content_hash,),
                )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            await self._release_db(db)

    async def find_runs_by_prefix(self, prefix: str) -> list[dict]:
        """Find all runs matching an ID prefix, ordered by most recent first."""
        db = await self._ensure_db()
        try:
            cursor = await db.execute(
                "SELECT id, timestamp, domain FROM runs WHERE id LIKE ? ORDER BY timestamp DESC",
                (f"{prefix}%",),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            await self._release_db(db)

    async def get_runs_count(self, **filters: Any) -> int:
        """Return the total number of runs."""
        db = await self._ensure_db()
        try:
            cursor = await db.execute("SELECT COUNT(*) FROM runs")
            row = await cursor.fetchone()
            return row[0]
        finally:
            await self._release_db(db)

    async def save_scrape_cache(self, batch_id: str, source: str, items: list[TrendingItem]) -> None:
        """Save scraped items to cache for later reuse."""
        db = await self._ensure_db()
        try:
            items_json = json.dumps([item.model_dump(mode="json") for item in items])
            await db.execute(
                "INSERT INTO scrape_cache (id, run_id, source, items_json, scraped_at) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), batch_id, source, items_json, datetime.now().isoformat()),
            )
            await db.commit()
        finally:
            await self._release_db(db)

    async def load_latest_scrape_cache(self, source_names: list[str] | None = None) -> list[TrendingItem]:
        """Load the most recent batch of cached scraped items.

        If ``source_names`` is provided, the batch must contain ALL of the
        requested sources (case-insensitive).  If any source is missing the
        method logs a warning and returns an empty list.  Pass ``None`` to
        preserve the original behaviour (return every item in the latest batch).
        """
        db = await self._ensure_db()
        try:
            cursor = await db.execute(
                "SELECT run_id FROM scrape_cache ORDER BY scraped_at DESC LIMIT 1"
            )
            row = await cursor.fetchone()
            if row is None:
                return []

            batch_id = row[0]

            if source_names is not None:
                # Normalise requested names to lower-case for comparison.
                requested = {s.lower() for s in source_names}

                # Find which sources are actually present in this batch.
                cursor = await db.execute(
                    "SELECT DISTINCT LOWER(source) FROM scrape_cache WHERE run_id = ?",
                    (batch_id,),
                )
                present_rows = await cursor.fetchall()
                present = {r[0] for r in present_rows}

                missing = requested - present
                if missing:
                    logger.warning(
                        "Cached batch %s is missing sources %s; "
                        "ignoring cache to avoid source mismatch.",
                        batch_id,
                        sorted(missing),
                    )
                    return []

                # All requested sources are present — fetch only those rows.
                placeholders = ",".join("?" * len(requested))
                cursor = await db.execute(
                    f"SELECT items_json FROM scrape_cache WHERE run_id = ? AND LOWER(source) IN ({placeholders})",
                    (batch_id, *sorted(requested)),
                )
            else:
                cursor = await db.execute(
                    "SELECT items_json FROM scrape_cache WHERE run_id = ?",
                    (batch_id,),
                )

            rows = await cursor.fetchall()
            items = []
            for row in rows:
                raw_items = json.loads(row[0])
                for raw in raw_items:
                    items.append(TrendingItem.model_validate(raw))
            return items
        finally:
            await self._release_db(db)

    async def delete_runs_older_than(self, days: int) -> int:
        """Delete runs older than N days. Returns count of deleted runs."""
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        db = await self._ensure_db()
        try:
            # Delete ideas first (foreign key)
            await db.execute(
                "DELETE FROM ideas WHERE run_id IN (SELECT id FROM runs WHERE timestamp < ?)",
                (cutoff,),
            )
            cursor = await db.execute("DELETE FROM runs WHERE timestamp < ?", (cutoff,))
            count = cursor.rowcount
            await db.commit()
            return count
        finally:
            await self._release_db(db)
