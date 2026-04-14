"""
Repository layer — all SQLite reads and writes go through this module.

No raw SQL should exist outside of this file (except schema.sql / database.py).
All writes are serialized to prevent WAL contention under concurrent async tasks.
"""

import threading
import time
from typing import Optional

from db.database import get_connection

# Serialize all writes through a single lock
_write_lock = threading.Lock()


# ─── FTS Content ────────────────────────────────────────────────────

def upsert_fts(path: str, vault: str, title: str, body: str) -> None:
    """Insert or update a document in the FTS index."""
    with _write_lock:
        conn = get_connection()
        conn.execute(
            """INSERT INTO fts_content (path, vault, title, body, modified_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(path) DO UPDATE SET
                 vault=excluded.vault,
                 title=excluded.title,
                 body=excluded.body,
                 modified_at=excluded.modified_at""",
            (path, vault, title, body, int(time.time())),
        )
        conn.commit()


def delete_fts(path: str) -> None:
    """Remove a document from the FTS index."""
    with _write_lock:
        conn = get_connection()
        conn.execute("DELETE FROM fts_content WHERE path = ?", (path,))
        conn.commit()


def search_fts(query: str, vault: Optional[str] = None, limit: int = 20):
    """
    Full-text search across indexed documents.

    Returns list of dicts: {path, vault, title, snippet, score}
    """
    conn = get_connection()
    vault_clause = "AND fc.vault = ?" if vault and vault != "all" else ""
    params = [query]
    if vault and vault != "all":
        params.append(vault)
    params.append(limit)

    rows = conn.execute(
        f"""SELECT fc.path, fc.vault, fc.title,
                   snippet(fts_index, 1, '<mark>', '</mark>', '...', 32) as snippet,
                   rank as score
            FROM fts_index fi
            JOIN fts_content fc ON fi.rowid = fc.id
            WHERE fts_index MATCH ?
            {vault_clause}
            ORDER BY rank
            LIMIT ?""",
        params,
    ).fetchall()

    return [dict(row) for row in rows]


# ─── Proposals ──────────────────────────────────────────────────────

def create_proposal(batch_id: str, batch_path: str, summary: str) -> None:
    """Create a new proposal batch."""
    with _write_lock:
        conn = get_connection()
        now = int(time.time())
        conn.execute(
            """INSERT INTO proposals (batch_id, batch_path, summary, status, created_at, updated_at)
               VALUES (?, ?, ?, 'pending', ?, ?)""",
            (batch_id, batch_path, summary, now, now),
        )
        conn.commit()


def add_proposal_article(batch_id: str, filename: str, title: str, action: str = "create") -> None:
    """Add an article to a proposal batch."""
    with _write_lock:
        conn = get_connection()
        conn.execute(
            "INSERT INTO proposal_articles (batch_id, filename, title, action) VALUES (?, ?, ?, ?)",
            (batch_id, filename, title, action),
        )
        conn.commit()


def get_pending_proposals():
    """Get all pending proposal batches with their articles."""
    conn = get_connection()
    batches = conn.execute(
        "SELECT * FROM proposals WHERE status = 'pending' ORDER BY created_at"
    ).fetchall()

    result = []
    for batch in batches:
        articles = conn.execute(
            "SELECT * FROM proposal_articles WHERE batch_id = ?",
            (batch["batch_id"],),
        ).fetchall()
        result.append({
            **dict(batch),
            "articles": [dict(a) for a in articles],
        })
    return result


def count_pending_proposals() -> int:
    """Count pending proposal batches."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM proposals WHERE status = 'pending'"
    ).fetchone()
    return row["cnt"]


def update_proposal_status(batch_id: str, status: str) -> None:
    """Update a proposal batch status (pending -> approved|rejected)."""
    with _write_lock:
        conn = get_connection()
        conn.execute(
            "UPDATE proposals SET status = ?, updated_at = ? WHERE batch_id = ?",
            (status, int(time.time()), batch_id),
        )
        conn.commit()


def update_article_status(batch_id: str, filename: str, status: str) -> None:
    """Update an individual article status within a batch."""
    with _write_lock:
        conn = get_connection()
        conn.execute(
            "UPDATE proposal_articles SET status = ? WHERE batch_id = ? AND filename = ?",
            (status, batch_id, filename),
        )
        conn.commit()


# ─── Agent Runs ─────────────────────────────────────────────────────

def create_agent_run(run_id: str, trigger_path: Optional[str] = None) -> None:
    """Record the start of an agent run."""
    with _write_lock:
        conn = get_connection()
        conn.execute(
            """INSERT INTO agent_runs (run_id, trigger_path, status, started_at)
               VALUES (?, ?, 'running', ?)""",
            (run_id, trigger_path, int(time.time())),
        )
        conn.commit()


def complete_agent_run(run_id: str, status: str = "complete",
                       error_msg: Optional[str] = None, tokens_used: int = 0) -> None:
    """Mark an agent run as complete or errored."""
    with _write_lock:
        conn = get_connection()
        conn.execute(
            """UPDATE agent_runs
               SET status = ?, completed_at = ?, error_msg = ?, tokens_used = ?
               WHERE run_id = ?""",
            (status, int(time.time()), error_msg, tokens_used, run_id),
        )
        conn.commit()


def get_last_run():
    """Get the most recent agent run."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def get_runs(limit: int = 20, offset: int = 0):
    """Get paginated agent run history."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [dict(row) for row in rows]


# ─── Stale Articles ────────────────────────────────────────────────

def flag_stale_article(article_path: str, source_path: str) -> None:
    """Flag a wiki article as stale due to a source change."""
    with _write_lock:
        conn = get_connection()
        conn.execute(
            "INSERT INTO stale_articles (article_path, source_path, flagged_at) VALUES (?, ?, ?)",
            (article_path, source_path, int(time.time())),
        )
        conn.commit()


def get_stale_articles():
    """Get all currently stale articles."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM stale_articles").fetchall()
    return [dict(row) for row in rows]


def clear_stale_article(article_path: str) -> None:
    """Remove stale flag for an article (after it's been re-evaluated)."""
    with _write_lock:
        conn = get_connection()
        conn.execute(
            "DELETE FROM stale_articles WHERE article_path = ?",
            (article_path,),
        )
        conn.commit()


# ─── Sync Writes ────────────────────────────────────────────────────

def record_sync_write(path: str) -> None:
    """Record that a file was written by sync (to prevent double-trigger)."""
    with _write_lock:
        conn = get_connection()
        conn.execute(
            "INSERT INTO sync_writes (path, sync_timestamp) VALUES (?, ?)",
            (path, int(time.time())),
        )
        conn.commit()


def is_recent_sync_write(path: str, within_seconds: int = 30) -> bool:
    """Check if a path was recently written by sync."""
    conn = get_connection()
    cutoff = int(time.time()) - within_seconds
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM sync_writes WHERE path = ? AND sync_timestamp > ?",
        (path, cutoff),
    ).fetchone()
    return row["cnt"] > 0


def cleanup_old_sync_writes(older_than_seconds: int = 60) -> None:
    """Remove old sync write records."""
    with _write_lock:
        conn = get_connection()
        cutoff = int(time.time()) - older_than_seconds
        conn.execute("DELETE FROM sync_writes WHERE sync_timestamp < ?", (cutoff,))
        conn.commit()
