import shutil

from config import Config
from repositories.file_repository import FileRepository
from repositories.log_repository import LogRepository
from repositories.user_repository import UserRepository
from services.log_service import LogService


class AdminService:
    def __init__(
        self,
        user_repository=None,
        file_repository=None,
        log_repository=None,
        log_service=None,
    ):
        self.user_repository = user_repository or UserRepository(Config.USERS_FILE)
        self.file_repository = file_repository or FileRepository(Config.FILES_FILE)
        self.log_repository = log_repository or LogRepository(Config.LOGS_FILE)
        self.log_service = log_service or LogService(self.log_repository)

    def get_statistics(self):
        users = self.user_repository.get_all()
        files = self.file_repository.get_all()
        active_files = [file_item for file_item in files if not file_item.is_deleted]
        deleted_files = [file_item for file_item in files if file_item.is_deleted]
        favorite_files = [file_item for file_item in active_files if file_item.is_favorite]
        total_size = sum(file_item.size for file_item in files)

        return {
            "users_count": len(users),
            "files_count": len(active_files),
            "deleted_files_count": len(deleted_files),
            "favorite_files_count": len(favorite_files),
            "total_size": total_size,
            "average_file_size": total_size // len(files) if files else 0,
            "blocked_users_count": len([user for user in users if user.is_blocked]),
        }

    def get_users(self):
        return sorted(self.user_repository.get_all(), key=lambda user: user.id)

    def get_logs(self):
        return self.log_repository.get_all()

    def delete_user(self, admin_user, user_id):
        user = self.user_repository.get_by_id(user_id)
        if not user:
            return False, "Пользователь не найден."

        if user.id == admin_user.id:
            return False, "Нельзя удалить собственную учетную запись."

        if user.role == "admin":
            return False, "Удаление администратора запрещено."

        user_folder = Config.USER_STORAGE_DIR / f"user_{user.id}"
        if user_folder.exists():
            shutil.rmtree(user_folder)

        self.file_repository.delete_user_files(user.id)
        self.log_repository.delete_user_logs(user.id)
        self.user_repository.delete(user.id)
        self.log_service.add(admin_user, "delete_user", f"Удален пользователь {user.email}")
        return True, "Пользователь удален."

    def set_user_blocked(self, admin_user, user_id, is_blocked):
        user = self.user_repository.get_by_id(user_id)
        if not user:
            return False, "Пользователь не найден."

        if user.id == admin_user.id:
            return False, "Нельзя заблокировать собственную учетную запись."

        if user.role == "admin":
            return False, "Блокировка администратора запрещена."

        updated = self.user_repository.set_blocked(user.id, is_blocked)
        action = "blocked" if is_blocked else "unblocked"
        details = f"Пользователь {user.email} {'заблокирован' if is_blocked else 'разблокирован'}"
        self.log_service.add(admin_user, action, details)
        return bool(updated), "Статус пользователя обновлен."
