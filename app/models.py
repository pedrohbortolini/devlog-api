"""Database layer for DevLog.

Deliberately simple: raw SQLite from the standard library.
Decision: single user, no concurrency needs -> no ORM, no external DB.
The DB path comes from the DEVLOG_DB env var so tests can use a temp file.
"""

import os
import sqlite3
from datetime import date, datetime, timedelta
from contextlib import contextmanager


SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,          -- ISO date-time of creation
    day TEXT NOT NULL,                 -- ISO date (YYYY-MM-DD), for grouping
    type TEXT NOT NULL,                -- study | work | project
    what TEXT NOT NULL,                -- free-text description
    tags TEXT NOT NULL DEFAULT '',     -- comma-separated, e.g. "docker,python"
    minutes INTEGER NOT NULL DEFAULT 0
);
"""


def db_path() -> str:
    return os.environ.get("DEVLOG_DB", "devlog.db")


@contextmanager
def get_conn():
    """Yields a connection, commits on success and ALWAYS closes it.

    Why: sqlite3's `with conn:` only commits — it does not close the file
    handle. On Linux a leaked handle goes unnoticed; on Windows it locks
    the file and breaks the test teardown. Closing explicitly is correct
    on both.
    """
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_entry(type_: str, what: str, tags: list[str], minutes: int) -> dict:
    now = datetime.now()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO entries (created_at, day, type, what, tags, minutes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                now.isoformat(timespec="seconds"),
                now.date().isoformat(),
                type_,
                what,
                ",".join(t.strip().lower() for t in tags if t.strip()),
                minutes,
            ),
        )
        return get_entry(conn, cur.lastrowid)


def get_entry(conn: sqlite3.Connection, entry_id: int) -> dict:
    row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    return _row_to_dict(row)


def list_entries(tag: str | None = None, days: int | None = None) -> list[dict]:
    query = "SELECT * FROM entries WHERE 1=1"
    params: list = []
    if tag:
        # tags is a comma-separated string; match whole tag, not substring
        query += " AND (',' || tags || ',') LIKE ?"
        params.append(f"%,{tag.strip().lower()},%")
    if days:
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        query += " AND day >= ?"
        params.append(cutoff)
    query += " ORDER BY created_at DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]


def stats() -> dict:
    """Current streak, minutes in the last 7 days, and top tags overall."""
    with get_conn() as conn:
        days_with_entries = {
            r["day"] for r in conn.execute("SELECT DISTINCT day FROM entries")
        }
        week_cutoff = (date.today() - timedelta(days=7)).isoformat()
        week_minutes = conn.execute(
            "SELECT COALESCE(SUM(minutes), 0) AS m FROM entries WHERE day >= ?",
            (week_cutoff,),
        ).fetchone()["m"]
        total_entries = conn.execute(
            "SELECT COUNT(*) AS c FROM entries"
        ).fetchone()["c"]
        all_rows = conn.execute("SELECT tags, minutes FROM entries").fetchall()

    return {
        "streak_days": _streak(days_with_entries),
        "minutes_last_7_days": week_minutes,
        "total_entries": total_entries,
        "top_tags": _top_tags(all_rows, limit=5),
    }


def weekly() -> dict:
    """Summary of the last 7 days: per-tag minutes and share (raw material for posts)."""
    cutoff = (date.today() - timedelta(days=7)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT tags, minutes, day, type, what FROM entries WHERE day >= ?",
            (cutoff,),
        ).fetchall()

    tag_minutes = _tag_minutes(rows)
    total = sum(tag_minutes.values()) or 1  # avoid division by zero
    breakdown = [
        {"tag": t, "minutes": m, "percent": round(100 * m / total)}
        for t, m in sorted(tag_minutes.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return {
        "since": cutoff,
        "entries": len(rows),
        "total_minutes": sum(r["minutes"] for r in rows),
        "by_tag": breakdown,
        "highlights": [f"[{r['type']}] {r['what']}" for r in rows[:10]],
    }


# ---------- helpers ----------

def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["tags"] = [t for t in d["tags"].split(",") if t]
    return d


def _streak(days_with_entries: set[str]) -> int:
    """Consecutive days with at least one entry, counting back from today
    (or from yesterday, so the streak isn't broken before you log today)."""
    day = date.today()
    if day.isoformat() not in days_with_entries:
        day = day - timedelta(days=1)
    streak = 0
    while day.isoformat() in days_with_entries:
        streak += 1
        day = day - timedelta(days=1)
    return streak


def _tag_minutes(rows) -> dict[str, int]:
    result: dict[str, int] = {}
    for r in rows:
        tags = [t for t in r["tags"].split(",") if t]
        for t in tags:
            result[t] = result.get(t, 0) + r["minutes"]
    return result


def _top_tags(rows, limit: int) -> list[dict]:
    tag_minutes = _tag_minutes(rows)
    ordered = sorted(tag_minutes.items(), key=lambda kv: kv[1], reverse=True)
    return [{"tag": t, "minutes": m} for t, m in ordered[:limit]]
