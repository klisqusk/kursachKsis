from datetime import datetime

from config import Config
from models.log_entry import LogEntry
from repositories.log_repository import LogRepository


class LogService:
    def __init__(self, log_repository=None):
        self.log_repository = log_repository or LogRepository(Config.LOGS_FILE)

    def add(self, user, action, details=""):
        username = user.username if user else "system"
        user_id = user.id if user else None
        log_entry = LogEntry(
            id=0,
            user_id=user_id,
            username=username,
            action=action,
            details=details,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        return self.log_repository.add(log_entry)

    def get_all(self):
        return self.log_repository.get_all()
