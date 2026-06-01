from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from config import Config
from services.file_service import FileService
from routes.decorators import login_required
from utils.formatters import format_size

files_bp = Blueprint("files", __name__)
file_service = FileService()


def _upload_request_too_large():
    content_length = request.content_length
    if not content_length:
        return False
    return content_length > Config.UPLOAD_MAX_BYTES + Config.UPLOAD_FORM_OVERHEAD_BYTES


def _redirect_to_dashboard(folder="", query=None, view="folder", sort_by="name"):
    params = {}
    if folder and view == "folder":
        params["folder"] = folder
    if view != "folder":
        params["view"] = view
    if sort_by != "name":
        params["sort"] = sort_by
    if query:
        params["q"] = query
    return redirect(url_for("files.dashboard", **params))


@files_bp.route("/dashboard")
@login_required
def dashboard():
    current_user = g.current_user
    folder = request.args.get("folder", "")
    query = request.args.get("q", "").strip()
    view = request.args.get("view", "folder")
    sort_by = request.args.get("sort", "name")
    if view not in {"folder", "favorites", "trash"}:
        view = "folder"

    try:
        normalized_folder = file_service.normalize_folder(folder)
        if query:
            files = file_service.search_files(current_user.id, query, view=view, sort_by=sort_by)
            folders = []
        else:
            files = file_service.get_files(
                current_user.id,
                normalized_folder,
                view=view,
                sort_by=sort_by,
            )
            folders = (
                file_service.list_folders(current_user.id, normalized_folder)
                if view == "folder"
                else []
            )

        return render_template(
            "dashboard.html",
            title="Личный кабинет",
            files=files,
            folders=folders,
            all_folders=file_service.list_all_folders(current_user.id),
            breadcrumbs=file_service.get_breadcrumbs(normalized_folder),
            current_folder=normalized_folder,
            query=query,
            view=view,
            sort_by=sort_by,
            storage_info=file_service.get_storage_info(current_user.id),
            summary=file_service.get_dashboard_summary(current_user.id),
        )
    except ValueError as error:
        flash(str(error), "danger")
        return _redirect_to_dashboard()


@files_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    if _upload_request_too_large():
        flash(f"Размер файла превышает лимит {format_size(Config.UPLOAD_MAX_BYTES)}.", "danger")
        return _redirect_to_dashboard()

    folder = request.form.get("folder", "")
    sort_by = request.form.get("sort", "name")
    redirect_folder = ""
    try:
        redirect_folder = file_service.normalize_folder(folder)
        success, message, _file_item = file_service.upload_file(
            g.current_user,
            request.files.get("file"),
            redirect_folder,
        )
        flash(message, "success" if success else "danger")
    except ValueError as error:
        flash(str(error), "danger")

    return _redirect_to_dashboard(redirect_folder, sort_by=sort_by)


@files_bp.route("/download/<int:file_id>")
@login_required
def download(file_id):
    file_item = file_service.get_file_info(g.current_user.id, file_id)
    if not file_item:
        flash("Файл не найден.", "danger")
        return _redirect_to_dashboard()

    file_path = file_service.get_file_path(file_item)
    if not file_path.exists():
        flash("Файл отсутствует на сервере.", "danger")
        return _redirect_to_dashboard(file_item.folder)

    return send_file(file_path, as_attachment=True, download_name=file_item.original_name)


@files_bp.route("/delete/<int:file_id>", methods=["POST"])
@login_required
def delete(file_id):
    folder = request.form.get("folder", "")
    view = request.form.get("view", "folder")
    sort_by = request.form.get("sort", "name")
    success, message = file_service.delete_file(g.current_user, file_id)
    flash(message, "success" if success else "danger")
    return _redirect_to_dashboard(folder, view=view, sort_by=sort_by)


@files_bp.route("/restore/<int:file_id>", methods=["POST"])
@login_required
def restore(file_id):
    sort_by = request.form.get("sort", "name")
    success, message = file_service.restore_file(g.current_user, file_id)
    flash(message, "success" if success else "danger")
    return _redirect_to_dashboard(view="trash", sort_by=sort_by)


@files_bp.route("/destroy/<int:file_id>", methods=["POST"])
@login_required
def destroy(file_id):
    sort_by = request.form.get("sort", "name")
    success, message = file_service.permanent_delete_file(g.current_user, file_id)
    flash(message, "success" if success else "danger")
    return _redirect_to_dashboard(view="trash", sort_by=sort_by)


@files_bp.route("/trash/empty", methods=["POST"])
@login_required
def empty_trash():
    sort_by = request.form.get("sort", "name")
    success, message = file_service.empty_trash(g.current_user)
    flash(message, "success" if success else "info")
    return _redirect_to_dashboard(view="trash", sort_by=sort_by)


@files_bp.route("/favorite/<int:file_id>", methods=["POST"])
@login_required
def favorite(file_id):
    folder = request.form.get("folder", "")
    view = request.form.get("view", "folder")
    sort_by = request.form.get("sort", "name")
    success, message = file_service.toggle_favorite(g.current_user, file_id)
    flash(message, "success" if success else "danger")
    return _redirect_to_dashboard(folder, view=view, sort_by=sort_by)


@files_bp.route("/rename/<int:file_id>", methods=["POST"])
@login_required
def rename(file_id):
    folder = request.form.get("folder", "")
    view = request.form.get("view", "folder")
    sort_by = request.form.get("sort", "name")
    new_name = request.form.get("new_name", "")
    try:
        success, message, _file_item = file_service.rename_file(g.current_user, file_id, new_name)
        flash(message, "success" if success else "danger")
    except ValueError as error:
        flash(str(error), "danger")
    return _redirect_to_dashboard(folder, view=view, sort_by=sort_by)


@files_bp.route("/move/<int:file_id>", methods=["POST"])
@login_required
def move(file_id):
    folder = request.form.get("folder", "")
    view = request.form.get("view", "folder")
    sort_by = request.form.get("sort", "name")
    target_folder = request.form.get("target_folder", "")
    try:
        success, message = file_service.move_file(g.current_user, file_id, target_folder)
        flash(message, "success" if success else "danger")
    except ValueError as error:
        flash(str(error), "danger")
    return _redirect_to_dashboard(folder, view=view, sort_by=sort_by)


@files_bp.route("/folder/create", methods=["POST"])
@login_required
def create_folder():
    current_folder = request.form.get("folder", "")
    sort_by = request.form.get("sort", "name")
    folder_name = request.form.get("folder_name", "")
    redirect_folder = ""
    try:
        redirect_folder = file_service.normalize_folder(current_folder)
        success, message, _new_folder = file_service.create_folder(
            g.current_user,
            redirect_folder,
            folder_name,
        )
        flash(message, "success" if success else "danger")
    except ValueError as error:
        flash(str(error), "danger")

    return _redirect_to_dashboard(redirect_folder, sort_by=sort_by)


@files_bp.route("/folder/delete", methods=["POST"])
@login_required
def delete_folder():
    current_folder = request.form.get("current_folder", "")
    target_folder = request.form.get("target_folder", "")
    sort_by = request.form.get("sort", "name")
    redirect_folder = ""
    try:
        redirect_folder = file_service.normalize_folder(current_folder)
        success, message = file_service.delete_folder(g.current_user, target_folder)
        flash(message, "success" if success else "danger")
    except ValueError as error:
        flash(str(error), "danger")

    return _redirect_to_dashboard(redirect_folder, sort_by=sort_by)


@files_bp.route("/search")
@login_required
def search():
    query = request.args.get("q", "").strip()
    folder = request.args.get("folder", "")
    view = request.args.get("view", "folder")
    sort_by = request.args.get("sort", "name")
    return _redirect_to_dashboard(folder=folder, query=query, view=view, sort_by=sort_by)


@files_bp.route("/file/<int:file_id>")
@login_required
def file_info(file_id):
    file_item = file_service.get_file_info(g.current_user.id, file_id, include_deleted=True)
    if not file_item:
        flash("Файл не найден.", "danger")
        return _redirect_to_dashboard()

    file_path = file_service.get_file_path(file_item)
    return render_template(
        "file_info.html",
        title="Информация о файле",
        file_item=file_item,
        file_exists=file_path.exists(),
    )
