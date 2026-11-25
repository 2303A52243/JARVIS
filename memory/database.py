"""Persistent memory system for JARVIS using SQLite.

Stores:
- Conversation history
- User preferences
- Notes / bookmarks
- Recent tasks
"""

from __future__ import annotations

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


def _db_path() -> Path:
    from app.config import get_settings
    return get_settings().jarvis_data_dir / "jarvis_memory.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create all required tables if they don't exist yet."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                role        TEXT    NOT NULL,          -- 'user' | 'assistant' | 'system'
                content     TEXT    NOT NULL,
                language    TEXT    DEFAULT 'en',
                created_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                body        TEXT    NOT NULL,
                tags        TEXT    DEFAULT '',        -- comma-separated
                created_at  TEXT    NOT NULL,
                updated_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS preferences (
                key         TEXT    PRIMARY KEY,
                value       TEXT    NOT NULL,
                updated_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT    NOT NULL,
                status      TEXT    DEFAULT 'pending', -- pending | done | failed
                result      TEXT    DEFAULT '',
                created_at  TEXT    NOT NULL,
                updated_at  TEXT    NOT NULL
            );
        """)


# ── Conversations ────────────────────────────────────────────────────────────

def save_message(role: str, content: str, language: str = "en") -> int:
    """Save a conversation message; returns the new row id."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO conversations (role, content, language, created_at) VALUES (?,?,?,?)",
            (role, content, language, now),
        )
        return cur.lastrowid


def get_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Return the most recent *limit* messages, oldest first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM conversations ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def clear_history() -> int:
    """Delete all conversation history; returns number of rows deleted."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM conversations")
        return cur.rowcount


# ── Notes ────────────────────────────────────────────────────────────────────

def add_note(title: str, body: str, tags: str = "") -> int:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO notes (title, body, tags, created_at, updated_at) VALUES (?,?,?,?,?)",
            (title, body, tags, now, now),
        )
        return cur.lastrowid


def search_notes(query: str) -> List[Dict[str, Any]]:
    q = f"%{query}%"
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM notes WHERE title LIKE ? OR body LIKE ? OR tags LIKE ? ORDER BY updated_at DESC",
            (q, q, q),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_note(note_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
        return cur.rowcount > 0


def get_all_notes() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM notes ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]


# ── Preferences ──────────────────────────────────────────────────────────────

def set_preference(key: str, value: Any) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO preferences (key, value, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, json.dumps(value), now),
        )


def get_preference(key: str, default: Any = None) -> Any:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
    if row is None:
        return default
    return json.loads(row["value"])


def get_all_preferences() -> Dict[str, Any]:
    with get_connection() as conn:
        rows = conn.execute("SELECT key, value FROM preferences").fetchall()
    return {r["key"]: json.loads(r["value"]) for r in rows}


# ── Tasks ────────────────────────────────────────────────────────────────────

def log_task(description: str) -> int:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (description, status, created_at, updated_at) VALUES (?,?,?,?)",
            (description, "pending", now, now),
        )
        return cur.lastrowid


def update_task(task_id: int, status: str, result: str = "") -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE tasks SET status=?, result=?, updated_at=? WHERE id=?",
            (status, result, now, task_id),
        )


def get_recent_tasks(limit: int = 20) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# Initialise tables as soon as the module is imported
init_db()
