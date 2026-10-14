# -*- coding: utf-8 -*-
"""Account self-service routes: edit own username."""
from flask import request, redirect, url_for, flash, jsonify
from storage import users
from helpers import current_user, notify, role_home
from decorators import role_required


def register(app):

    # ═══════════════════════════════════════════════════════════
    # CHANGE OWN USERNAME (Teacher / Student self-service)
    # ═══════════════════════════════════════════════════════════
    @app.route("/api/account/username", methods=["POST"])
    @role_required("Teacher", "Student")
    def change_own_username():
        u = current_user()
        new_username = request.form.get("username", "").strip()

        # Detect AJAX (para hindi mag-redirect)
        wants_json = (request.headers.get("X-Requested-With") == "XMLHttpRequest"
                      or request.form.get("_ajax") == "1")

        def _err(msg):
            if wants_json:
                return jsonify({"ok": False, "error": msg}), 400
            flash(msg, "error")
            return redirect(url_for(role_home(u.role)))

        # ── Validation ──
        if not new_username:
            return _err("Username required.")

        if len(new_username) < 3:
            return _err("Username must be at least 3 characters.")

        if len(new_username) > 30:
            return _err("Username must be at most 30 characters.")

        # Allowed: letters, numbers, _ . -
        import re
        if not re.match(r"^[a-zA-Z0-9_.\-]+$", new_username):
            return _err("Username can only contain letters, numbers, "
                        "underscore, dot, and hyphen.")

        if new_username.lower() == u.username.lower():
            return _err("New username is the same as your current username.")

        # ── Uniqueness check ──
        for other in users:
            if other.id == u.id:
                continue
            if not other.username:
                continue
            if other.username.lower() == new_username.lower():
                return _err(f"Username '{new_username}' is already taken.")

        # ── Save ──
        old_username = u.username
        u.username = new_username

        # ── Notify user ──
        notify(u.id, "✏️ Username Changed",
               f"Your username was updated from @{old_username} "
               f"to @{new_username}.",
               link=f"/{u.role.lower()}#account",
               kind="info")

        if wants_json:
            return jsonify({
                "ok": True,
                "message": f"Username updated to @{new_username}",
                "new_username": new_username,
            })

        flash(f"Username updated to @{new_username}", "success")
        return redirect(url_for(role_home(u.role)))