import os
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent
    DATA_DIR = BASE_DIR / "data"
    STORAGE_DIR = BASE_DIR / "storage"
    USER_STORAGE_DIR = STORAGE_DIR / "users"

    USERS_FILE = DATA_DIR / "users.json"
    FILES_FILE = DATA_DIR / "files.json"
    LOGS_FILE = DATA_DIR / "logs.json"

    SECRET_KEY = os.environ.get("SECRET_KEY", "cloudbox-dev-secret-key")
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024

    DEFAULT_ADMIN_USERNAME = os.environ.get("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_EMAIL = os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@cloudbox.local")
    DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "admin12345")
    USER_QUOTA_BYTES = int(os.environ.get("USER_QUOTA_BYTES", 200 * 1024 * 1024))

    @classmethod
    def init_app(cls):
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.USER_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        cls.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

        for json_file in (cls.USERS_FILE, cls.FILES_FILE, cls.LOGS_FILE):
            if not json_file.exists():
                json_file.write_text("[]\n", encoding="utf-8")
