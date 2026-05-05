from models.user import User
from repositories.json_repository import JsonRepository


class UserRepository(JsonRepository):
    def get_all(self):
        return [User.from_dict(item) for item in self._read_raw()]

    def get_by_id(self, user_id):
        if user_id is None:
            return None

        for user in self.get_all():
            if user.id == int(user_id):
                return user
        return None

    def get_by_email(self, email):
        normalized_email = (email or "").strip().lower()
        for user in self.get_all():
            if user.email.lower() == normalized_email:
                return user
        return None

    def add(self, user):
        users = self._read_raw()
        if not user.id:
            user.id = self._next_id(users)
        users.append(user.to_dict())
        self._write_raw(users)
        return user

    def update(self, user):
        users = self._read_raw()
        for index, item in enumerate(users):
            if int(item["id"]) == int(user.id):
                users[index] = user.to_dict()
                self._write_raw(users)
                return user
        return None

    def delete(self, user_id):
        users = self._read_raw()
        filtered = [item for item in users if int(item["id"]) != int(user_id)]
        self._write_raw(filtered)
        return len(filtered) != len(users)

    def set_blocked(self, user_id, is_blocked):
        user = self.get_by_id(user_id)
        if not user:
            return None
        user.is_blocked = bool(is_blocked)
        return self.update(user)
