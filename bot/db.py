"""The SQLite layer.

Holds users and their cigarettes. A record can carry a photo, stored on disk
with only its path kept here.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
from typing import Iterator, Optional

DB_PATH = os.environ.get("DB_PATH", "/data/cigarettes.db")


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    # WAL lets a chart read while a tap is being written; without it a slow
    # chart could hold the writer off long enough to raise "database is locked".
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create the tables if they are missing, and run the small migrations."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id       INTEGER PRIMARY KEY,
                username      TEXT,
                first_name    TEXT,
                display_name  TEXT,
                created_at    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                count       INTEGER NOT NULL,
                created_at  TEXT NOT NULL,
                photo_path  TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_sets_user ON sets(user_id, created_at);

            -- Consumables: a pack of tobacco, paper, filters or cigarettes.
            -- You "open" a unit and record its price, then "close" it when it
            -- runs out. closed_at = NULL means it is still in use.
            CREATE TABLE IF NOT EXISTS consumables (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                kind        TEXT NOT NULL,
                price       REAL NOT NULL,
                currency    TEXT,
                opened_at   TEXT NOT NULL,
                closed_at   TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_cons_user ON consumables(user_id, opened_at);
            """
        )
        # Migrations for databases created before these columns existed
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
        for col, ddl in [
            ("display_name", "TEXT"),
            ("currency", "TEXT"),
            ("price_per_pack", "REAL"),
            ("pack_size", "INTEGER"),
        ]:
            if col not in cols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
        # Interface language. New users get English (see upsert_user); everyone
        # who already existed when this column landed was speaking Russian, so
        # switching them would have been a rude surprise.
        if "language" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN language TEXT")
            conn.execute("UPDATE users SET language = 'ru' WHERE language IS NULL")


def user_exists(user_id: int) -> bool:
    with _connect() as conn:
        return conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
        ).fetchone() is not None


def upsert_user(user_id: int, username: Optional[str], first_name: Optional[str]) -> None:
    """Make sure the user exists.

    display_name is taken from Telegram on first sight and never overwritten
    afterwards - only set_display_name touches it. Otherwise renaming yourself
    in Telegram would silently rename you on the leaderboard."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, username, first_name, display_name, created_at,
                               language, currency)
            VALUES (?, ?, ?, ?, ?, 'en', '€')
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
            """,
            (user_id, username, first_name, first_name,
             datetime.now().isoformat(timespec="seconds")),
        )


def get_language(user_id: int) -> str:
    """The user's interface language, English by default."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT language FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return (row["language"] if row and row["language"] else "en")


def set_language(user_id: int, language: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET language = ? WHERE user_id = ?", (language, user_id)
        )


def set_display_name(user_id: int, name: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE users SET display_name = ? WHERE user_id = ?", (name, user_id))


def get_display_name(user_id: int) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(display_name, first_name, username) AS name "
            "FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row["name"] if row else None


def add_set(user_id: int, count: int) -> int:
    """Log a smoke break and return its id."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO sets (user_id, count, created_at) VALUES (?, ?, ?)",
            (user_id, count, datetime.now().isoformat(timespec="seconds")),
        )
        return int(cur.lastrowid)


def attach_photo(set_id: int, photo_path: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE sets SET photo_path = ? WHERE id = ?", (photo_path, set_id))


def last_set_id(user_id: int) -> Optional[int]:
    """Id of the user's last break, so a photo can be attached to it."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM sets WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        return int(row["id"]) if row else None


def total_count(user_id: int) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(count), 0) AS total FROM sets WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return int(row["total"])


def today_count(user_id: int) -> int:
    today = date.today().isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(count), 0) AS total FROM sets "
            "WHERE user_id = ? AND substr(created_at, 1, 10) = ?",
            (user_id, today),
        ).fetchone()
        return int(row["total"])


def sets_count(user_id: int) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM sets WHERE user_id = ?", (user_id,)
        ).fetchone()
        return int(row["c"])


def per_day(user_id: int) -> list[tuple[str, int]]:
    """Cigarettes per day: [(YYYY-MM-DD, count), ...], oldest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT substr(created_at, 1, 10) AS day, SUM(count) AS total "
            "FROM sets WHERE user_id = ? GROUP BY day ORDER BY day",
            (user_id,),
        ).fetchall()
        return [(r["day"], int(r["total"])) for r in rows]


def sessions(user_id: int) -> list[tuple[str, int]]:
    """Every break in order: [(timestamp, count), ...]."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT created_at, count FROM sets WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
        return [(r["created_at"], int(r["count"])) for r in rows]


def by_hour(user_id: int) -> list[int]:
    """Cigarettes by hour of day: 24 numbers, index is the hour."""
    out = [0] * 24
    with _connect() as conn:
        rows = conn.execute(
            "SELECT CAST(substr(created_at, 12, 2) AS INTEGER) AS h, "
            "SUM(count) AS total FROM sets WHERE user_id = ? GROUP BY h",
            (user_id,),
        ).fetchall()
    for r in rows:
        h = r["h"]
        if h is not None and 0 <= h < 24:
            out[h] = int(r["total"])
    return out


def by_weekday(user_id: int) -> list[int]:
    """Cigarettes by weekday: 7 numbers, index 0 = Monday ... 6 = Sunday."""
    out = [0] * 7
    with _connect() as conn:
        # strftime('%w') gives 0 = Sunday ... 6 = Saturday
        rows = conn.execute(
            "SELECT CAST(strftime('%w', created_at) AS INTEGER) AS w, "
            "SUM(count) AS total FROM sets WHERE user_id = ? GROUP BY w",
            (user_id,),
        ).fetchall()
    for r in rows:
        w = r["w"]
        if w is not None:
            idx = (w - 1) % 7  # shift it so that 0 = Monday ... 6 = Sunday
            out[idx] = int(r["total"])
    return out


def leaderboard() -> list[tuple[str, int]]:
    """All users ranked: [(name, total), ...], most first."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT u.user_id,
                   COALESCE(u.display_name, u.first_name, u.username, 'Аноним') AS name,
                   COALESCE(SUM(s.count), 0) AS total
            FROM users u
            LEFT JOIN sets s ON s.user_id = u.user_id
            GROUP BY u.user_id
            HAVING total > 0
            ORDER BY total DESC
            """
        ).fetchall()
        return [(r["name"], int(r["total"])) for r in rows]


def recent_sets(user_id: int, limit: int = 10) -> list[tuple[int, str, int]]:
    """The user's recent breaks: [(id, timestamp, count), ...], newest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, count FROM sets "
            "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [(int(r["id"]), r["created_at"], int(r["count"])) for r in rows]


def set_owner(set_id: int) -> Optional[int]:
    """Who owns this break, or None if there is no such break."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT user_id FROM sets WHERE id = ?", (set_id,)
        ).fetchone()
        return int(row["user_id"]) if row else None


def edit_set(set_id: int, count: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE sets SET count = ? WHERE id = ?", (count, set_id))


def set_created_at(set_id: int) -> Optional[str]:
    """When the break happened, as an ISO string, or None if it is gone."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT created_at FROM sets WHERE id = ?", (set_id,)
        ).fetchone()
        return row["created_at"] if row else None


def edit_set_time(set_id: int, created_at: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE sets SET created_at = ? WHERE id = ?", (created_at, set_id)
        )


def delete_set(set_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sets WHERE id = ?", (set_id,))


# -- Per-user settings: currency, price and pack size --------------
def get_settings(user_id: int) -> dict:
    """Pricing settings. price_per_pack of None means "never set"."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT currency, price_per_pack, pack_size FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return {"currency": "грн", "price_per_pack": None, "pack_size": 20}
    return {
        "currency": row["currency"] or "грн",
        "price_per_pack": row["price_per_pack"],
        "pack_size": row["pack_size"] or 20,
    }


def set_currency(user_id: int, currency: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE users SET currency = ? WHERE user_id = ?", (currency, user_id))


def set_settings(user_id: int, currency: str, price_per_pack: float, pack_size: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET currency = ?, price_per_pack = ?, pack_size = ? WHERE user_id = ?",
            (currency, price_per_pack, pack_size, user_id),
        )


# -- Weekly totals and the "fewer is better" ranking ----------------
def range_total(user_id: int, start: str, end: str) -> int:
    """Cigarettes over [start, end), dates as YYYY-MM-DD."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(count), 0) AS t FROM sets "
            "WHERE user_id = ? AND created_at >= ? AND created_at < ?",
            (user_id, start, end),
        ).fetchone()
        return int(row["t"])


# -- Consumables: tobacco, paper, filters, ready-made packs ---------
def open_consumable(user_id: int, kind: str, price: float, currency: str) -> int:
    """Open a new unit.

    If one of the same kind was still open it gets closed automatically -
    opening a second pouch of tobacco means the first one ran out."""
    now = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            "UPDATE consumables SET closed_at = ? "
            "WHERE user_id = ? AND kind = ? AND closed_at IS NULL",
            (now, user_id, kind),
        )
        cur = conn.execute(
            "INSERT INTO consumables (user_id, kind, price, currency, opened_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, kind, price, currency, now),
        )
        return int(cur.lastrowid)


def close_consumable(user_id: int, kind: str) -> bool:
    """Mark the open unit of this kind as finished.

    Returns True if there was anything to close."""
    now = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE consumables SET closed_at = ? "
            "WHERE user_id = ? AND kind = ? AND closed_at IS NULL",
            (now, user_id, kind),
        )
        return cur.rowcount > 0


def open_consumables(user_id: int) -> list[tuple[str, float, str, str]]:
    """Units currently in use: [(kind, price, currency, opened_at), ...]."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT kind, price, currency, opened_at FROM consumables "
            "WHERE user_id = ? AND closed_at IS NULL ORDER BY kind",
            (user_id,),
        ).fetchall()
        return [(r["kind"], float(r["price"]), r["currency"], r["opened_at"]) for r in rows]


def all_consumables(user_id: int) -> list[tuple[str, float, str]]:
    """Everything ever bought: [(kind, price, currency), ...].

    The currency is stored per purchase, not per user, so a pouch bought in
    Kyiv still reads as hryvnia after you move and switch to crowns."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT kind, price, currency FROM consumables WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return [(r["kind"], float(r["price"]), r["currency"]) for r in rows]


def leaderboard_week(start: str, end: str) -> list[tuple[str, int]]:
    """Ranking over [start, end): [(name, cigarettes), ...] ASCENDING.

    Fewer is higher - that is the whole point of the board. Only users who
    have logged something at all take part."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT u.user_id,
                   COALESCE(u.display_name, u.first_name, u.username, 'Аноним') AS name,
                   COALESCE(SUM(CASE WHEN s.created_at >= ? AND s.created_at < ?
                                     THEN s.count END), 0) AS week,
                   COUNT(s.id) AS ever
            FROM users u
            LEFT JOIN sets s ON s.user_id = u.user_id
            GROUP BY u.user_id
            HAVING ever > 0
            ORDER BY week ASC, name ASC
            """,
            (start, end),
        ).fetchall()
        return [(r["name"], int(r["week"])) for r in rows]
