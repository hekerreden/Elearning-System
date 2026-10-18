# -*- coding: utf-8 -*-
"""Account self-service routes: edit own username."""
from flask import request, redirect, url_for, flash, jsonify
from storage import users, save_to_mongo
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
    
        # ═══════════════════════════════════════════════════════════
    # UNIFIED PROFILE UPDATE — Full Name / Username (AJAX)
    # ═══════════════════════════════════════════════════════════
    @app.route("/api/account/profile", methods=["POST"])
    @role_required("Teacher", "Student")
    def update_own_profile():
        u = current_user()
        field = (request.form.get("field") or "").strip()
        value = (request.form.get("value") or "").strip()

        wants_json = (request.headers.get("X-Requested-With") == "XMLHttpRequest"
                      or request.form.get("_ajax") == "1")

        def _err(msg, code=400):
            if wants_json:
                return jsonify({"ok": False, "error": msg}), code
            flash(msg, "error")
            return redirect(url_for(role_home(u.role)))

        # ─── FULL NAME ───
        if field == "full_name":
            if len(value) < 2:
                return _err("Full name must be at least 2 characters.")
            if len(value) > 100:
                return _err("Full name must be at most 100 characters.")

            old_name = u.full_name
            if value == old_name:
                return _err("New full name is the same as your current one.")

            u.full_name = value

            notify(u.id, "✏️ Full Name Updated",
                   f"Your full name was updated from \"{old_name}\" "
                   f"to \"{value}\".",
                   link=f"/{u.role.lower()}#account",
                   kind="info")
            
            try: save_to_mongo()
            except Exception as e: print(f"⚠️ Save failed: {e}")


            if wants_json:
                return jsonify({
                    "ok": True,
                    "message": f"Full name updated to \"{value}\".",
                    "new_full_name": value,
                })
            flash(f"Full name updated to \"{value}\".", "success")
            return redirect(url_for(role_home(u.role)))

        # ─── USERNAME ───
        if field == "username":
            import re
            if len(value) < 3:
                return _err("Username must be at least 3 characters.")
            if len(value) > 30:
                return _err("Username must be at most 30 characters.")
            if not re.match(r"^[a-zA-Z0-9_.\-]+$", value):
                return _err("Username can only contain letters, numbers, "
                            "underscore, dot, and hyphen.")

            if value.lower() == u.username.lower():
                return _err("New username is the same as your current username.")

            for other in users:
                if other.id == u.id:
                    continue
                if not other.username:
                    continue
                if other.username.lower() == value.lower():
                    return _err(f"Username '{value}' is already taken.", code=409)

            old_username = u.username
            u.username = value

            notify(u.id, "✏️ Username Changed",
                   f"Your username was updated from @{old_username} "
                   f"to @{value}.",
                   link=f"/{u.role.lower()}#account",
                   kind="info")
            
            try: save_to_mongo()
            except Exception as e: print(f"⚠️ Save failed: {e}")


            if wants_json:
                return jsonify({
                    "ok": True,
                    "message": f"Username updated to @{value}.",
                    "new_username": value,
                })
            flash(f"Username updated to @{value}.", "success")
            return redirect(url_for(role_home(u.role))+"#account")

        return _err("Unknown field.")
