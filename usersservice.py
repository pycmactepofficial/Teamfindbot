
"""Service for managing users and teams"""

from typing import List, Dict, Optional
import json
import os

class UserService:
    def __init__(self, data_file: str = "users_data.json"):
        self.data_file = data_file
        self.users: List[Dict] = []
        self.teams: List[Dict] = []
        self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.users = data.get('users', [])
                self.teams = data.get('teams', [])

    def save_data(self):
        data = {
            'users': self.users,
            'teams': self.teams
        }
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_user(self, user_id: int, name: str, game: str, role: str, rank: str, description: str):
        user = {
            'id': user_id,
            'type': 'player',
            'name': name,
            'game': game,
            'role': role,
            'rank': rank,
            'description': description
        }
        # Remove existing user if any
        self.users = [u for u in self.users if u['id'] != user_id]
        self.users.append(user)
        self.save_data()

    def add_team(self, user_id: int, name: str, game: str, rank: str, members: int, description: str):
        team = {
            'id': user_id,
            'type': 'team',
            'name': name,
            'game': game,
            'rank': rank,
            'members': members,
            'description': description
        }
        # Remove existing team if any
        self.teams = [t for t in self.teams if t['id'] != user_id]
        self.teams.append(team)
        self.save_data()

    def get_all_data(self) -> List[Dict]:
        return self.users + self.teams

    def search(self, game: Optional[str] = None, type_filter: Optional[str] = None, search_text: Optional[str] = None) -> List[Dict]:
        data = self.get_all_data()
        if game and game != 'all':
            data = [item for item in data if item['game'] == game]
        if type_filter and type_filter != 'all':
            data = [item for item in data if item['type'] == type_filter]
        if search_text:
            search_lower = search_text.lower()
            filtered = []
            for item in data:
                if (item.get('role', '').lower().find(search_lower) != -1 or
                    item['rank'].lower().find(search_lower) != -1 or
                    item['description'].lower().find(search_lower) != -1 or
                    item['name'].lower().find(search_lower) != -1):
                    filtered.append(item)
            data = filtered
        return data

# Global instance
user_service = UserService()