from models.file_item import FileItem
from repositories.json_repository import JsonRepository


class FileRepository(JsonRepository):
    def get_all(self):
        return [FileItem.from_dict(item) for item in self._read_raw()]

    def get_by_id(self, file_id):
        if file_id is None:
            return None

        for file_item in self.get_all():
            if file_item.id == int(file_id):
                return file_item
        return None

    def get_user_file(self, user_id, file_id, include_deleted=False):
        file_item = self.get_by_id(file_id)
        if file_item and file_item.user_id == int(user_id):
            if file_item.is_deleted and not include_deleted:
                return None
            return file_item
        return None

    def get_user_files(
        self,
        user_id,
        folder=None,
        include_deleted=False,
        only_deleted=False,
        favorite_only=False,
        sort_by="name",
    ):
        user_id = int(user_id)
        files = [item for item in self.get_all() if item.user_id == user_id]
        if only_deleted:
            files = [item for item in files if item.is_deleted]
        elif not include_deleted:
            files = [item for item in files if not item.is_deleted]

        if favorite_only:
            files = [item for item in files if item.is_favorite]

        if folder is not None:
            files = [item for item in files if item.folder == folder]
        return self._sort_files(files, sort_by)

    def search_files(
        self,
        user_id,
        query,
        include_deleted=False,
        only_deleted=False,
        favorite_only=False,
        sort_by="name",
    ):
        user_id = int(user_id)
        query = (query or "").strip().lower()
        files = [
            item
            for item in self.get_all()
            if item.user_id == user_id and query in item.original_name.lower()
        ]

        if only_deleted:
            files = [item for item in files if item.is_deleted]
        elif not include_deleted:
            files = [item for item in files if not item.is_deleted]

        if favorite_only:
            files = [item for item in files if item.is_favorite]

        return self._sort_files(files, sort_by)

    def add_file(self, file_item):
        files = self._read_raw()
        if not file_item.id:
            file_item.id = self._next_id(files)
        files.append(file_item.to_dict())
        self._write_raw(files)
        return file_item

    def update_file(self, file_item):
        files = self._read_raw()
        for index, item in enumerate(files):
            if int(item["id"]) == int(file_item.id):
                files[index] = file_item.to_dict()
                self._write_raw(files)
                return file_item
        return None

    def delete_file(self, file_id):
        files = self._read_raw()
        filtered = [item for item in files if int(item["id"]) != int(file_id)]
        self._write_raw(filtered)
        return len(filtered) != len(files)

    def delete_user_files(self, user_id):
        files = self._read_raw()
        filtered = [item for item in files if int(item["user_id"]) != int(user_id)]
        self._write_raw(filtered)
        return len(files) - len(filtered)

    def _sort_files(self, files, sort_by):
        sort_by = sort_by if sort_by in {"name", "date", "size", "type"} else "name"
        sort_map = {
            "name": lambda item: item.original_name.lower(),
            "date": lambda item: item.uploaded_at,
            "size": lambda item: item.size,
            "type": lambda item: (item.category, item.original_name.lower()),
        }
        reverse = sort_by in {"date", "size"}
        return sorted(files, key=sort_map[sort_by], reverse=reverse)
