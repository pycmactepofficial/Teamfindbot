import aiosqlite
from datetime import datetime
from typing import List, Dict, Optional
import os
from contextlib import asynccontextmanager
import json  # <-- добавлен импорт

DB_PATH = os.getenv("DB_PATH", "users.db")

class UserService:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    @asynccontextmanager
    async def _get_connection(self):
        """Асинхронный контекстный менеджер соединения с БД."""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            await conn.close()

    async def init_db(self):
        """Создаёт таблицы, если их нет. Добавляет новые колонки при необходимости."""
        async with self._get_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    chat_id INTEGER PRIMARY KEY,
                    user_id INTEGER UNIQUE NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    game TEXT NOT NULL,
                    role TEXT,
                    rank TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    cheat_verdict TEXT DEFAULT 'not_checked',
                    cheat_report TEXT,
                    last_verification TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            """)
            # Миграция: добавляем колонки, если их ещё нет (для существующих БД)
            await self._migrate_add_verification_columns(conn)
            await conn.commit()

    async def _migrate_add_verification_columns(self, conn):
        """Проверяет и добавляет новые колонки в существующую таблицу profiles."""
        # Получаем список существующих колонок
        cursor = await conn.execute("PRAGMA table_info(profiles)")
        rows = await cursor.fetchall()
        existing_columns = [row['name'] for row in rows]
        
        columns_to_add = {
            'cheat_verdict': 'TEXT DEFAULT "not_checked"',
            'cheat_report': 'TEXT',
            'last_verification': 'TEXT'
        }
        for col_name, col_def in columns_to_add.items():
            if col_name not in existing_columns:
                await conn.execute(f"ALTER TABLE profiles ADD COLUMN {col_name} {col_def}")

    # ---------- Существующие методы (оставлены без изменений) ----------
    async def _get_user_by_chat_id(self, chat_id: int) -> Optional[Dict]:
        async with self._get_connection() as conn:
            async with conn.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def _get_user_by_user_id(self, user_id: int) -> Optional[Dict]:
        async with self._get_connection() as conn:
            async with conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def add_or_update_user(self, chat_id: int, user_id: int = None) -> Dict:
        if user_id is None:
            user_id = chat_id
        now = datetime.now().isoformat()

        async with self._get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO users (chat_id, user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    updated_at = excluded.updated_at
                """,
                (chat_id, user_id, now, now)
            )
            await conn.commit()

            async with conn.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row)

    async def get_profile_by_id(self, profile_id: int) -> Optional[Dict]:
        async with self._get_connection() as conn:
            async with conn.execute(
                "SELECT profiles.*, users.user_id AS owner_user_id, users.chat_id FROM profiles JOIN users ON profiles.user_id = users.user_id WHERE profiles.id = ?",
                (profile_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_chat_id_by_user_id(self, user_id: int) -> Optional[int]:
        async with self._get_connection() as conn:
            async with conn.execute("SELECT chat_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def add_user(self, user_id: int, name: str, game: str, role: str, rank: str, description: str) -> Dict:
        user = await self._get_user_by_user_id(user_id)
        if not user:
            await self.add_or_update_user(user_id, user_id)

        now = datetime.now().isoformat()
        async with self._get_connection() as conn:
            async with conn.execute(
                "SELECT id FROM profiles WHERE user_id = ? AND type = 'player' AND name = ?",
                (user_id, name)
            ) as cursor:
                existing = await cursor.fetchone()

            if existing:
                profile_id = existing[0]
                await conn.execute(
                    """UPDATE profiles
                       SET game = ?, role = ?, rank = ?, description = ?, updated_at = ?
                       WHERE id = ?""",
                    (game, role, rank, description, now, profile_id)
                )
                await conn.commit()
                return {"status": "updated", "id": profile_id}
            else:
                cursor = await conn.execute(
                    """INSERT INTO profiles
                       (user_id, type, name, game, role, rank, description, created_at, updated_at)
                       VALUES (?, 'player', ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, name, game, role, rank, description, now, now)
                )
                await conn.commit()
                return {"status": "success", "id": cursor.lastrowid}

    async def add_team(self, user_id: int, name: str, game: str, rank: str, members: int, description: str) -> Dict:
        user = await self._get_user_by_user_id(user_id)
        if not user:
            await self.add_or_update_user(user_id, user_id)

        full_desc = f"Состав: {members}/5\n{description}" if description else f"Состав: {members}/5"
        now = datetime.now().isoformat()

        async with self._get_connection() as conn:
            async with conn.execute(
                "SELECT id FROM profiles WHERE user_id = ? AND type = 'team' AND name = ?",
                (user_id, name)
            ) as cursor:
                existing = await cursor.fetchone()

            if existing:
                profile_id = existing[0]
                await conn.execute(
                    """UPDATE profiles
                       SET game = ?, rank = ?, description = ?, updated_at = ?
                       WHERE id = ?""",
                    (game, rank, full_desc, now, profile_id)
                )
                await conn.commit()
                return {"status": "updated", "id": profile_id}
            else:
                cursor = await conn.execute(
                    """INSERT INTO profiles
                       (user_id, type, name, game, rank, description, created_at, updated_at)
                       VALUES (?, 'team', ?, ?, ?, ?, ?, ?)""",
                    (user_id, name, game, rank, full_desc, now, now)
                )
                await conn.commit()
                return {"status": "success", "id": cursor.lastrowid}

    async def delete_profile(self, user_id: int, profile_id: int) -> bool:
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM profiles WHERE id = ? AND user_id = ?",
                (profile_id, user_id)
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def update_profile(self, user_id: int, profile_id: int, **kwargs) -> bool:
        allowed = {'name', 'game', 'role', 'rank', 'description'}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        set_clause = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values()) + [datetime.now().isoformat(), profile_id, user_id]

        async with self._get_connection() as conn:
            cursor = await conn.execute(
                f"UPDATE profiles SET {set_clause}, updated_at = ? WHERE id = ? AND user_id = ?",
                values
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def get_user_profiles(self, user_id: int) -> List[Dict]:
        async with self._get_connection() as conn:
            async with conn.execute(
                "SELECT * FROM profiles WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_all_data(self) -> List[Dict]:
        async with self._get_connection() as conn:
            async with conn.execute("""
                SELECT profiles.*, users.user_id AS owner_user_id
                FROM profiles
                JOIN users ON profiles.user_id = users.user_id
            """) as cursor:
                rows = await cursor.fetchall()
                result = []
                for row in rows:
                    d = dict(row)
                    d["user_id"] = d["owner_user_id"]
                    result.append(d)
                return result

    async def search(self, game: Optional[str] = None, type_filter: Optional[str] = None, search_text: Optional[str] = None) -> List[Dict]:
        query = """
            SELECT profiles.*, users.user_id AS owner_user_id
            FROM profiles
            JOIN users ON profiles.user_id = users.user_id
            WHERE 1=1
        """
        params = []
        if game and game != 'all':
            query += " AND profiles.game = ?"
            params.append(game)
        if type_filter and type_filter != 'all':
            query += " AND profiles.type = ?"
            params.append(type_filter)
        if search_text:
            query += """ AND (
                profiles.name LIKE ? OR
                profiles.role LIKE ? OR
                profiles.rank LIKE ? OR
                profiles.description LIKE ?
            )"""
            like = f"%{search_text}%"
            params.extend([like, like, like, like])

        query += " ORDER BY profiles.updated_at DESC"

        async with self._get_connection() as conn:
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                result = []
                for row in rows:
                    d = dict(row)
                    d["user_id"] = d["owner_user_id"]
                    result.append(d)
                return result

    # ---------- НОВЫЕ МЕТОДЫ ДЛЯ ВЕРИФИКАЦИИ ----------
    async def save_verification_result(self, profile_id: int, report: dict) -> bool:
        """
        Сохраняет JSON-отчёт от античита и вычисляет вердикт.
        report должен содержать ключ 'verdict' и опционально 'findings'.
        """
        verdict = report.get('verdict', 'unknown')
        findings = report.get('findings', {})
        findings_json = json.dumps(findings)
        now = datetime.now().isoformat()

        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                UPDATE profiles
                SET cheat_verdict = ?,
                    cheat_report = ?,
                    last_verification = ?
                WHERE id = ?
            """, (verdict, findings_json, now, profile_id))
            await conn.commit()
            return cursor.rowcount > 0

    async def get_verification_status(self, profile_id: int) -> Optional[Dict]:
        """Возвращает актуальный статус верификации для фронта."""
        async with self._get_connection() as conn:
            async with conn.execute(
                "SELECT cheat_verdict, last_verification FROM profiles WHERE id = ?",
                (profile_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "verdict": row['cheat_verdict'] or 'not_checked',
                        "last_check": row['last_verification']
                    }
                return None

user_service = UserService()