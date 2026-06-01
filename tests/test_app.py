import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from config import Config


TEST_ROOT = Path(tempfile.mkdtemp(prefix="cloudbox-tests-"))
Config.DATA_DIR = TEST_ROOT / "data"
Config.STORAGE_DIR = TEST_ROOT / "storage"
Config.USER_STORAGE_DIR = Config.STORAGE_DIR / "users"
Config.USERS_FILE = Config.DATA_DIR / "users.json"
Config.FILES_FILE = Config.DATA_DIR / "files.json"
Config.LOGS_FILE = Config.DATA_DIR / "logs.json"
Config.SECRET_KEY = "test-secret"
Config.UPLOAD_MAX_BYTES = 1024
Config.UPLOAD_FORM_OVERHEAD_BYTES = 2048
Config.MAX_CONTENT_LENGTH = 10 * 1024
Config.USER_QUOTA_BYTES = 3 * 1024
Config.DEFAULT_ADMIN_USERNAME = "admin"
Config.DEFAULT_ADMIN_EMAIL = "admin@cloudbox.local"
Config.DEFAULT_ADMIN_PASSWORD = "admin12345"

from app import create_app  # noqa: E402


class CloudBoxAppTest(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    def setUp(self):
        Config.init_app()
        for json_file in (Config.USERS_FILE, Config.FILES_FILE, Config.LOGS_FILE):
            json_file.write_text("[]\n", encoding="utf-8")
        if Config.USER_STORAGE_DIR.exists():
            for path in sorted(Config.USER_STORAGE_DIR.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()

        self.app = create_app()
        self.app.config.update(TESTING=True, MAX_CONTENT_LENGTH=Config.MAX_CONTENT_LENGTH)
        self.client = self.app.test_client()
        self._register_and_login()

    def _register_and_login(self):
        self._register()
        self._login()

    def _register(
        self,
        username="Tester",
        email="tester@example.com",
        password="secret1",
        password_repeat="secret1",
    ):
        self.client.post(
            "/register",
            data={
                "username": username,
                "email": email,
                "password": password,
                "password_repeat": password_repeat,
            },
            follow_redirects=True,
        )

    def _login(self, email="tester@example.com", password="secret1", follow_redirects=True):
        return self.client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=follow_redirects,
        )

    def _upload(self, name, content, folder=""):
        return self.client.post(
            "/upload",
            data={"folder": folder, "file": (io.BytesIO(content), name)},
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    @staticmethod
    def _read_json(path):
        return json.loads(path.read_text(encoding="utf-8"))

    def _file_record(self, original_name):
        return next(
            item
            for item in self._read_json(Config.FILES_FILE)
            if item["original_name"] == original_name
        )

    def _user_record(self, email):
        return next(
            item
            for item in self._read_json(Config.USERS_FILE)
            if item["email"] == email
        )

    def test_private_pages_require_login(self):
        self.client.get("/logout")

        for url in ("/dashboard", "/admin", "/admin/users", "/admin/logs"):
            with self.subTest(url=url):
                response = self.client.get(url, follow_redirects=False)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login?next=", response.headers["Location"])

    def test_regular_user_cannot_open_admin_panel(self):
        response = self.client.get("/admin", follow_redirects=True)

        self.assertIn("Доступ разрешен только администратору.".encode(), response.data)
        self.assertIn("Файловое хранилище".encode(), response.data)

    def test_registration_rejects_duplicate_email(self):
        self.client.get("/logout")
        response = self.client.post(
            "/register",
            data={
                "username": "Another Tester",
                "email": "TESTER@example.com",
                "password": "secret2",
                "password_repeat": "secret2",
            },
            follow_redirects=True,
        )

        self.assertIn("Пользователь с таким email уже существует.".encode(), response.data)

    def test_login_rejects_wrong_password(self):
        self.client.get("/logout")
        response = self._login(password="incorrect")

        self.assertIn("Неверный email или пароль.".encode(), response.data)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_upload_is_available_in_main_views(self):
        for url in ("/dashboard", "/dashboard?view=favorites", "/dashboard?view=trash"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn(b'type="file"', response.data)
                self.assertIn("До 1.0 КБ за файл".encode(), response.data)

    def test_upload_limit_and_cleanup(self):
        response = self.client.post(
            "/upload",
            data={"file": (io.BytesIO(b"a" * 1024), "ok.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn("Файл успешно загружен.".encode(), response.data)

        response = self.client.post(
            "/upload",
            data={"file": (io.BytesIO(b"a" * 1025), "too-big.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn("Размер файла превышает лимит 1.0 КБ.".encode(), response.data)

        files = json.loads(Config.FILES_FILE.read_text(encoding="utf-8"))
        self.assertTrue(all(item["original_name"] != "too-big.txt" for item in files))
        self.assertFalse(list(Config.USER_STORAGE_DIR.rglob("*too-big.txt")))

    def test_large_upload_is_rejected_before_form_parsing(self):
        response = self.client.post(
            "/upload",
            data={"folder": "docs", "file": (io.BytesIO(b"a" * 5000), "too-big-early.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn("Размер файла превышает лимит 1.0 КБ.".encode(), response.data)
        self.assertFalse(list(Config.USER_STORAGE_DIR.rglob("*too-big-early.txt")))

        response = self.client.post(
            "/upload",
            data={"file": (io.BytesIO(b"ok"), "after-early-reject.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn("Файл успешно загружен.".encode(), response.data)
        self.assertIn(b"after-early-reject.txt", response.data)

    def test_request_too_large_returns_dashboard_message(self):
        self.app.config["MAX_CONTENT_LENGTH"] = 512
        response = self.client.post(
            "/upload",
            data={"file": (io.BytesIO(b"a" * 700), "request-too-big.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(
            "Размер загружаемого файла превышает ограничение 1.0 КБ.".encode(),
            response.data,
        )

    def test_folder_separator_is_rejected(self):
        response = self.client.post(
            "/folder/create",
            data={"folder_name": "../"},
            follow_redirects=True,
        )
        self.assertIn(
            "Имя папки не должно содержать разделители пути.".encode(),
            response.data,
        )

    def test_external_next_url_is_ignored(self):
        self.client.get("/logout")
        response = self.client.post(
            "/login?next=https://example.com/phish",
            data={"email": "tester@example.com", "password": "secret1"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/dashboard"))

    def test_relative_next_url_is_used_after_login(self):
        self.client.get("/logout")
        response = self._login(follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/dashboard"))

        self.client.get("/logout")
        response = self.client.post(
            "/login?next=/dashboard?view=favorites",
            data={"email": "tester@example.com", "password": "secret1"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/dashboard?view=favorites"))

    def test_uploaded_file_can_be_downloaded_and_inspected(self):
        response = self._upload("script.py", b"print('hello')\n")
        self.assertIn("Файл успешно загружен.".encode(), response.data)

        file_record = self._file_record("script.py")
        self.assertEqual(file_record["category"], "code")

        response = self.client.get(f"/download/{file_record['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"print('hello')\n")
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertIn("script.py", response.headers["Content-Disposition"])
        response.close()

        response = self.client.get(f"/file/{file_record['id']}")
        self.assertIn(b"script.py", response.data)
        self.assertIn(b".py", response.data)
        self.assertIn(b"code", response.data)
        self.assertIn("найден".encode(), response.data)

    def test_file_can_be_favorited_renamed_moved_and_restored(self):
        self.client.post("/folder/create", data={"folder_name": "docs"}, follow_redirects=True)
        self._upload("note.txt", b"note")
        file_record = self._file_record("note.txt")
        file_id = file_record["id"]
        original_path = Config.USER_STORAGE_DIR / "user_2" / file_record["stored_name"]

        response = self.client.post(f"/favorite/{file_id}", follow_redirects=True)
        self.assertIn("Статус избранного обновлен.".encode(), response.data)
        response = self.client.get("/dashboard?view=favorites")
        self.assertIn(b"note.txt", response.data)

        response = self.client.post(
            f"/rename/{file_id}",
            data={"new_name": "picture.png"},
            follow_redirects=True,
        )
        self.assertIn("Файл переименован.".encode(), response.data)
        file_record = self._file_record("picture.png")
        self.assertEqual(file_record["extension"], ".png")
        self.assertEqual(file_record["category"], "image")

        response = self.client.post(
            f"/move/{file_id}",
            data={"target_folder": "docs"},
            follow_redirects=True,
        )
        self.assertIn("Файл перемещен.".encode(), response.data)
        file_record = self._file_record("picture.png")
        moved_path = Config.USER_STORAGE_DIR / "user_2" / "docs" / file_record["stored_name"]
        self.assertFalse(original_path.exists())
        self.assertTrue(moved_path.exists())

        response = self.client.post(f"/delete/{file_id}", follow_redirects=True)
        self.assertIn("Файл перемещен в корзину.".encode(), response.data)
        response = self.client.get("/dashboard?view=trash")
        self.assertIn(b"picture.png", response.data)

        response = self.client.post(f"/restore/{file_id}", follow_redirects=True)
        self.assertIn("Файл восстановлен.".encode(), response.data)
        response = self.client.get("/dashboard?folder=docs")
        self.assertIn(b"picture.png", response.data)

    def test_permanent_delete_removes_file_and_metadata(self):
        self._upload("obsolete.txt", b"remove me")
        file_record = self._file_record("obsolete.txt")
        file_id = file_record["id"]
        file_path = Config.USER_STORAGE_DIR / "user_2" / file_record["stored_name"]
        self.assertTrue(file_path.exists())

        self.client.post(f"/delete/{file_id}", follow_redirects=True)
        response = self.client.post(f"/destroy/{file_id}", follow_redirects=True)

        self.assertIn("Файл удален окончательно.".encode(), response.data)
        self.assertFalse(file_path.exists())
        self.assertFalse(
            any(item["id"] == file_id for item in self._read_json(Config.FILES_FILE))
        )

    def test_user_quota_is_enforced_and_rejected_file_is_cleaned_up(self):
        for index in range(3):
            response = self._upload(f"part-{index}.txt", b"a" * 1024)
            self.assertIn("Файл успешно загружен.".encode(), response.data)

        response = self._upload("over-quota.txt", b"x")
        self.assertIn("Недостаточно места в хранилище пользователя.".encode(), response.data)
        self.assertEqual(len(self._read_json(Config.FILES_FILE)), 3)
        self.assertFalse(list(Config.USER_STORAGE_DIR.rglob("*over-quota.txt")))

    def test_user_cannot_access_another_users_file(self):
        self._upload("private.txt", b"classified")
        file_record = self._file_record("private.txt")
        file_id = file_record["id"]

        self.client.get("/logout")
        self._register("Other", "other@example.com", "secret2", "secret2")
        self._login("other@example.com", "secret2")

        for url in (f"/download/{file_id}", f"/file/{file_id}"):
            with self.subTest(url=url):
                response = self.client.get(url, follow_redirects=True)
                self.assertIn("Файл не найден.".encode(), response.data)
                self.assertNotIn(b"classified", response.data)

        response = self.client.post(f"/delete/{file_id}", follow_redirects=True)
        self.assertIn("Файл не найден.".encode(), response.data)
        self.assertEqual(self._file_record("private.txt")["user_id"], 2)

    def test_admin_can_block_unblock_and_delete_user_with_files(self):
        self._upload("owned.txt", b"content")
        tester = self._user_record("tester@example.com")

        self.client.get("/logout")
        self._login("admin@cloudbox.local", "admin12345")
        response = self.client.get("/admin/users")
        self.assertIn(b"tester@example.com", response.data)

        response = self.client.post(
            "/admin/users/block",
            data={"user_id": tester["id"], "is_blocked": "1"},
            follow_redirects=True,
        )
        self.assertIn("Статус пользователя обновлен.".encode(), response.data)

        self.client.get("/logout")
        response = self._login()
        self.assertIn("Учетная запись заблокирована администратором.".encode(), response.data)

        self._login("admin@cloudbox.local", "admin12345")
        self.client.post(
            "/admin/users/block",
            data={"user_id": tester["id"], "is_blocked": "0"},
            follow_redirects=True,
        )
        response = self.client.post(
            "/admin/users/delete",
            data={"user_id": tester["id"]},
            follow_redirects=True,
        )

        self.assertIn("Пользователь удален.".encode(), response.data)
        self.assertFalse((Config.USER_STORAGE_DIR / f"user_{tester['id']}").exists())
        self.assertFalse(
            any(item["email"] == "tester@example.com" for item in self._read_json(Config.USERS_FILE))
        )
        self.assertEqual(self._read_json(Config.FILES_FILE), [])
        self.assertFalse(
            any(item["user_id"] == tester["id"] for item in self._read_json(Config.LOGS_FILE))
        )

    def test_empty_folder_can_be_deleted(self):
        response = self.client.post(
            "/folder/create",
            data={"folder_name": "empty"},
            follow_redirects=True,
        )
        self.assertIn("Папка создана.".encode(), response.data)

        response = self.client.post(
            "/folder/delete",
            data={"current_folder": "", "target_folder": "empty"},
            follow_redirects=True,
        )
        self.assertIn("Папка удалена.".encode(), response.data)
        self.assertFalse((Config.USER_STORAGE_DIR / "user_2" / "empty").exists())

    def test_folder_with_files_is_not_deleted_until_trash_is_empty(self):
        self.client.post(
            "/folder/create",
            data={"folder_name": "docs"},
            follow_redirects=True,
        )
        self.client.post(
            "/upload",
            data={"folder": "docs", "file": (io.BytesIO(b"doc"), "doc.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        response = self.client.post(
            "/folder/delete",
            data={"current_folder": "", "target_folder": "docs"},
            follow_redirects=True,
        )
        self.assertIn("В папке есть файлы.".encode(), response.data)

        files = json.loads(Config.FILES_FILE.read_text(encoding="utf-8"))
        file_id = next(item["id"] for item in files if item["original_name"] == "doc.txt")
        self.client.post(f"/delete/{file_id}", follow_redirects=True)
        response = self.client.post(
            "/folder/delete",
            data={"current_folder": "", "target_folder": "docs"},
            follow_redirects=True,
        )
        self.assertIn("В папке есть файлы.".encode(), response.data)

        response = self.client.post("/trash/empty", follow_redirects=True)
        self.assertIn("Корзина очищена. Удалено файлов: 1.".encode(), response.data)
        self.assertEqual(json.loads(Config.FILES_FILE.read_text(encoding="utf-8")), [])

        response = self.client.post(
            "/folder/delete",
            data={"current_folder": "", "target_folder": "docs"},
            follow_redirects=True,
        )
        self.assertIn("Папка удалена.".encode(), response.data)


if __name__ == "__main__":
    unittest.main()
