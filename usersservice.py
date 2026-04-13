import aiosqlite
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os
from contextlib import asynccontextmanager
import json
import aiohttp
import logging

DB_PATH = os.getenv("DB_PATH", "users.db")
STEAM_API_KEY = os.getenv("STEAM_API_KEY", "")

class UserService:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    @asynccontextmanager
    async def _get_connection(self):
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            await conn.close()

    async def init_db(self):
        async with self._get_connection() as conn:
            # Таблица users
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    chat_id INTEGER PRIMARY KEY,
                    user_id INTEGER UNIQUE NOT NULL,
                    steam_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    verification_verdict TEXT DEFAULT 'not_checked',
                    verification_expires_at TEXT,
                    verification_report TEXT,
                    verification_updated_at TEXT
                )
            """)
            # Таблица profiles
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
                    steam_playtime INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    cheat_verdict TEXT DEFAULT 'not_checked',
                    cheat_report TEXT,
                    last_verification TEXT,
                    team_members INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            """)
            # Добавляем колонки, если их нет (миграции)
            await self._migrate_add_columns(conn)
            await conn.commit()

    async def _migrate_add_columns(self, conn):
        # users: steam_id
        cursor = await conn.execute("PRAGMA table_info(users)")
        existing = [row['name'] for row in await cursor.fetchall()]
        if 'steam_id' not in existing:
            await conn.execute("ALTER TABLE users ADD COLUMN steam_id TEXT")
        # profiles: steam_playtime
        cursor = await conn.execute("PRAGMA table_info(profiles)")
        existing = [row['name'] for row in await cursor.fetchall()]
        if 'steam_playtime' not in existing:
            await conn.execute("ALTER TABLE profiles ADD COLUMN steam_playtime INTEGER DEFAULT 0")

    # ---------- Steam ----------
    async def update_steam_id(self, user_id: int, steam_id: str) -> bool:
        async with self._get_connection() as conn:
            # Сначала убедимся, что пользователь существует
            async with conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
                user = await cursor.fetchone()
                if not user:
                    now = datetime.now().isoformat()
                    await conn.execute(
                        "INSERT INTO users (chat_id, user_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
                        (user_id, user_id, now, now)
                    )
                    logging.info(f"Created user record for {user_id}")
            # Обновляем steam_id
            await conn.execute(
                "UPDATE users SET steam_id = ?, updated_at = ? WHERE user_id = ?",
                (steam_id, datetime.now().isoformat(), user_id)
            )
            await conn.commit()
            # Проверяем
            async with conn.execute("SELECT steam_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                success = row is not None and row['steam_id'] == steam_id
                logging.info(f"update_steam_id for user {user_id}: {'OK' if success else 'FAIL'}")
                return success

    async def get_steam_id(self, user_id: int) -> Optional[str]:
        async with self._get_connection() as conn:
            async with conn.execute("SELECT steam_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return row['steam_id'] if row else None

    async def get_steam_games(self, user_id: int) -> List[Dict]:
        steam_id = await self.get_steam_id(user_id)
        if not steam_id:
            logging.warning(f"No steam_id for user {user_id}")
            return []
        if not STEAM_API_KEY:
            logging.error("STEAM_API_KEY not set")
            return []
        url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
        params = {
            'key': STEAM_API_KEY,
            'steamid': steam_id,
            'include_appinfo': '1',
            'include_played_free_games': '1'
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as resp:
                    text = await resp.text()
                    logging.info(f"Steam API for {steam_id}: status {resp.status}, preview {text[:200]}")
                    if resp.status != 200:
                        logging.error(f"Steam API error: {resp.status}")
                        return []
                    data = await resp.json()
                    games = data.get('response', {}).get('games', [])
                    return [{
                        'appid': g['appid'],
                        'name': g.get('name', 'Unknown'),
                        'playtime_minutes': g.get('playtime_forever', 0),
                        'img_icon_url': g.get('img_icon_url', '')
                    } for g in games]
            except Exception as e:
                logging.exception(f"Exception in get_steam_games: {e}")
                return []

    # ---------- Пользователи ----------
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

    async def _get_user_by_user_id(self, user_id: int) -> Optional[Dict]:
        async with self._get_connection() as conn:
            async with conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_chat_id_by_user_id(self, user_id: int) -> Optional[int]:
        async with self._get_connection() as conn:
            async with conn.execute("SELECT chat_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    # ---------- Анкеты ----------
    async def add_user(self, user_id: int, name: str, game: str, role: str, rank: str, description: str, steam_playtime: int = 0) -> Dict:
        user = await self._get_user_by_user_id(user_id)
        if not user:
            await self.add_or_update_user(user_id, user_id)

        now = datetime.now().isoformat()
        async with self._get_connection() as conn:
            # Проверка дубляжа
            async with conn.execute(
                "SELECT id FROM profiles WHERE user_id = ? AND type = 'player' AND game = ?",
                (user_id, game)
            ) as cursor:
                existing = await cursor.fetchone()
            if existing:
                # Обновляем
                await conn.execute(
                    """UPDATE profiles
                       SET name = ?, role = ?, rank = ?, description = ?, steam_playtime = ?, updated_at = ?
                       WHERE id = ?""",
                    (name, role, rank, description, steam_playtime, now, existing[0])
                )
                await conn.commit()
                return {"status": "updated", "id": existing[0]}
            else:
                cursor = await conn.execute(
                    """INSERT INTO profiles
                       (user_id, type, name, game, role, rank, description, steam_playtime, created_at, updated_at)
                       VALUES (?, 'player', ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, name, game, role, rank, description, steam_playtime, now, now)
                )
                await conn.commit()
                return {"status": "success", "id": cursor.lastrowid}

    async def add_team(self, user_id: int, name: str, game: str, rank: str, members: int, description: str) -> Dict:
        user = await self._get_user_by_user_id(user_id)
        if not user:
            await self.add_or_update_user(user_id, user_id)

        now = datetime.now().isoformat()
        async with self._get_connection() as conn:
            async with conn.execute(
                "SELECT id FROM profiles WHERE user_id = ? AND type = 'team' AND game = ?",
                (user_id, game)
            ) as cursor:
                existing = await cursor.fetchone()
            if existing:
                await conn.execute(
                    """UPDATE profiles
                       SET name = ?, rank = ?, description = ?, team_members = ?, updated_at = ?
                       WHERE id = ?""",
                    (name, rank, description, members, now, existing[0])
                )
                await conn.commit()
                return {"status": "updated", "id": existing[0]}
            else:
                cursor = await conn.execute(
                    """INSERT INTO profiles
                       (user_id, type, name, game, rank, description, team_members, created_at, updated_at)
                       VALUES (?, 'team', ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, name, game, rank, description, members, now, now)
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
        allowed = {'name', 'game', 'role', 'rank', 'description', 'team_members', 'steam_playtime'}
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
            async with conn.execute("""
                SELECT profiles.*, users.verification_verdict AS user_verdict
                FROM profiles
                JOIN users ON profiles.user_id = users.user_id
                WHERE profiles.user_id = ?
                ORDER BY profiles.updated_at DESC
            """, (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_profile_by_id(self, profile_id: int) -> Optional[Dict]:
        async with self._get_connection() as conn:
            async with conn.execute(
                "SELECT profiles.*, users.user_id AS owner_user_id FROM profiles JOIN users ON profiles.user_id = users.user_id WHERE profiles.id = ?",
                (profile_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
            
    # ---------- Поиск ----------
    async def search(self, game: Optional[str] = None, type_filter: Optional[str] = None, search_text: Optional[str] = None) -> List[Dict]:
        query = """
            SELECT profiles.*, users.user_id AS owner_user_id, users.verification_verdict AS user_verdict
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

    # ---------- Верификация ----------
    async def save_user_verification(self, user_id: int, report: dict) -> bool:
        verdict = report.get('verdict', 'unknown')
        findings = report.get('findings', {})
        report_json = json.dumps(findings)
        now = datetime.now().isoformat()
        expires_at = (datetime.now() + timedelta(days=2)).isoformat()
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                UPDATE users
                SET verification_verdict = ?,
                    verification_expires_at = ?,
                    verification_report = ?,
                    verification_updated_at = ?
                WHERE user_id = ?
            """, (verdict, expires_at, report_json, now, user_id))
            await conn.commit()
            return cursor.rowcount > 0

    async def get_user_verification_status(self, user_id: int) -> dict:
        async with self._get_connection() as conn:
            async with conn.execute(
                "SELECT verification_verdict, verification_expires_at, verification_updated_at FROM users WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return {"verdict": "not_checked", "is_valid": False, "expires_at": None}
                verdict = row['verification_verdict'] or 'not_checked'
                expires_at = row['verification_expires_at']
                is_valid = (verdict == 'clean' and expires_at and datetime.now().isoformat() < expires_at)
                return {
                    "verdict": verdict,
                    "is_valid": is_valid,
                    "expires_at": expires_at,
                    "updated_at": row['verification_updated_at']
                }

user_service = UserService()