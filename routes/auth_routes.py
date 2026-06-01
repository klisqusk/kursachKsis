from urllib.parse import urlsplit

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from config import Config
from repositories.user_repository import UserRepository
from services.auth_service import AuthService
from services.log_service import LogService

auth_bp = Blueprint("auth", __name__)

user_repository = UserRepository(Config.USERS_FILE)
auth_service = AuthService(user_repository)
log_service = LogService()


def _safe_next_url(next_url):
    if not next_url:
        return None

    parsed = urlsplit(next_url)
    if parsed.scheme or parsed.netloc:
        return None
    if not next_url.startswith("/") or next_url.startswith("//"):
        return None
    return next_url


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if getattr(g, "current_user", None):
        return redirect(url_for("files.dashboard"))

    if request.method == "POST":
        success, message, user = auth_service.register_user(
            request.form.get("username"),
            request.form.get("email"),
            request.form.get("password"),
            request.form.get("password_repeat"),
        )
        flash(message, "success" if success else "danger")
        if success:
            log_service.add(user, "register", "Зарегистрирован новый пользователь")
            return redirect(url_for("auth.login"))

    return render_template("register.html", title="Регистрация")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if getattr(g, "current_user", None):
        return redirect(url_for("files.dashboard"))

    if request.method == "POST":
        success, message, user = auth_service.login_user(
            request.form.get("email"),
            request.form.get("password"),
        )
        flash(message, "success" if success else "danger")
        if success:
            session.clear()
            session["user_id"] = user.id
            log_service.add(user, "login", "Пользователь вошел в систему")
            next_url = _safe_next_url(request.args.get("next"))
            return redirect(next_url or url_for("files.dashboard"))

    return render_template("login.html", title="Вход")


@auth_bp.route("/logout")
def logout():
    current_user = getattr(g, "current_user", None)
    if current_user:
        log_service.add(current_user, "logout", "Пользователь вышел из системы")
    session.clear()
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("auth.login"))
