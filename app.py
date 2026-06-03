import os

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.exceptions import RequestEntityTooLarge

from config import Config
from repositories.user_repository import UserRepository
from routes.admin_routes import admin_bp
from routes.auth_routes import auth_bp
from routes.file_routes import files_bp
from services.auth_service import AuthService
from utils.formatters import format_datetime, format_size


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    Config.init_app()

    user_repository = UserRepository(Config.USERS_FILE)
    auth_service = AuthService(user_repository)
    auth_service.ensure_default_admin()

    @app.before_request
    def load_current_user():
        user_id = session.get("user_id")
        g.current_user = user_repository.get_by_id(user_id) if user_id else None

    @app.context_processor
    def inject_current_user():
        return {
            "current_user": getattr(g, "current_user", None),
            "upload_max_bytes": Config.UPLOAD_MAX_BYTES,
        }

    @app.template_filter("filesize")
    def filesize_filter(value):
        return format_size(value)

    @app.template_filter("datetime")
    def datetime_filter(value):
        return format_datetime(value)

    @app.route("/")
    def index():
        if getattr(g, "current_user", None):
            return redirect(url_for("files.dashboard"))
        return redirect(url_for("auth.login"))

    @app.errorhandler(RequestEntityTooLarge)
    def file_too_large(error):
        message = (
            "Размер загружаемого файла превышает ограничение "
            f"{format_size(Config.UPLOAD_MAX_BYTES)}."
        )
        if getattr(g, "current_user", None):
            flash(message, "danger")
            return redirect(url_for("files.dashboard"))

        return (
            render_template(
                "error.html",
                title="Файл слишком большой",
                message=message,
            ),
            413,
        )

    @app.errorhandler(404)
    def page_not_found(error):
        return (
            render_template(
                "error.html",
                title="Страница не найдена",
                message="Запрошенная страница не существует.",
            ),
            404,
        )

    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(admin_bp)

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    app.run(debug=True, host="0.0.0.0", port=port)
