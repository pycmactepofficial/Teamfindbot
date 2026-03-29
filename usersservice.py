
"""Service for managing users and teams with SQLite"""

import sqlite3
from typing import List, Dict, Optional
import os

class UserService:
    def __init__(self, db_file: str = "database.db"):
        self.db_file = db_file
        self.init_db()

    def init_db(self):
        """Initialize database with tables"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                game TEXT NOT NULL,
                role TEXT,
                rank TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, type, name)
            )
        ''')
        conn.commit()
        conn.close()

    def add_user(self, user_id: int, name: str, game: str, role: str, rank: str, description: str) -> Dict:
        """Add or update player profile"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO profiles (user_id, type, name, game, role, rank, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, 'player', name, game, role, rank, description))
            profile_id = cursor.lastrowid
            conn.commit()
            return {'status': 'success', 'id': profile_id}
        except sqlite3.IntegrityError:
            # Update if exists
            cursor.execute('''
                UPDATE profiles 
                SET game = ?, role = ?, rank = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND type = ? AND name = ?
            ''', (game, role, rank, description, user_id, 'player', name))
            conn.commit()
            return {'status': 'updated'}
        finally:
            conn.close()

    def add_team(self, user_id: int, name: str, game: str, rank: str, members: int, description: str) -> Dict:
        """Add or update team profile"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        try:
            # Store members in description if needed or as separate field
            full_desc = f"Состав: {members}/5\n{description}" if description else f"Состав: {members}/5"
            cursor.execute('''
                INSERT INTO profiles (user_id, type, name, game, rank, description)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, 'team', name, game, rank, full_desc))
            profile_id = cursor.lastrowid
            conn.commit()
            return {'status': 'success', 'id': profile_id}
        except sqlite3.IntegrityError:
            full_desc = f"Состав: {members}/5\n{description}" if description else f"Состав: {members}/5"
            cursor.execute('''
                UPDATE profiles 
                SET game = ?, rank = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND type = ? AND name = ?
            ''', (game, rank, full_desc, user_id, 'team', name))
            conn.commit()
            return {'status': 'updated'}
        finally:
            conn.close()

    def delete_profile(self, user_id: int, profile_id: int) -> bool:
        """Delete profile (only owner can delete)"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM profiles WHERE id = ? AND user_id = ?', (profile_id, user_id))
        result = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return result

    def update_profile(self, user_id: int, profile_id: int, **kwargs) -> bool:
        """Update profile fields (only owner can update)"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        allowed_fields = {'name', 'game', 'role', 'rank', 'description'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            conn.close()
            return False
        
        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [profile_id, user_id]
        
        cursor.execute(f'UPDATE profiles SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?', values)
        result = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return result

    def get_user_profiles(self, user_id: int) -> List[Dict]:
        """Get all profiles created by user"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM profiles WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_profile_by_id(self, profile_id: int, user_id: int) -> Optional[Dict]:
        """Get specific profile (verify ownership)"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM profiles WHERE id = ? AND user_id = ?', (profile_id, user_id))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_all_data(self) -> List[Dict]:
        """Get all profiles for public search"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT id, type, name, game, role, rank, description FROM profiles ORDER BY updated_at DESC')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def search(self, game: Optional[str] = None, type_filter: Optional[str] = None, search_text: Optional[str] = None) -> List[Dict]:
        """Search profiles"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = 'SELECT id, type, name, game, role, rank, description FROM profiles WHERE 1=1'
        params = []
        
        if game and game != 'all':
            query += ' AND game = ?'
            params.append(game)
        
        if type_filter and type_filter != 'all':
            query += ' AND type = ?'
            params.append(type_filter)
        
        if search_text:
            query += ' AND (role LIKE ? OR rank LIKE ? OR description LIKE ? OR name LIKE ?)'
            search_pattern = f'%{search_text}%'
            params.extend([search_pattern] * 4)
        
        query += ' ORDER BY updated_at DESC'
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

# Global instance
user_service = UserService()