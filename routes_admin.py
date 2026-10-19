# -*- coding: utf-8 -*-
"""Admin: delete flag, appeal, password change/reset, hard delete."""
from datetime import timedelta
from flask import (request, redirect, url_for, flash, jsonify,
                   session)
from storage import users, studies, quiz_results, attendance, connections, save_to_mongo
from helpers import (current_user, find_user_by_id, role_home,
                     notify, now_str, now_dt)
from decorators import role_required
import re

def register(app):

    # ═══════════════════════════════════════════════════════════
    # ✅ BAGONG FEATURE: ADMIN CHANGE USERNAME / FULL NAME
    # ═══════════════════════════════════════════════════════════
    @app.route("/api/admin/users/<uid>/update_profile", methods=["POST"])
    @role_required("SuperAdmin")
    def admin_update_user_profile(uid):
        admin = current_user()
        target = find_user_by_id(uid)
        if not target:
            return jsonify({"ok": False, "error": "User not found"}), 404
            
        if target.role == "SuperAdmin":
            return jsonify({"ok": False, "error": "Cannot edit another SuperAdmin."}), 403

        field = (request.form.get("field") or "").strip()
        value = (request.form.get("value") or "").strip()

        # ─── FULL NAME ───
        if field == "full_name":
            if len(value) < 2:
                return jsonify({"ok": False, "error": "Name too short."}), 400
            
            old_name = target.full_name
            target.full_name = value
            
            notify(target.id, "✏️ Full Name Updated by Admin", 
                   f"Your full name was updated to \"{value}\" by an admin.", 
                   kind="info")
            
            try: save_to_mongo()
            except: pass
            return jsonify({"ok": True, "message": f"Full name updated to {value}."})

        # ─── USERNAME ───
        elif field == "username":
            if len(value) < 3 or len(value) > 30:
                return jsonify({"ok": False, "error": "Username must be 3-30 characters."}), 400
            if not re.match(r"^[a-zA-Z0-9_.\-]+$", value):
                return jsonify({"ok": False, "error": "Invalid characters."}), 400

            for other in users:
                if other.id != target.id and other.username.lower() == value.lower():
                    return jsonify({"ok": False, "error": "Username already taken."}), 409

            old_username = target.username
            
            # ✅ I-save sa history para makapag-login pa rin gamit ang luma
            if not hasattr(target, 'username_history') or target.username_history is None:
                target.username_history = []
            target.username_history.append(old_username)
            
            target.username = value
            
            notify(target.id, "✏️ Username Changed by Admin", 
                   f"Your username was changed by an admin from @{old_username} to @{value}. You can still use your old username to log in.", 
                   kind="info")
            
            try: save_to_mongo()
            except: pass
            return jsonify({"ok": True, "message": f"Username updated to @{value}."})
            
        return jsonify({"ok": False, "error": "Unknown field"}), 400

    # ═══════════════════════════════════════════════════════════
    # EXISTING ROUTES
    # ═══════════════════════════════════════════════════════════
    @app.route("/api/admin/delete/<uid>/flag", methods=["POST"])
    @role_required("SuperAdmin")
    def admin_flag_user(uid):
        admin = current_user()
        target = find_user_by_id(uid)
        if not target:
            flash("User not found.", "error")
            return redirect(url_for("super_admin_page"))
        if target.role == "SuperAdmin":
            flash("Cannot delete Super Admin.", "error")
            return redirect(url_for("super_admin_page"))

        reason = request.form.get("reason", "").strip()
        try:
            duration = int(request.form.get("duration", "7"))
        except ValueError:
            duration = 7
        unit = request.form.get("unit", "days").strip()

        if not reason:
            flash("Reason is required.", "error")
            return redirect(url_for("super_admin_page"))
        if duration < 1:
            flash("Duration must be at least 1.", "error")
            return redirect(url_for("super_admin_page"))

        if unit == "hours":
            grace = timedelta(hours=duration)
            unit_label = f"{duration} hour(s)"
        elif unit == "months":
            grace = timedelta(days=30 * duration)
            unit_label = f"{duration} month(s)"
        else:
            grace = timedelta(days=duration)
            unit_label = f"{duration} day(s)"

        target.status = "pending_delete"
        target.delete_requested_at = now_str()
        target.delete_grace_until = (now_dt() + grace).strftime("%Y-%m-%d %H:%M")
        target.delete_reason = reason

        notify(target.id, "⚠️ Account Deletion Notice",
               f"Your account has been flagged for deletion by an admin. "
               f"Reason: {reason}. Deletion scheduled in {unit_label} "
               f"(on {target.delete_grace_until}). You may appeal.",
               link=f"/{target.role.lower()}#account",
               kind="delete_notice")
        notify(admin.id, "Deletion Scheduled",
               f"You flagged {target.full_name} (@{target.username}) for deletion in {unit_label}.",
               link="/super-admin#deletes", kind="info")
        flash(f"Deletion scheduled for {target.full_name} in {unit_label}.", "success")
        return redirect(url_for("super_admin_page")+"#deletes")

    @app.route("/api/account/appeal", methods=["POST"])
    @role_required("Teacher", "Student")
    def appeal_delete():
        u = current_user()
        message = request.form.get("message", "").strip()
        if u.status != "pending_delete":
            flash("No deletion to appeal.", "error")
            return redirect(url_for("dashboard"))
        u.status = "appealed"
        for x in users:
            if x.role == "SuperAdmin":
                notify(x.id, "📩 Appeal Received",
                       f"{u.full_name} (@{u.username}) appealed their deletion. "
                       f"Message: {message[:120]}",
                       link="/super-admin#deletes", kind="appeal")
        notify(u.id, "Appeal Submitted",
               "Your appeal has been sent to the Super Admin for review.",
               link=f"/{u.role.lower()}#account", kind="info")
        flash("Appeal submitted. Super Admin will review.", "success")
        return redirect(url_for("dashboard")+"#account")

    @app.route("/api/account/appeal/cancel", methods=["POST"])
    @role_required("Teacher", "Student")
    def cancel_delete():
        u = current_user()
        if u.status != "pending_delete":
            flash("Nothing to cancel.", "error")
            return redirect(url_for("dashboard"))
        u.status = "active"
        u.delete_requested_at = None
        u.delete_grace_until = None
        u.delete_reason = ""
        flash("Account deletion cancelled. Welcome back!", "success")
        return redirect(url_for("dashboard")+"#account")

    @app.route("/api/admin/delete/<uid>/approve", methods=["POST"])
    @role_required("SuperAdmin")
    def admin_approve_delete(uid):
        target = find_user_by_id(uid)
        if not target:
            flash("User not found.", "error")
            return redirect(url_for("super_admin_page"))
        target.status = "deleted"
        target.username = f"deleted_{target.id}"
        notify(target.id, "Account Deleted", "Your account has been deleted.", kind="info")
        flash(f"Deleted {target.full_name}.", "success")
        return redirect(url_for("super_admin_page")+"#deletes")

    @app.route("/api/admin/delete/<uid>/reject", methods=["POST"])
    @role_required("SuperAdmin")
    def admin_reject_delete(uid):
        target = find_user_by_id(uid)
        if not target:
            flash("User not found.", "error")
            return redirect(url_for("super_admin_page"))
        target.status = "active"
        target.delete_requested_at = None
        target.delete_grace_until = None
        target.delete_reason = ""
        notify(target.id, "Deletion Cancelled",
               "Super Admin rejected the deletion. Your account is active.",
               link=f"/{target.role.lower()}#account", kind="info")
        flash(f"Restored {target.full_name}.", "success")
        return redirect(url_for("super_admin_page")+"#deletes")

    @app.route("/api/users/<uid>/delete", methods=["POST"])
    @role_required("SuperAdmin")
    def admin_hard_delete(uid):
        target = find_user_by_id(uid)
        if not target:
            flash("User not found.", "error")
            return redirect(url_for("super_admin_page"))
        if target.role == "SuperAdmin":
            flash("Cannot delete Super Admin.", "error")
            return redirect(url_for("super_admin_page"))
        users.remove(target)
        studies[:] = [s for s in studies if s.get("teacher_id") != uid]
        quiz_results[:] = [r for r in quiz_results if r["student_id"] != uid]
        attendance[:] = [a for a in attendance if a["student_id"] != uid]
        connections[:] = [c for c in connections
                          if c["student_id"] != uid and c["teacher_id"] != uid]
        flash(f"User '{target.username}' permanently deleted.", "success")
        return redirect(url_for("super_admin_page")+"#delete")

    @app.route("/api/admin/users/<uid>/reset-password", methods=["POST"])
    @role_required("SuperAdmin")
    def admin_reset_user_password(uid):
        admin = current_user()
        target = find_user_by_id(uid)
        if not target:
            flash("User not found.", "error")
            return redirect(url_for("super_admin_page"))
        if target.role == "SuperAdmin":
            flash("Cannot reset SuperAdmin password this way.", "error")
            return redirect(url_for("super_admin_page"))
        if target.status == "deleted":
            flash("Cannot reset deleted account.", "error")
            return redirect(url_for("super_admin_page"))

        target.reset_with_temp()
        target.reset_by = admin.id

        notify(admin.id, "🔑 Password Reset Successful",
               f"Password reset for @{target.username} ({target.full_name}). "
               f"The user will see their temp password on the login page.",
               link="/super-admin#users", kind="reset")

        notify(target.id, "🔑 Password Reset by Admin",
               "Your password was reset. To view your new temporary password, "
               "log in using your OLD password and username.",
               link=f"/{target.role.lower()}#account", kind="reset")

        flash(f"✅ Password reset for {target.full_name}. "
              f"User must log in with old password to view temp password.",
              "success")
        return redirect(url_for("super_admin_page"))

    @app.route("/api/admin/users/<uid>/reset-password-json", methods=["POST"])
    @role_required("SuperAdmin")
    def admin_reset_password_json(uid):
        admin = current_user()
        target = find_user_by_id(uid)
        if not target:
            return jsonify({"ok": False, "error": "User not found."}), 404
        if target.role == "SuperAdmin":
            return jsonify({"ok": False, "error": "Cannot reset SuperAdmin."}), 400
        if target.status == "deleted":
            return jsonify({"ok": False, "error": "Account is deleted."}), 400

        target.reset_with_temp()
        target.reset_by = admin.id
        notify(admin.id, "🔑 Password Reset Done",
               f"Password reset for @{target.username}. "
               f"User must log in with their OLD password to view the temp password.",
               link="/super-admin#teachers", kind="reset")
        notify(target.id, "🔑 Password Reset by Admin",
               "Your password was reset. Log in with your OLD password "
               "to view your temporary password on the login page.",
               link=f"/{target.role.lower()}#account", kind="reset")
        return jsonify({
            "ok": True,
            "username": target.username,
            "full_name": target.full_name
        })