import shutil
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath

from werkzeug.utils import secure_filename

from config import Config
from models.file_item import FileItem
from repositories.file_repository import FileRepository
from services.log_service import LogService
from utils.formatters import format_size


class FileService:
    FORBIDDEN_NAME_CHARS = set('<>:"\\|?*\0')
    CATEGORY_EXTENSIONS = {
        "document": {
            ".txt",
            ".pdf",
            ".doc",
            ".docx",
            ".odt",
            ".rtf",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".csv",
        },
        "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"},
        "archive": {".zip", ".rar", ".7z", ".tar", ".gz"},
        "code": {".py", ".js", ".html", ".css", ".json", ".xml", ".java", ".cpp", ".c"},
        "media": {".mp3", ".wav", ".mp4", ".mov", ".avi", ".mkv"},
    }

    def __init__(self, file_repository=None, log_service=None):
        self.file_repository = file_repository or FileRepository(Config.FILES_FILE)
        self.log_service = log_service or LogService()

    def get_files(self, user_id, folder="", view="folder", sort_by="name"):
        folder = self.normalize_folder(folder)
        if view == "trash":
            return self.file_repository.get_user_files(
                user_id,
                folder=None,
                only_deleted=True,
                sort_by=sort_by,
            )
        if view == "favorites":
            return self.file_repository.get_user_files(
                user_id,
                folder=None,
                favorite_only=True,
                sort_by=sort_by,
            )
        return self.file_repository.get_user_files(user_id, folder, sort_by=sort_by)

    def search_files(self, user_id, query, view="folder", sort_by="name"):
        if view == "trash":
            return self.file_repository.search_files(
                user_id,
                query,
                only_deleted=True,
                sort_by=sort_by,
            )
        if view == "favorites":
            return self.file_repository.search_files(
                user_id,
                query,
                favorite_only=True,
                sort_by=sort_by,
            )
        return self.file_repository.search_files(user_id, query, sort_by=sort_by)

    def get_storage_info(self, user_id):
        stored_files = self.file_repository.get_user_files(
            user_id,
            folder=None,
            include_deleted=True,
        )
        used = sum(file_item.size for file_item in stored_files)
        quota = Config.USER_QUOTA_BYTES
        percent = round((used / quota) * 100, 1) if quota else 0
        return {
            "used": used,
            "quota": quota,
            "available": max(quota - used, 0),
            "percent": min(percent, 100),
        }

    def get_dashboard_summary(self, user_id):
        active_files = self.file_repository.get_user_files(user_id, folder=None)
        deleted_files = self.file_repository.get_user_files(
            user_id,
            folder=None,
            only_deleted=True,
        )
        favorite_files = [file_item for file_item in active_files if file_item.is_favorite]
        return {
            "active_files_count": len(active_files),
            "favorite_files_count": len(favorite_files),
            "trash_files_count": len(deleted_files),
            "total_size": sum(file_item.size for file_item in active_files),
        }

    def list_folders(self, user_id, folder=""):
        current_path = self._folder_path(user_id, folder)
        if not current_path.exists():
            return []

        folders = []
        for item in current_path.iterdir():
            if item.is_dir():
                relative_folder = self._relative_folder(user_id, item)
                folders.append(
                    {
                        "name": item.name,
                        "path": relative_folder,
                    }
                )
        return sorted(folders, key=lambda item: item["name"].lower())

    def list_all_folders(self, user_id):
        root = self._user_root(user_id)
        root.mkdir(parents=True, exist_ok=True)

        result = [{"name": "Главная папка", "path": ""}]
        for path in sorted([item for item in root.rglob("*") if item.is_dir()]):
            relative_folder = self._relative_folder(user_id, path)
            result.append(
                {
                    "name": relative_folder,
                    "path": relative_folder,
                }
            )
        return result

    def upload_file(self, user, uploaded_file, folder=""):
        folder = self.normalize_folder(folder)
        if not uploaded_file or not uploaded_file.filename:
            return False, "Выберите файл для загрузки.", None

        original_name = self.clean_file_name(uploaded_file.filename)
        stored_base_name = secure_filename(original_name) or "file"
        stored_name = f"{uuid.uuid4().hex}_{stored_base_name}"

        target_folder = self._folder_path(user.id, folder)
        target_folder.mkdir(parents=True, exist_ok=True)
        target_path = target_folder / stored_name
        uploaded_file.save(target_path)
        file_size = target_path.stat().st_size
        if file_size > Config.UPLOAD_MAX_BYTES:
            target_path.unlink(missing_ok=True)
            return (
                False,
                f"Размер файла превышает лимит {format_size(Config.UPLOAD_MAX_BYTES)}.",
                None,
            )

        storage_info = self.get_storage_info(user.id)
        if storage_info["used"] + file_size > storage_info["quota"]:
            target_path.unlink(missing_ok=True)
            return False, "Недостаточно места в хранилище пользователя.", None

        extension = Path(original_name).suffix.lower()

        file_item = FileItem(
            id=0,
            user_id=user.id,
            original_name=original_name,
            stored_name=stored_name,
            folder=folder,
            size=file_size,
            extension=extension,
            uploaded_at=self._now(),
            category=self._category_by_extension(extension),
        )
        saved_file = self.file_repository.add_file(file_item)
        self.log_service.add(user, "upload", f"Загружен файл {original_name}")
        return True, "Файл успешно загружен.", saved_file

    def create_folder(self, user, current_folder, folder_name):
        current_folder = self.normalize_folder(current_folder)
        folder_name = self.clean_path_part(folder_name)

        new_folder = "/".join(part for part in (current_folder, folder_name) if part)
        path = self._folder_path(user.id, new_folder)
        if path.exists():
            return False, "Папка с таким именем уже существует.", new_folder

        path.mkdir(parents=True, exist_ok=False)
        self.log_service.add(user, "create_folder", f"Создана папка {new_folder}")
        return True, "Папка создана.", new_folder

    def delete_folder(self, user, folder):
        folder = self.normalize_folder(folder)
        if not folder:
            return False, "Главную папку удалить нельзя."

        path = self._folder_path(user.id, folder)
        if not path.exists() or not path.is_dir():
            return False, "Папка не найдена."

        if self._folder_has_files(user.id, folder):
            return False, "В папке есть файлы. Сначала удалите их или очистите корзину."

        if any(path.iterdir()):
            return False, "Папка не пуста."

        path.rmdir()
        self.log_service.add(user, "delete_folder", f"Удалена папка {folder}")
        return True, "Папка удалена."

    def get_file_info(self, user_id, file_id, include_deleted=False):
        return self.file_repository.get_user_file(user_id, file_id, include_deleted=include_deleted)

    def get_file_path(self, file_item):
        return self._folder_path(file_item.user_id, file_item.folder) / file_item.stored_name

    def delete_file(self, user, file_id):
        file_item = self.file_repository.get_user_file(user.id, file_id)
        if not file_item:
            return False, "Файл не найден."

        file_item.is_deleted = True
        file_item.deleted_at = self._now()
        self.file_repository.update_file(file_item)
        self.log_service.add(user, "delete", f"Файл {file_item.original_name} перемещен в корзину")
        return True, "Файл перемещен в корзину."

    def restore_file(self, user, file_id):
        file_item = self.file_repository.get_user_file(user.id, file_id, include_deleted=True)
        if not file_item or not file_item.is_deleted:
            return False, "Файл не найден в корзине."

        file_item.is_deleted = False
        file_item.deleted_at = None
        self.file_repository.update_file(file_item)
        self.log_service.add(user, "restore", f"Восстановлен файл {file_item.original_name}")
        return True, "Файл восстановлен."

    def permanent_delete_file(self, user, file_id):
        file_item = self.file_repository.get_user_file(user.id, file_id, include_deleted=True)
        if not file_item:
            return False, "Файл не найден."

        file_path = self.get_file_path(file_item)
        if file_path.exists():
            file_path.unlink()

        self.file_repository.delete_file(file_item.id)
        self.log_service.add(user, "destroy", f"Файл {file_item.original_name} удален окончательно")
        return True, "Файл удален окончательно."

    def empty_trash(self, user):
        deleted_files = self.file_repository.get_user_files(
            user.id,
            folder=None,
            only_deleted=True,
        )
        if not deleted_files:
            return False, "Корзина уже пуста."

        for file_item in deleted_files:
            file_path = self.get_file_path(file_item)
            if file_path.exists():
                file_path.unlink()
            self.file_repository.delete_file(file_item.id)

        self.log_service.add(user, "empty_trash", f"Очищена корзина: {len(deleted_files)} файлов")
        return True, f"Корзина очищена. Удалено файлов: {len(deleted_files)}."

    def toggle_favorite(self, user, file_id):
        file_item = self.file_repository.get_user_file(user.id, file_id)
        if not file_item:
            return False, "Файл не найден."

        file_item.is_favorite = not file_item.is_favorite
        self.file_repository.update_file(file_item)
        action = "добавлен в избранное" if file_item.is_favorite else "убран из избранного"
        self.log_service.add(user, "favorite", f"Файл {file_item.original_name} {action}")
        return True, "Статус избранного обновлен."

    def rename_file(self, user, file_id, new_name):
        file_item = self.file_repository.get_user_file(user.id, file_id)
        if not file_item:
            return False, "Файл не найден.", None

        new_name = self.clean_file_name(new_name)
        file_item.original_name = new_name
        file_item.extension = Path(new_name).suffix.lower()
        file_item.category = self._category_by_extension(file_item.extension)
        self.file_repository.update_file(file_item)
        self.log_service.add(user, "rename", f"Файл переименован в {new_name}")
        return True, "Файл переименован.", file_item

    def move_file(self, user, file_id, target_folder):
        file_item = self.file_repository.get_user_file(user.id, file_id)
        if not file_item:
            return False, "Файл не найден."

        target_folder = self.normalize_folder(target_folder)
        old_path = self.get_file_path(file_item)
        new_folder_path = self._folder_path(user.id, target_folder)
        new_folder_path.mkdir(parents=True, exist_ok=True)
        new_path = new_folder_path / file_item.stored_name

        if old_path.exists() and old_path != new_path:
            shutil.move(str(old_path), str(new_path))

        file_item.folder = target_folder
        self.file_repository.update_file(file_item)
        destination = target_folder or "главную папку"
        self.log_service.add(user, "move", f"Файл {file_item.original_name} перемещен в {destination}")
        return True, "Файл перемещен."

    def get_breadcrumbs(self, folder):
        folder = self.normalize_folder(folder)
        breadcrumbs = [{"name": "Главная", "path": ""}]
        current = []

        for part in folder.split("/"):
            if not part:
                continue
            current.append(part)
            breadcrumbs.append({"name": part, "path": "/".join(current)})

        return breadcrumbs

    def normalize_folder(self, folder):
        folder = (folder or "").replace("\\", "/").strip("/")
        if not folder:
            return ""

        parts = []
        for part in PurePosixPath(folder).parts:
            if part in ("", ".", ".."):
                raise ValueError("Некорректный путь к папке.")
            parts.append(self.clean_path_part(part))
        return "/".join(parts)

    def clean_path_part(self, value):
        value = (value or "").strip()
        if "/" in value or "\\" in value:
            raise ValueError("Имя папки не должно содержать разделители пути.")

        cleaned = "".join(
            char
            for char in value
            if char not in self.FORBIDDEN_NAME_CHARS and char.isprintable()
        )
        cleaned = cleaned.strip().strip(".")
        if not cleaned:
            raise ValueError("Имя папки не может быть пустым.")
        return cleaned[:120]

    def clean_file_name(self, value):
        value = Path(value or "").name.strip()
        cleaned = "".join(
            char
            for char in value
            if char not in self.FORBIDDEN_NAME_CHARS and char.isprintable()
        )
        cleaned = cleaned.strip().strip(".")
        if not cleaned:
            raise ValueError("Имя файла не может быть пустым.")
        return cleaned[:160]

    def _user_root(self, user_id):
        root = Config.USER_STORAGE_DIR / f"user_{int(user_id)}"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _folder_path(self, user_id, folder=""):
        folder = self.normalize_folder(folder)
        root = self._user_root(user_id)
        target = root.joinpath(*folder.split("/")) if folder else root
        resolved_root = root.resolve()
        resolved_target = target.resolve()
        try:
            resolved_target.relative_to(resolved_root)
        except ValueError as error:
            raise ValueError("Путь выходит за пределы хранилища пользователя.") from error
        return target

    def _relative_folder(self, user_id, path):
        root = self._user_root(user_id)
        return path.relative_to(root).as_posix()

    def _folder_has_files(self, user_id, folder):
        folder = self.normalize_folder(folder)
        prefix = f"{folder}/"
        files = self.file_repository.get_user_files(
            user_id,
            folder=None,
            include_deleted=True,
        )
        return any(
            file_item.folder == folder or file_item.folder.startswith(prefix)
            for file_item in files
        )

    @staticmethod
    def _now():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _category_by_extension(self, extension):
        extension = (extension or "").lower()
        for category, extensions in self.CATEGORY_EXTENSIONS.items():
            if extension in extensions:
                return category
        return "other"
