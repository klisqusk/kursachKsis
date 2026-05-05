from dataclasses import asdict, dataclass


@dataclass
class User:
    id: int
    username: str
    email: str
    password_hash: str
    role: str
    created_at: str
    is_blocked: bool = False

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=int(data["id"]),
            username=data["username"],
            email=data["email"],
            password_hash=data["password_hash"],
            role=data.get("role", "user"),
            created_at=data["created_at"],
            is_blocked=bool(data.get("is_blocked", False)),
        )

    def to_dict(self):
        return asdict(self)

    @property
    def is_admin(self):
        return self.role == "admin"
