# -*- coding: utf-8 -*-
"""Auth decorators."""
from functools import wraps
from flask import flash, redirect, url_for, session, request, jsonify
from helpers import current_user


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            u = current_user()
            is_api = request.path.startswith("/api/")

            if not u:
                if is_api:
                    return jsonify({"ok": False, "error": "Not logged in."}), 401
                flash("Please log in first.", "error")
                return redirect(url_for("login"))

            if u.role not in roles:
                if is_api:
                    return jsonify({"ok": False, "error": "Unauthorized role."}), 403
                flash("Unauthorized access.", "error")
                return redirect(url_for("dashboard"))

            if u.status == "deleted":
                session.clear()
                if is_api:
                    return jsonify({"ok": False, "error": "Account deleted."}), 403
                flash("This account has been deleted.", "error")
                return redirect(url_for("login"))

            return fn(*a, **kw)
        return wrapper
    return decorator