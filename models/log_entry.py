from dataclasses import asdict, dataclass


@dataclass
class LogEntry:
    id: int
    user_id: int | None
    username: str
    action: str
    details: str
    created_at: str

    @classmethod
    def from_dict(cls, data):
        user_id = data.get("user_id")
        return cls(
            id=int(data["id"]),
            user_id=int(user_id) if user_id is not None else None,
            username=data.get("username", "system"),
            action=data["action"],
            details=data.get("details", ""),
            created_at=data["created_at"],
        )

    def to_dict(self):
        return asdict(self)
