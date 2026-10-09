"""
reconmind.db.init_db
====================
Initialize (or reset) the SQLite database from schema.sql.

Usage (from repo root):
    python -m reconmind.db.init_db          # create DB if missing, no-op if already correct
    python -m reconmind.db.init_db --reset  # DROP all tables then re-create (destructive!)

Imported API:
    from reconmind.db.init_db import init_db
    init_db()           # safe default
    init_db(reset=True) # destructive reset

Design rules:
  - Idempotent by default: "CREATE TABLE IF NOT EXISTS" means re-running never errors.
  - Column additions are handled by _migrate_schema() — ALTER TABLE per new column,
    guarded by a check against PRAGMA table_info so it is always safe to re-run.
  - --reset explicitly drops tables (opt-in only, not the default).
  - foreign_keys pragma set at every connection open (SQLite resets it per session).
  - DB directory created automatically (avoids "no such file" on clean clone).
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

from reconmind.config import cfg

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# ---------------------------------------------------------------------------
# Column migrations: list of (table, column_name, ALTER TABLE sql).
# Add a new tuple here whenever schema.sql gains a new column that may not
# exist in an already-initialised dev DB.  The migration is safe to re-run.
# ---------------------------------------------------------------------------
_COLUMN_MIGRATIONS: list[tuple[str, str, str]] = [
    ("events", "temperature",   "ALTER TABLE events ADD COLUMN temperature REAL"),
    ("events", "input_tokens",  "ALTER TABLE events ADD COLUMN input_tokens INTEGER"),
    ("events", "output_tokens", "ALTER TABLE events ADD COLUMN output_tokens INTEGER"),
    ("events", "defense_confidence_score", "ALTER TABLE events ADD COLUMN defense_confidence_score REAL"),
    ("runs", "attack_objective", "ALTER TABLE runs ADD COLUMN attack_objective TEXT"),
    ("runs", "attack_strength", "ALTER TABLE runs ADD COLUMN attack_strength TEXT"),
    ("runs", "expected_signal", "ALTER TABLE runs ADD COLUMN expected_signal TEXT"),
    ("runs", "injection_outcome", "ALTER TABLE runs ADD COLUMN injection_outcome TEXT"),
    ("runs", "judge_confidence", "ALTER TABLE runs ADD COLUMN judge_confidence REAL"),
    ("runs", "session_id", "ALTER TABLE runs ADD COLUMN session_id TEXT"),
    ("runs", "repeat_index", "ALTER TABLE runs ADD COLUMN repeat_index INTEGER"),
]


def _get_connection(db_path: Path) -> sqlite3.Connection:
    """Open a connection with FK enforcement and WAL journal mode."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def _drop_all_tables(conn: sqlite3.Connection) -> None:
    """
    Drop all user-created tables in FK-safe order (child tables first).

    Note: SQLite automatically drops indexes when their table is dropped,
    so no explicit DROP INDEX statements are needed here.
    Extend this list when new tables are added in later milestones.
    """
    tables_in_drop_order = ["events", "session_memory", "runs"]
    for table in tables_in_drop_order:
        conn.execute(f"DROP TABLE IF EXISTS {table};")
        logger.info("Dropped table '%s' (reset mode).", table)
    conn.commit()


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """
    Apply column-level schema migrations that cannot be expressed as
    CREATE TABLE IF NOT EXISTS (i.e. new columns added to existing tables).

    Each migration is guarded: if the column already exists, the ALTER TABLE
    is skipped. This makes the function fully idempotent.

    Args:
        conn: Open SQLite connection (with FK enabled).
    """
    for table, column, sql in _COLUMN_MIGRATIONS:
        rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
        existing_cols = {row[1] for row in rows}
        if column not in existing_cols:
            conn.execute(sql)
            logger.info("Migration: added column '%s' to table '%s'.", column, table)
        else:
            logger.debug("Migration skip: '%s.%s' already exists.", table, column)
    conn.commit()


def init_db(
    db_path: Path | None = None,
    schema_path: Path | None = None,
    reset: bool = False,
) -> Path:
    """
    Create (or optionally reset) the SQLite database.

    Args:
        db_path:     Override DB path (defaults to cfg.database.resolved_path).
        schema_path: Override schema.sql path (useful for tests).
        reset:       If True, DROP all tables before re-creating. DESTRUCTIVE.

    Returns:
        The absolute Path to the DB file that was initialized.

    Raises:
        FileNotFoundError: if schema.sql is missing.
        sqlite3.Error:     on any DB-level failure.
    """
    resolved_db = db_path or cfg.database.resolved_path
    resolved_schema = schema_path or _SCHEMA_PATH

    if not resolved_schema.exists():
        raise FileNotFoundError(
            f"schema.sql not found at '{resolved_schema}'. "
            "Ensure the package is installed from source."
        )

    resolved_db.parent.mkdir(parents=True, exist_ok=True)
    logger.info("DB path: %s", resolved_db)

    schema_sql = resolved_schema.read_text(encoding="utf-8")

    with _get_connection(resolved_db) as conn:
        if reset:
            logger.warning("--reset flag active: dropping all tables.")
            _drop_all_tables(conn)

        conn.executescript(schema_sql)
        logger.info("Schema applied from '%s'.", resolved_schema)

        _migrate_schema(conn)

    logger.info("DB initialised at '%s'.", resolved_db)
    return resolved_db


def _main() -> None:
    logging.basicConfig(level=cfg.logging.level, format=cfg.logging.format)

    parser = argparse.ArgumentParser(
        description="Initialize the reconmind SQLite database from schema.sql."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="DROP all existing tables before re-creating (DESTRUCTIVE — data loss!).",
    )
    args = parser.parse_args()

    db_path = init_db(reset=args.reset)
    print(f"✓ DB ready at: {db_path}")


if __name__ == "__main__":
    _main()
