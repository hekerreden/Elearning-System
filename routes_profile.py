# -*- coding: utf-8 -*-
"""Profile route."""
from flask import render_template, redirect, url_for, flash
from storage import users, studies, quiz_results
from helpers import (current_user, get_login_candidates, find_user_by_username, can_view_user)
from decorators import role_required  # noqa (kept for parity)


def register(app):
    @app.route("/profile/<username>")
    def profile(username):
        viewer = current_user()
        if not viewer:
            return redirect(url_for("login"))
            
        # ✅ GAMITIN ANG CANDIDATES
        candidates = get_login_candidates(username)
        target = candidates[0] if candidates else None
        
        if not target or target.status == "deleted":
            flash("User not found.", "error")
            return redirect(url_for("dashboard"))
            
        # Kung iba ang current username, i-redirect sa tamang URL
        if target.username.lower() != username.lower():
            return redirect(url_for("profile", username=target.username))

        ctx = {
            "user": viewer,
            "target": target.to_dict(viewer=viewer),
            "target_obj": target,
            "target_role": target.role,
            "is_owner": viewer.id == target.id,
            "results": [],
            "studies": [],
            "rating": {"average": 0.0, "count": 0},
        }

        if target.role == "Student":
            res = [r for r in quiz_results if r["student_id"] == target.id]
            res.sort(key=lambda r: r["timestamp"], reverse=True)
            ctx["results"] = res
        elif target.role == "Teacher":
            ctx["studies"] = [s for s in studies if s["teacher_id"] == target.id]

        return render_template("profile.html", **ctx)