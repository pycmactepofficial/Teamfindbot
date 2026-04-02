import json
import os
from typing import List, Dict, Optional
from datetime import datetime

class UserService:
    def __init__(self, json_file: str = "users.json"):
        self.json_file = json_file
        self.init_json()

    def init_json(self):
        if not os.path.exists(self.json_file):
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump({"users": []}, f, ensure_ascii=False, indent=2)

    def _load_data(self) -> Dict:
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"users": []}

    def _save_data(self, data: Dict):
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_user_by_chat_id(self, chat_id: int) -> Optional[Dict]:
        data = self._load_data()
        for user in data["users"]:
            if user["chat_id"] == chat_id:
                return user
        return None

    def get_user_by_user_id(self, user_id: int) -> Optional[Dict]:
        data = self._load_data()
        for user in data["users"]:
            if user.get("user_id") == user_id:
                return user
        return None

    def add_or_update_user(self, chat_id: int, user_id: int = None) -> Dict:
        data = self._load_data()
        user = self.get_user_by_chat_id(chat_id)
        if user_id is None:
            user_id = chat_id
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
            user["user_id"] = user_id
            user["updated_at"] = datetime.now().isoformat()
        self._save_data(data)
        return user

    def add_user(self, user_id: int, name: str, game: str, role: str, rank: str, description: str) -> Dict:
        data = self._load_data()
        user = self.get_user_by_user_id(user_id)
        if user is None:
            user = {
                "chat_id": user_id,
                "user_id": user_id,
                "profiles": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            data["users"].append(user)

        # Поиск существующего профиля игрока с таким же именем
        existing = None
        for p in user["profiles"]:
            if p.get("type") == "player" and p.get("name") == name:
                existing = p
                break

        if existing:
            existing.update({
                "game": game,
                "role": role,
                "rank": rank,
                "description": description,
                "updated_at": datetime.now().isoformat()
            })
            result = {"status": "updated", "id": existing["id"]}
        else:
            max_id = max([p.get("id", 0) for p in user["profiles"]], default=0)
            new_id = max_id + 1
            profile = {
                "id": new_id,
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
            result = {"status": "success", "id": new_id}

        user["updated_at"] = datetime.now().isoformat()
        self._save_data(data)
        return result

    def add_team(self, user_id: int, name: str, game: str, rank: str, members: int, description: str) -> Dict:
        data = self._load_data()
        user = self.get_user_by_user_id(user_id)
        if user is None:
            user = {
                "chat_id": user_id,
                "user_id": user_id,
                "profiles": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            data["users"].append(user)

        # Поиск существующей команды с таким же названием
        existing = None
        for p in user["profiles"]:
            if p.get("type") == "team" and p.get("name") == name:
                existing = p
                break

        full_desc = f"Состав: {members}/5\n{description}" if description else f"Состав: {members}/5"

        if existing:
            existing.update({
                "game": game,
                "rank": rank,
                "description": full_desc,
                "updated_at": datetime.now().isoformat()
            })
            result = {"status": "updated", "id": existing["id"]}
        else:
            max_id = max([p.get("id", 0) for p in user["profiles"]], default=0)
            new_id = max_id + 1
            profile = {
                "id": new_id,
                "type": "team",
                "name": name,
                "game": game,
                "rank": rank,
                "description": full_desc,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            user["profiles"].append(profile)
            result = {"status": "success", "id": new_id}

        user["updated_at"] = datetime.now().isoformat()
        self._save_data(data)
        return result

    def delete_profile(self, user_id: int, profile_id: int) -> bool:
        data = self._load_data()
        user = self.get_user_by_user_id(user_id)
        if not user:
            return False
        for i, p in enumerate(user["profiles"]):
            if p["id"] == profile_id:
                user["profiles"].pop(i)
                user["updated_at"] = datetime.now().isoformat()
                self._save_data(data)
                return True
        return False

    def update_profile(self, user_id: int, profile_id: int, **kwargs) -> bool:
        data = self._load_data()
        user = self.get_user_by_user_id(user_id)
        if not user:
            return False
        for p in user["profiles"]:
            if p["id"] == profile_id:
                allowed = {'name', 'game', 'role', 'rank', 'description'}
                updates = {k: v for k, v in kwargs.items() if k in allowed}
                if updates:
                    p.update(updates)
                    p["updated_at"] = datetime.now().isoformat()
                    user["updated_at"] = datetime.now().isoformat()
                    self._save_data(data)
                    return True
        return False

    def get_user_profiles(self, user_id: int) -> List[Dict]:
        user = self.get_user_by_user_id(user_id)
        if not user:
            return []
        return user["profiles"]

    def get_profile_by_id(self, user_id: int, profile_id: int) -> Optional[Dict]:
        user = self.get_user_by_user_id(user_id)
        if not user:
            return None
        for p in user["profiles"]:
            if p["id"] == profile_id:
                return p
        return None

    def get_all_data(self) -> List[Dict]:
        data = self._load_data()
        result = []
        for user in data["users"]:
            for profile in user["profiles"]:
                profile_copy = profile.copy()
                profile_copy["user_id"] = user["user_id"]
                result.append(profile_copy)
        return result

    def search(self, game: Optional[str] = None, type_filter: Optional[str] = None, search_text: Optional[str] = None) -> List[Dict]:
        all_data = self.get_all_data()
        result = []
        for item in all_data:
            if game and game != 'all' and item.get('game') != game:
                continue
            if type_filter and type_filter != 'all' and item.get('type') != type_filter:
                continue
            if search_text:
                search_lower = search_text.lower()
                fields = [item.get('name',''), item.get('role',''), item.get('rank',''), item.get('description','')]
                if not any(search_lower in f.lower() for f in fields if f):
                    continue
            result.append(item)
        result.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        return result

user_service = UserService()