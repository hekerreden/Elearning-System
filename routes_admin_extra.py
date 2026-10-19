# -*- coding: utf-8 -*-
"""Extra admin features: edit username."""
import re
from flask import request, redirect, url_for, flash
from storage import users, save_to_mongo
from helpers import find_user_by_id, notify
from decorators import role_required


USERNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.\-]{2,29}$")


def register(app):

    # ═══════════════════════════════════════════════════════════
    # EDIT USERNAME (by admin)
    # ═══════════════════════════════════════════════════════════
    @app.route("/api/admin/users/<uid>/edit-username", methods=["POST"])
    @role_required("SuperAdmin") # ✅ FIX: Tinanggal ang space sa "SuperAd min"
    def admin_edit_username(uid):
        target = find_user_by_id(uid)
        if not target:
            flash("User not found.", "error")
            return redirect(url_for("super_admin_page"))

        if target.role == "SuperAdmin":
            flash("Cannot edit SuperAdmin username.", "error")
            return redirect(url_for("super_admin_page"))

        if target.status == "deleted":
            flash("Cannot edit deleted account.", "error")
            return redirect(url_for("super_admin_page"))

        new_username = request.form.get("username", "").strip()

        # ── Presence ──
        if not new_username:
            flash("Username required.", "error")
            return redirect(url_for("super_admin_page"))

        # ── Length ──
        if len(new_username) < 3:
            flash("Username must be at least 3 characters.", "error")
            return redirect(url_for("super_admin_page"))

        if len(new_username) > 30:
            flash("Username must be at most 30 characters.", "error")
            return redirect(url_for("super_admin_page"))

        # ── Format ──
        if not USERNAME_RE.match(new_username):
            flash("Username must start with a letter/number, and contain "
                  "only letters, numbers, underscore, dot, hyphen.", "error")
            return redirect(url_for("super_admin_page"))

        # ── Same as current ──
        if new_username.lower() == target.username.lower():
            flash("New username is the same as current.", "error")
            return redirect(url_for("super_admin_page"))

        # ── Uniqueness (case-insensitive) ──
        for u in users:
            if u.id == target.id:
                continue
            if not u.username:
                continue
            if u.username.lower() == new_username.lower():
                flash(f"Username '{new_username}' is already taken.", "error")
                return redirect(url_for("super_admin_page"))

        # ── Save ──
        old_username = target.username
        target.username = new_username
        
        # ✅ FIX: Ilagay ang history BAGO mag-save
        if not hasattr(target, 'username_history') or target.username_history is None:
            target.username_history = []
        if old_username not in target.username_history:
            target.username_history.append(old_username)
            target.username_history = target.username_history[-5:] # Max 5 history
            
        # ✅ Save sa DB
        try: save_to_mongo()
        except Exception as e: print(f"⚠️ Save failed: {e}")

        # ── Audit log ──
        print(f"✏️ [AUDIT] Admin edit-username: "
              f"@{old_username} → @{new_username} (uid={target.id})")

        # ── Notify user ──
        notify(target.id, "✏️ Username Changed",
               f"Your username was changed from @{old_username} to "
               f"@{new_username} by an admin.",
               link=f"/{target.role.lower()}#account",
               kind="info")

        flash(f"✅ Username changed: @{old_username} → @{new_username}", "success")
        return redirect(url_for("super_admin_page")+"#teachers")