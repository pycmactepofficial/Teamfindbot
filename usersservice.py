
"""Service for managing users and teams with JSON storage"""

import json
import os
from typing import List, Dict, Optional
from datetime import datetime

class UserService:
    def __init__(self, json_file: str = "users.json"):
        self.json_file = json_file
        self.init_json()

    def init_json(self):
        """Initialize JSON file with basic structure"""
        if not os.path.exists(self.json_file):
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump({"users": []}, f, ensure_ascii=False, indent=2)

    def _load_data(self) -> Dict:
        """Load data from JSON file"""
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"users": []}

    def _save_data(self, data: Dict):
        """Save data to JSON file"""
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_user_by_chat_id(self, chat_id: int) -> Optional[Dict]:
        """Get user data by chat_id"""
        data = self._load_data()
        for user in data["users"]:
            if user["chat_id"] == chat_id:
                return user
        return None

    def get_user_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Get user data by user_id"""
        data = self._load_data()
        for user in data["users"]:
            if user.get("user_id", user["chat_id"]) == user_id:  # Fallback for old entries
                return user
        return None

    def add_or_update_user(self, chat_id: int, user_id: int = None) -> Dict:
        """Add new user or update existing one"""
        data = self._load_data()
        user = self.get_user_by_chat_id(chat_id)

        if user_id is None:
            user_id = chat_id  # For personal chats

        if user is None:
            user = {
                "chat_id": chat_id,
                "user_id": user_id,
                "profiles": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            data["users"].append(user)
        else:
            user["user_id"] = user_id  # Update if needed
            user["updated_at"] = datetime.now().isoformat()

        self._save_data(data)
        return user

    def add_user(self, user_id: int, name: str, game: str, role: str, rank: str, description: str) -> Dict:
        """Add or update player profile"""
        data = self._load_data()
        user = self.get_user_by_user_id(user_id)

        if user is None:
            # Create user if doesn't exist
            user = {
                "chat_id": user_id,  # Assume chat_id = user_id for personal use
                "user_id": user_id,
                "profiles": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            data["users"].append(user)

        # Check if profile already exists
        existing_profile = None
        for profile in user["profiles"]:
            if profile["type"] == "player" and profile["name"] == name:
                existing_profile = profile
                break

        if existing_profile:
            # Update existing
            existing_profile.update({
                "game": game,
                "role": role,
                "rank": rank,
                "description": description,
                "updated_at": datetime.now().isoformat()
            })
            result = {"status": "updated", "id": existing_profile["id"]}
        else:
            # Create new
            profile_id = len(user["profiles"]) + 1
            profile = {
                "id": profile_id,
                "type": "player",
                "name": name,
                "game": game,
                "role": role,
                "rank": rank,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            user["profiles"].append(profile)
            result = {"status": "success", "id": profile_id}

        user["updated_at"] = datetime.now().isoformat()
        self._save_data(data)
        return result

    def add_team(self, user_id: int, name: str, game: str, rank: str, members: int, description: str) -> Dict:
        """Add or update team profile"""
        data = self._load_data()
        user = self.get_user_by_user_id(user_id)

        if user is None:
            # Create user if doesn't exist
            user = {
                "chat_id": user_id,
                "user_id": user_id,
                "profiles": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            data["users"].append(user)

        # Check if team already exists
        existing_profile = None
        for profile in user["profiles"]:
            if profile["type"] == "team" and profile["name"] == name:
                existing_profile = profile
                break

        full_desc = f"Состав: {members}/5\n{description}" if description else f"Состав: {members}/5"

        if existing_profile:
            # Update existing
            existing_profile.update({
                "game": game,
                "rank": rank,
                "description": full_desc,
                "updated_at": datetime.now().isoformat()
            })
            result = {"status": "updated", "id": existing_profile["id"]}
        else:
            # Create new
            profile_id = len(user["profiles"]) + 1
            profile = {
                "id": profile_id,
                "type": "team",
                "name": name,
                "game": game,
                "rank": rank,
                "description": full_desc,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            user["profiles"].append(profile)
            result = {"status": "success", "id": profile_id}

        user["updated_at"] = datetime.now().isoformat()
        self._save_data(data)
        return result

    def delete_profile(self, user_id: int, profile_id: int) -> bool:
        """Delete profile (only owner can delete)"""
        data = self._load_data()
        user = self.get_user_by_user_id(user_id)

        if user is None:
            return False

        for i, profile in enumerate(user["profiles"]):
            if profile["id"] == profile_id:
                user["profiles"].pop(i)
                user["updated_at"] = datetime.now().isoformat()
                self._save_data(data)
                return True

        return False

    def update_profile(self, user_id: int, profile_id: int, **kwargs) -> bool:
        """Update profile fields (only owner can update)"""
        data = self._load_data()
        user = self.get_user_by_user_id(user_id)

        if user is None:
            return False

        for profile in user["profiles"]:
            if profile["id"] == profile_id:
                allowed_fields = {'name', 'game', 'role', 'rank', 'description'}
                updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

                if updates:
                    profile.update(updates)
                    profile["updated_at"] = datetime.now().isoformat()
                    user["updated_at"] = datetime.now().isoformat()
                    self._save_data(data)
                    return True

        return False

    def get_user_profiles(self, chat_id: int) -> List[Dict]:
        """Get all profiles created by user"""
        user = self.get_user_by_user_id(user_id)
        if user is None:
            return []
        return user["profiles"]

    def get_profile_by_id(self, user_id: int, profile_id: int) -> Optional[Dict]:
        """Get specific profile (verify ownership)"""
        user = self.get_user_by_user_id(user_id)
        if user is None:
            return None

        for profile in user["profiles"]:
            if profile["id"] == profile_id:
                return profile

        return None

    def get_all_data(self) -> List[Dict]:
        """Get all profiles for public search"""
        data = self._load_data()
        result = []
        for user in data["users"]:
            for profile in user["profiles"]:
                # Add chat_id for ownership verification
                profile_copy = profile.copy()
                profile_copy["chat_id"] = user["chat_id"]
                result.append(profile_copy)
        return result

    def search(self, game: Optional[str] = None, type_filter: Optional[str] = None, search_text: Optional[str] = None) -> List[Dict]:
        """Search profiles"""
        all_data = self.get_all_data()
        result = []

        for item in all_data:
            # Filter by game
            if game and game != 'all' and item.get('game') != game:
                continue

            # Filter by type
            if type_filter and type_filter != 'all' and item.get('type') != type_filter:
                continue

            # Filter by search text
            if search_text:
                search_lower = search_text.lower()
                searchable_fields = [
                    item.get('name', ''),
                    item.get('role', ''),
                    item.get('rank', ''),
                    item.get('description', '')
                ]
                if not any(search_lower in field.lower() for field in searchable_fields if field):
                    continue

            result.append(item)

        # Sort by updated_at (most recent first)
        result.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        return result

# Global instance
user_service = UserService()