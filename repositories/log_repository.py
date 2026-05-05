from models.log_entry import LogEntry
from repositories.json_repository import JsonRepository


class LogRepository(JsonRepository):
    def get_all(self):
        logs = [LogEntry.from_dict(item) for item in self._read_raw()]
        return sorted(logs, key=lambda item: item.id, reverse=True)

    def add(self, log_entry):
        logs = self._read_raw()
        if not log_entry.id:
            log_entry.id = self._next_id(logs)
        logs.append(log_entry.to_dict())
        self._write_raw(logs)
        return log_entry

    def delete_user_logs(self, user_id):
        logs = self._read_raw()
        filtered = [
            item
            for item in logs
            if item.get("user_id") is None or int(item["user_id"]) != int(user_id)
        ]
        self._write_raw(filtered)
