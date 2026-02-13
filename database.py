import sqlite3
from pathlib import Path
from typing import List, Tuple


DB_PATH = Path(__file__).with_name("bot.db")


def _get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """Создает таблицы для хранения бесед и администраторов, если их еще нет."""
    with _get_connection() as conn:
        # Таблица чатов
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                title   TEXT,
                type    TEXT
            )
            """
        )

        # Таблица администраторов рассылки
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                user_id  INTEGER PRIMARY KEY,
                is_owner INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        conn.commit()


def add_chat(chat_id: int, title: str, chat_type: str) -> None:
    """Добавляет беседу в БД (id, название, тип). Если уже есть — игнорирует."""
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO chats (chat_id, title, type)
            VALUES (?, ?, ?)
            """,
            (chat_id, title, chat_type),
        )
        conn.commit()


def get_all_chat_ids() -> List[int]:
    """Возвращает список ID всех бесед."""
    with _get_connection() as conn:
        cursor = conn.execute("SELECT chat_id FROM chats")
        rows: List[Tuple[int]] = cursor.fetchall()
    return [row[0] for row in rows]


# ---- Работа с администраторами рассылки ----

def add_admin(user_id: int, *, is_owner: bool = False) -> None:
    """Добавляет пользователя в админы рассылки."""
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO admins (user_id, is_owner)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET is_owner=excluded.is_owner OR admins.is_owner
            """,
            (user_id, 1 if is_owner else 0),
        )
        conn.commit()


def remove_admin(user_id: int) -> None:
    """Удаляет пользователя из админов (но владельца можно убрать только вручную из БД)."""
    with _get_connection() as conn:
        conn.execute(
            """
            DELETE FROM admins
            WHERE user_id = ? AND is_owner = 0
            """,
            (user_id,),
        )
        conn.commit()


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь админом рассылки (включая владельца)."""
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM admins WHERE user_id = ?",
            (user_id,),
        )
        return cursor.fetchone() is not None


def is_owner(user_id: int) -> bool:
    """Проверяет, является ли пользователь владельцем бота."""
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM admins WHERE user_id = ? AND is_owner = 1",
            (user_id,),
        )
        return cursor.fetchone() is not None


def has_any_owner() -> bool:
    """Есть ли хоть один владелец в БД."""
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM admins WHERE is_owner = 1 LIMIT 1",
        )
        return cursor.fetchone() is not None


def list_admin_ids() -> List[int]:
    """Возвращает список ID всех админов рассылки."""
    with _get_connection() as conn:
        cursor = conn.execute("SELECT user_id FROM admins ORDER BY is_owner DESC, user_id")
        rows: List[Tuple[int]] = cursor.fetchall()
    return [row[0] for row in rows]


