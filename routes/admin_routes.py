from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from routes.decorators import admin_required
from services.admin_service import AdminService

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
admin_service = AdminService()


@admin_bp.route("")
@admin_required
def dashboard():
    return render_template(
        "admin.html",
        title="Админ-панель",
        statistics=admin_service.get_statistics(),
        recent_logs=admin_service.get_logs()[:8],
    )


@admin_bp.route("/users")
@admin_required
def users():
    return render_template(
        "admin_users.html",
        title="Пользователи",
        users=admin_service.get_users(),
    )


@admin_bp.route("/users/delete", methods=["POST"])
@admin_required
def delete_user():
    user_id = request.form.get("user_id")
    success, message = admin_service.delete_user(g.current_user, user_id)
    flash(message, "success" if success else "danger")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/block", methods=["POST"])
@admin_required
def block_user():
    user_id = request.form.get("user_id")
    is_blocked = request.form.get("is_blocked") == "1"
    success, message = admin_service.set_user_blocked(g.current_user, user_id, is_blocked)
    flash(message, "success" if success else "danger")
    return redirect(url_for("admin.users"))


@admin_bp.route("/statistics")
@admin_required
def statistics():
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/logs")
@admin_required
def logs():
    return render_template(
        "admin_logs.html",
        title="Журнал действий",
        logs=admin_service.get_logs(),
    )
