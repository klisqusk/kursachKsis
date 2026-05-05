import json
import os
import tempfile
from pathlib import Path


class JsonRepository:
    def __init__(self, file_path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._write_raw([])

    def _read_raw(self):
        if not self.file_path.exists():
            self._write_raw([])

        content = self.file_path.read_text(encoding="utf-8").strip()
        if not content:
            return []

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return []

        return data if isinstance(data, list) else []

    def _write_raw(self, data):
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.file_path.parent,
            delete=False,
        ) as temp_file:
            json.dump(data, temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
            temp_name = temp_file.name

        os.replace(temp_name, self.file_path)

    @staticmethod
    def _next_id(items):
        if not items:
            return 1
        return max(int(item.get("id", 0)) for item in items) + 1
