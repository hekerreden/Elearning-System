# -*- coding: utf-8 -*-
"""Account self-service routes."""
from flask import request, redirect, url_for, flash, jsonify, session
from storage import users, save_to_mongo
from helpers import current_user, notify, role_home
from decorators import role_required
import re

def register(app):

    # ═══════════════════════════════════════════════════════════
    # 1. CHANGE PASSWORD (Para sa Temp Password at Manual Change)
    # ═══════════════════════════════════════════════════════════
    @app.route("/api/account/password", methods=["POST"])
    @role_required("Teacher", "Student", "SuperAdmin")
    def change_password():
        u = current_user()
        # ✅ FIX: Ginamit ang "current", "new", "confirm" base sa base.html mo
        current_password = request.form.get("current", "")
        new_password = request.form.get("new", "")
        confirm_password = request.form.get("confirm", "")

        wants_json = (request.headers.get("X-Requested-With") == "XMLHttpRequest"
                      or request.form.get("_ajax") == "1")

        def _err(msg):
            if wants_json: return jsonify({"ok": False, "error": msg}), 400
            flash(msg, "error")
            return redirect(url_for(role_home(u.role)) + "#account")

        if not u.check_password(current_password):
            return _err("Current password is incorrect.")

        if len(new_password) < 8:
            return _err("New password must be at least 8 characters.")
        if new_password != confirm_password:
            return _err("Passwords do not match.")
        if new_password == current_password:
            return _err("New password must be different from current.")

        u.set_password(new_password)
        u.finalize_password_change() 
        
        session.pop("force_password_change", None)
        session.pop("current_temp_password", None)

        try: save_to_mongo()
        except Exception as e: print(f"⚠️ Save failed: {e}")

        notify(u.id, "🔒 Password Changed", "Your password has been successfully updated.", kind="security")

        if wants_json:
            return jsonify({"ok": True, "message": "Password updated successfully!"})

        flash("Password updated successfully!", "success")
        return redirect(url_for(role_home(u.role)) + "#account")


    # ═══════════════════════════════════════════════════════════
    # 2. UPDATE USERNAME & FULL NAME (May History Tracking)
    # ═══════════════════════════════════════════════════════════
    @app.route("/api/account/profile", methods=["POST"])
    @role_required("Teacher", "Student", "SuperAdmin")
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
            return redirect(url_for(role_home(u.role)) + "#account")

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
            notify(u.id, "✏️ Full Name Updated", f"Your name was updated from \"{old_name}\" to \"{value}\".", kind="info")
            
            try: save_to_mongo()
            except Exception as e: print(f"⚠️ Save failed: {e}")

            if wants_json:
                return jsonify({"ok": True, "message": f"Full name updated to \"{value}\"."})
            flash(f"Full name updated to \"{value}\".", "success")
            return redirect(url_for(role_home(u.role)) + "#account")

        # ─── USERNAME ───
        if field == "username":
            if len(value) < 3:
                return _err("Username must be at least 3 characters.")
            if len(value) > 30:
                return _err("Username must be at most 30 characters.")
            if not re.match(r"^[a-zA-Z0-9_.\-]+$", value):
                return _err("Username can only contain letters, numbers, underscore, dot, and hyphen.")

            if value.lower() == u.username.lower():
                return _err("New username is the same as your current username.")

            if hasattr(u, 'username_history') and u.username_history:
                for old_u in u.username_history:
                    if old_u.lower() == value.lower():
                        return _err("You cannot reuse a previous username.")

            for other in users:
                if other.id == u.id: continue
                if other.username and other.username.lower() == value.lower():
                    return _err(f"Username '{value}' is already taken.", code=409)

            old_username = u.username
            if not hasattr(u, 'username_history') or u.username_history is None:
                u.username_history = []
            u.username_history.append(old_username)
            
            u.username = value
            notify(u.id, "✏️ Username Changed", f"Your username was updated from @{old_username} to @{value}.", kind="info")
            
            try: save_to_mongo()
            except Exception as e: print(f"⚠️ Save failed: {e}")

            if wants_json:
                return jsonify({"ok": True, "message": f"Username updated to @{value}."})
            flash(f"Username updated to @{value}.", "success")
            return redirect(url_for(role_home(u.role)) + "#account")

        return _err("Unknown field.")