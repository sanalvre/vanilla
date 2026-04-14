"""
SQLite database initialization and connection management.

The Python sidecar is the sole owner of the SQLite database.
WAL mode is enabled for concurrent read access from async tasks.
All writes are serialized through the repository layer.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from config import VanillaConfig

# Module-level connection (reused across requests)
_connection: Optional[sqlite3.Connection] = None


SCHEMA_SQL = """
-- Full-text search content table
CREATE TABLE IF NOT EXISTS fts_content (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    vault TEXT NOT NULL,
    title TEXT,
    body TEXT,
    modified_at INTEGER
);

-- FTS5 virtual table for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS fts_index USING fts5(
    title, body,
    content='fts_content', content_rowid='id'
);

-- FTS5 triggers to keep index in sync with content table
CREATE TRIGGER IF NOT EXISTS fts_content_ai AFTER INSERT ON fts_content BEGIN
    INSERT INTO fts_index(rowid, title, body) VALUES (new.id, new.title, new.body);
END;
CREATE TRIGGER IF NOT EXISTS fts_content_ad AFTER DELETE ON fts_content BEGIN
    INSERT INTO fts_index(fts_index, rowid, title, body) VALUES ('delete', old.id, old.title, old.body);
END;
CREATE TRIGGER IF NOT EXISTS fts_content_au AFTER UPDATE ON fts_content BEGIN
    INSERT INTO fts_index(fts_index, rowid, title, body) VALUES ('delete', old.id, old.title, old.body);
    INSERT INTO fts_index(rowid, title, body) VALUES (new.id, new.title, new.body);
END;

-- Proposal batches
CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY,
    batch_id TEXT NOT NULL UNIQUE,
    batch_path TEXT NOT NULL,
    summary TEXT,
    status TEXT DEFAULT 'pending',
    created_at INTEGER,
    updated_at INTEGER
);

-- Individual articles within a batch
CREATE TABLE IF NOT EXISTS proposal_articles (
    id INTEGER PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES proposals(batch_id),
    filename TEXT NOT NULL,
    title TEXT,
    action TEXT DEFAULT 'create',
    status TEXT DEFAULT 'pending'
);

-- Agent run history
CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,
    trigger_path TEXT,
    status TEXT,
    started_at INTEGER,
    completed_at INTEGER,
    error_msg TEXT,
    tokens_used INTEGER DEFAULT 0
);

-- Stale article tracking
CREATE TABLE IF NOT EXISTS stale_articles (
    id INTEGER PRIMARY KEY,
    article_path TEXT NOT NULL,
    source_path TEXT NOT NULL,
    flagged_at INTEGER
);

-- Sync write tracking (for Supabase double-trigger prevention)
CREATE TABLE IF NOT EXISTS sync_writes (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL,
    sync_timestamp INTEGER NOT NULL
);
"""


def get_db_path(config: VanillaConfig) -> Path:
    """Get the SQLite database file path from config."""
    return config.db_path


def init_db(db_path: Path) -> sqlite3.Connection:
    """
    Initialize the SQLite database with WAL mode and create all tables.

    Returns the connection for reuse.
    """
    global _connection

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Enable WAL mode for concurrent reads
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Create schema
    conn.executescript(SCHEMA_SQL)
    conn.commit()

    _connection = conn
    return conn


def get_connection() -> sqlite3.Connection:
    """Get the active database connection. Raises if not initialized."""
    if _connection is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _connection
