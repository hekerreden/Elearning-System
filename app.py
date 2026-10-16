# -*- coding: utf-8 -*-
"""
E-Learning — 3-role edition
SuperAdmin / Teacher / Student

Main entry point — lahat ng routes naka-split sa routes_*.py
"""

# ⚠️ DNS patch MUST be first — bago lahat ng imports
# Para gumana ang MongoDB Atlas sa Android
try:
    import dns_patch
except ImportError:
    pass  # Not needed on Render (Linux has proper DNS)

import os
from flask import (Flask, render_template, request, redirect,
                   url_for, session, jsonify)


# ═══════════════════════════════════════════════════════════════
# LOAD .ENV FILE
# ═══════════════════════════════════════════════════════════════
if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


# ═══════════════════════════════════════════════════════════════
# CREATE FLASK APP
# ═══════════════════════════════════════════════════════════════
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")


# ═══════════════════════════════════════════════════════════════
# CORE IMPORTS
# ═══════════════════════════════════════════════════════════════
from storage import users
from helpers import current_user, unread_count
from config import hash_password
from models import SuperAdmin


# ═══════════════════════════════════════════════════════════════
# REGISTER ROUTES
# ═══════════════════════════════════════════════════════════════
import routes_auth
import routes_dashboard
import routes_connections
import routes_profile
import routes_notifications
import routes_admin
import routes_admin_extra
import routes_studies
import routes_student_activity
import routes_quiz
import routes_attendance
import routes_misc
import routes_account

routes_account.register(app)
routes_auth.register(app)
routes_dashboard.register(app)
routes_connections.register(app)
routes_profile.register(app)
routes_notifications.register(app)
routes_admin.register(app)
routes_admin_extra.register(app)
routes_studies.register(app)
routes_student_activity.register(app)
routes_quiz.register(app)
routes_attendance.register(app)
routes_misc.register(app)


# ═══════════════════════════════════════════════════════════════
# CONTEXT PROCESSOR
# ═══════════════════════════════════════════════════════════════
@app.context_processor
def inject_globals():
    u = current_user()
    if session.get("user_id") and not u:
        session.clear()
        u = None
    return {
        "current_user_obj": u,
        "current_role": u.role if u else None,
        "current_username": u.username if u else None,
        "unread_notifications": unread_count(u.id) if u else 0,
        "force_password_change": bool(session.get("force_password_change")),
        "current_temp_password": session.get("current_temp_password") if session.get("force_password_change") else None,
    }

# ═══════════════════════════════════════════════════════════════
# BEFORE REQUEST — Force password change
# ═══════════════════════════════════════════════════════════════
@app.before_request
def enforce_password_change():
    """Force users with temp password to change it before anything else."""
    exempt = ("/login", "/logout", "/signup", "/api/account/password",
              "/api/notifications", "/static", "/system-console")
    if any(request.path.startswith(p) for p in exempt):
        return

    if session.get("force_password_change"):
        allowed = ("/teacher", "/student", "/super-admin", "/dashboard")
        if request.path not in allowed and not request.path.startswith("/profile"):
            return redirect(url_for("dashboard"))


# ═══════════════════════════════════════════════════════════════
# SEED DEFAULTS
# ═══════════════════════════════════════════════════════════════
def seed_defaults():
    """Create default SuperAdmin if none exists."""
    if not any(u.role == "SuperAdmin" for u in users):
        u = os.getenv("SUPERADMIN_USER", "admin")
        p = os.getenv("SUPERADMIN_PASS", "Admin123!")
        hashed = hash_password(p)
        users.append(SuperAdmin(
            username=u,
            full_name="System Owner",
            password_hash=hashed,
        ))
        print(f"✅ Created SuperAdmin: {u}")


# ═══════════════════════════════════════════════════════════════
# MONGODB INITIALIZATION
# ═══════════════════════════════════════════════════════════════
import db
from storage import load_from_mongo, save_to_mongo

if db.init_db():
    # Load existing data from MongoDB
    load_from_mongo()
    print("✅ Data loaded from MongoDB")

    # Seed SuperAdmin kung wala pa
    if not any(u.role == "SuperAdmin" for u in users):
        seed_defaults()
        save_to_mongo()
        print(f"✅ Seeded default SuperAdmin: {os.getenv('SUPERADMIN_USER', 'admin')}")
    else:
        print(f"ℹ️  SuperAdmin already exists ({len(users)} users total)")
else:
    # Fallback kung hindi makaka-connect
    print("⚠️  Running WITHOUT persistence — data will be lost on restart")
    seed_defaults()


# ═══════════════════════════════════════════════════════════════
# AUTO-SAVE AFTER MUTATIONS
# ═══════════════════════════════════════════════════════════════
@app.after_request
def persist_after_mutation(response):
    """Save to MongoDB after every POST request (mutations only)."""
    if request.method == "POST" and db.is_connected():
        try:
            save_to_mongo()
        except Exception as e:
            print(f"⚠️  Auto-save failed: {e}")
    return response


# ═══════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════════════════════════
@app.errorhandler(404)
def nf(e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Endpoint not found."}), 404
    return render_template("login.html"), 404


@app.errorhandler(500)
def se(e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Server error."}), 500
    return "<h1 style='color:#fff;background:#111;padding:2rem'>500 Error</h1>", 500


# ═══════════════════════════════════════════════════════════════
# RUN APP
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)