from functools import wraps

from flask import flash, g, redirect, request, url_for


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not getattr(g, "current_user", None):
            flash("Сначала войдите в систему.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        current_user = getattr(g, "current_user", None)
        if not current_user:
            flash("Сначала войдите в систему.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        if not current_user.is_admin:
            flash("Доступ разрешен только администратору.", "danger")
            return redirect(url_for("files.dashboard"))
        return view(*args, **kwargs)

    return wrapped_view
