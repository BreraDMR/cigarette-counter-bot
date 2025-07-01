"""Слой работы с базой данных (SQLite).

Хранит пользователей и их сигареты. Каждая запись может иметь
привязанное локально сохранённое фото (путь к файлу).
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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Создаёт таблицы, если их ещё нет (с лёгкой миграцией display_name)."""
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

            -- Расходники: пачка табака/бумаги/фильтров/сигарет.
            -- Пользователь «открывает» упаковку (пишет цену), потом «закрывает»,
            -- когда она закончилась. closed_at = NULL → ещё в ходу.
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
        # Миграции для старых БД (добавляем недостающие колонки)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
        for col, ddl in [
            ("display_name", "TEXT"),
            ("currency", "TEXT"),
            ("price_per_pack", "REAL"),
            ("pack_size", "INTEGER"),
        ]:
            if col not in cols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
        # Язык интерфейса. Новые пользователи получают английский (см. upsert_user),
        # а существующие на момент миграции — русский (это Дамир и его друзья).
        if "language" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN language TEXT")
            conn.execute("UPDATE users SET language = 'ru' WHERE language IS NULL")


def user_exists(user_id: int) -> bool:
    with _connect() as conn:
        return conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
        ).fetchone() is not None


def upsert_user(user_id: int, username: Optional[str], first_name: Optional[str]) -> None:
    """Гарантирует наличие пользователя. Отображаемое имя (display_name)
    задаётся при первом создании из имени Telegram и НЕ перезатирается потом —
    его меняет только set_display_name (через регистрацию/смену имени)."""
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
    """Язык интерфейса пользователя ('en' по умолчанию)."""
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
    """Записывает перекур и возвращает его id."""
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
    """id последнего перекура пользователя (для привязки фото)."""
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
    """Сумма сигарет по дням: [(YYYY-MM-DD, count), ...] по возрастанию даты."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT substr(created_at, 1, 10) AS day, SUM(count) AS total "
            "FROM sets WHERE user_id = ? GROUP BY day ORDER BY day",
            (user_id,),
        ).fetchall()
        return [(r["day"], int(r["total"])) for r in rows]


def sessions(user_id: int) -> list[tuple[str, int]]:
    """Все перекуры по порядку: [(timestamp, count), ...]."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT created_at, count FROM sets WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
        return [(r["created_at"], int(r["count"])) for r in rows]


def by_hour(user_id: int) -> list[int]:
    """Распределение сигарет по часам суток: список из 24 чисел (индекс = час)."""
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
    """Распределение сигарет по дням недели: 7 чисел, индекс 0=Пн … 6=Вс."""
    out = [0] * 7
    with _connect() as conn:
        # strftime('%w'): 0=воскресенье … 6=суббота
        rows = conn.execute(
            "SELECT CAST(strftime('%w', created_at) AS INTEGER) AS w, "
            "SUM(count) AS total FROM sets WHERE user_id = ? GROUP BY w",
            (user_id,),
        ).fetchall()
    for r in rows:
        w = r["w"]
        if w is not None:
            idx = (w - 1) % 7  # сдвигаем так, чтобы 0=Пн … 6=Вс
            out[idx] = int(r["total"])
    return out


def leaderboard() -> list[tuple[str, int]]:
    """Рейтинг всех пользователей: [(имя, всего_сигарет), ...] по убыванию."""
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
    """Последние перекуры пользователя: [(id, timestamp, count), ...] — свежие сверху."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, count FROM sets "
            "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [(int(r["id"]), r["created_at"], int(r["count"])) for r in rows]


def set_owner(set_id: int) -> Optional[int]:
    """user_id владельца перекура, либо None если перекура нет."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT user_id FROM sets WHERE id = ?", (set_id,)
        ).fetchone()
        return int(row["user_id"]) if row else None


def edit_set(set_id: int, count: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE sets SET count = ? WHERE id = ?", (count, set_id))


def set_created_at(set_id: int) -> Optional[str]:
    """Время перекура (ISO-строка), либо None если записи нет."""
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


# ── Настройки пользователя (валюта, цена и размер пачки) ──────────
def get_settings(user_id: int) -> dict:
    """Настройки стоимости. price_per_pack=None означает «не задано»."""
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


# ── Недельные суммы и рейтинг «меньше = лучше» ────────────────────
def range_total(user_id: int, start: str, end: str) -> int:
    """Сумма сигарет за период [start, end) — даты в формате YYYY-MM-DD."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(count), 0) AS t FROM sets "
            "WHERE user_id = ? AND created_at >= ? AND created_at < ?",
            (user_id, start, end),
        ).fetchone()
        return int(row["t"])


# ── Расходники (табак / бумага / фильтры / сигареты) ──────────────
def open_consumable(user_id: int, kind: str, price: float, currency: str) -> int:
    """Открывает новую упаковку. Если упаковка этого же типа была ещё открыта —
    автоматически закрывает её (значит «старая кончилась, новая началась»)."""
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
    """Отмечает открытую упаковку этого типа как закончившуюся.
    Возвращает True, если было что закрывать."""
    now = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE consumables SET closed_at = ? "
            "WHERE user_id = ? AND kind = ? AND closed_at IS NULL",
            (now, user_id, kind),
        )
        return cur.rowcount > 0


def open_consumables(user_id: int) -> list[tuple[str, float, str, str]]:
    """Сейчас открытые упаковки: [(kind, price, currency, opened_at), ...]."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT kind, price, currency, opened_at FROM consumables "
            "WHERE user_id = ? AND closed_at IS NULL ORDER BY kind",
            (user_id,),
        ).fetchall()
        return [(r["kind"], float(r["price"]), r["currency"], r["opened_at"]) for r in rows]


def all_consumables(user_id: int) -> list[tuple[str, float, str]]:
    """Все купленные упаковки: [(kind, price, currency), ...] —
    валюту храним по каждой покупке, чтобы потом сконвертировать в Python."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT kind, price, currency FROM consumables WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return [(r["kind"], float(r["price"]), r["currency"]) for r in rows]


def leaderboard_week(start: str, end: str) -> list[tuple[str, int]]:
    """Рейтинг за период [start, end): [(имя, сигарет_за_неделю), ...]
    по ВОЗРАСТАНИЮ (меньше — выше). Только пользователи, у кого вообще есть записи."""
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
