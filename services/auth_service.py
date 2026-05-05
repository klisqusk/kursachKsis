from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from models.user import User


class AuthService:
    def __init__(self, user_repository):
        self.user_repository = user_repository

    def register_user(self, username, email, password, password_repeat):
        username = (username or "").strip()
        email = (email or "").strip().lower()

        if not username or not email or not password:
            return False, "Заполните все поля.", None

        if "@" not in email or "." not in email:
            return False, "Введите корректный email.", None

        if password != password_repeat:
            return False, "Пароли не совпадают.", None

        if len(password) < 6:
            return False, "Пароль должен содержать не менее 6 символов.", None

        if self.user_repository.get_by_email(email):
            return False, "Пользователь с таким email уже существует.", None

        user = User(
            id=0,
            username=username,
            email=email,
            password_hash=self.hash_password(password),
            role="user",
            created_at=self._now(),
            is_blocked=False,
        )
        return True, "Регистрация выполнена. Теперь можно войти.", self.user_repository.add(user)

    def login_user(self, email, password):
        email = (email or "").strip().lower()
        user = self.user_repository.get_by_email(email)

        if not user or not self.check_password(user.password_hash, password or ""):
            return False, "Неверный email или пароль.", None

        if user.is_blocked:
            return False, "Учетная запись заблокирована администратором.", None

        return True, "Вход выполнен.", user

    def ensure_default_admin(self):
        existing_admin = next(
            (user for user in self.user_repository.get_all() if user.role == "admin"),
            None,
        )
        if existing_admin:
            return existing_admin

        admin = User(
            id=0,
            username=Config.DEFAULT_ADMIN_USERNAME,
            email=Config.DEFAULT_ADMIN_EMAIL.lower(),
            password_hash=self.hash_password(Config.DEFAULT_ADMIN_PASSWORD),
            role="admin",
            created_at=self._now(),
            is_blocked=False,
        )
        return self.user_repository.add(admin)

    @staticmethod
    def hash_password(password):
        return generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)

    @staticmethod
    def check_password(password_hash, password):
        return check_password_hash(password_hash, password)

    @staticmethod
    def _now():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
