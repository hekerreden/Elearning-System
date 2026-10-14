# -*- coding: utf-8 -*-
"""Extra admin features: edit username."""
from flask import request, redirect, url_for, flash
from storage import users
from helpers import find_user_by_id, notify
from decorators import role_required


def register(app):

    # ═══════════════════════════════════════════════════════════
    # EDIT USERNAME
    # ═══════════════════════════════════════════════════════════
    @app.route("/api/admin/users/<uid>/edit-username", methods=["POST"])
    @role_required("SuperAdmin")
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

        # ── Validation ──
        if not new_username:
            flash("Username required.", "error")
            return redirect(url_for("super_admin_page"))

        if len(new_username) < 3:
            flash("Username must be at least 3 characters.", "error")
            return redirect(url_for("super_admin_page"))

        if len(new_username) > 30:
            flash("Username must be at most 30 characters.", "error")
            return redirect(url_for("super_admin_page"))

        # ── Uniqueness check (case-insensitive) ──
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

        # ── Notify user ──
        notify(target.id, "✏️ Username Changed",
               f"Your username was changed from @{old_username} to "
               f"@{new_username} by an admin.",
               link=f"/{target.role.lower()}#account",
               kind="info")

        flash(f"✅ Username changed: @{old_username} → @{new_username}", "success")
        return redirect(url_for("super_admin_page"))