from dataclasses import asdict, dataclass


@dataclass
class FileItem:
    id: int
    user_id: int
    original_name: str
    stored_name: str
    folder: str
    size: int
    extension: str
    uploaded_at: str
    category: str = "other"
    is_favorite: bool = False
    is_deleted: bool = False
    deleted_at: str | None = None

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=int(data["id"]),
            user_id=int(data["user_id"]),
            original_name=data["original_name"],
            stored_name=data["stored_name"],
            folder=data.get("folder", ""),
            size=int(data.get("size", 0)),
            extension=data.get("extension", ""),
            uploaded_at=data["uploaded_at"],
            category=data.get("category", "other"),
            is_favorite=bool(data.get("is_favorite", False)),
            is_deleted=bool(data.get("is_deleted", False)),
            deleted_at=data.get("deleted_at"),
        )

    def to_dict(self):
        return asdict(self)
