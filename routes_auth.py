# -*- coding: utf-8 -*-
"""Auth routes: login, signup, logout, dashboard, system-console."""
import re
from flask import render_template, request, redirect, url_for, session, flash
from storage import users
from helpers import find_user_by_username, find_user_by_id, notify
from helpers import current_user, get_login_candidates
from models import SuperAdmin, Teacher, Student


USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]{3,30}$")


def register(app):

    @app.route("/") 
    def index():
        if current_user():
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            if not username or not password:
                flash("Username and password required.", "error")
                return redirect(url_for("login"))

            # ✅ 1. HANAPIN SA LAHAT NG CANDIDATES
            candidates = get_login_candidates(username)
            user = None
            for c in candidates:
                if c.check_password(password):
                    user = c
                    break

            # ✅ 2. KUNG WALANG MATCH SA PASSWORD
            if not user:
                flash("Invalid username or password.", "error")
                return redirect(url_for("login"))

            # ✅ 3. I-CHECK KUNG LUMA ANG USERNAME
            used_old_username = (user.username.lower() != username.lower())

            # Check temp password
            if user and user.reset_pending:
                if user.check_old_password(password):
                    return render_template(
                        "login.html",
                        show_temp=True,
                        temp_password=user.temp_password,
                        temp_username=user.username,
                        temp_full_name=user.full_name,
                    )
                if password == user.temp_password:
                    if user.status == "deleted":
                        flash("This account has been deleted.", "error")
                        return redirect(url_for("login"))
                    session.clear()
                    session["user_id"] = user.id
                    session["role"] = user.role
                    session["force_password_change"] = True
                    session["current_temp_password"] = password
                    flash(
                        "🔓 Logged in with temporary password. "
                        "Please change it in Account Settings.",
                        "warning"
                    )
                    return redirect(url_for("dashboard"))
                flash("Invalid username or password.", "error")
                return redirect(url_for("login"))

            # Check deleted status bago lahat
            if user.status == "deleted":
                flash("This account has been deleted.", "error")
                return redirect(url_for("login"))

            if user.role == "SuperAdmin":
                flash("This account must use the system console.", "error")
                return redirect(url_for("login"))

            if user.role not in ("Teacher", "Student"):
                flash("Invalid account role.", "error")
                return redirect(url_for("login"))

            # Session regeneration (anti-fixation)
            session.clear()
            session["user_id"] = user.id
            session["role"] = user.role
            
            # ✅ 4. MAG-FLASH NG WARNING KUNG LUMA ANG USERNAME
            if used_old_username:
                flash(f"👋 Welcome back! Your username was recently changed. Please use <b>@{user.username}</b> next time.", "warning")
            else:
                flash(f"Welcome back, {user.full_name}!", "success")

            return redirect(url_for("dashboard"))

        return render_template("login.html")

    @app.route("/system-console", methods=["GET", "POST"])
    def super_admin_login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            if not username or not password:
                flash("Username and password required.", "error")
                return redirect(url_for("super_admin_login"))

            user = find_user_by_username(username)
            if not user or not user.check_password(password):
                flash("Invalid credentials.", "error")
                return redirect(url_for("super_admin_login"))

            if user.status == "deleted":
                flash("This account has been deleted.", "error")
                return redirect(url_for("super_admin_login"))

            if user.role != "SuperAdmin":
                flash("Access denied.", "error")
                return redirect(url_for("super_admin_login"))

            session.clear()
            session["user_id"] = user.id
            session["role"] = user.role
            flash(f"Welcome, {user.full_name}.", "success")
            return redirect(url_for("super_admin_page"))

        return render_template("super_admin_login.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "GET":
            form_data = session.pop("signup_form", {})
            return render_template("signup.html", form_data=form_data)

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        full_name = request.form.get("full_name", "").strip()
        confirm = request.form.get("password_confirm", "")

        def _signup_error(msg):
            flash(msg, "error")
            session["signup_form"] = {
                "username": username,
                "full_name": full_name,
                "role": role,
            }
            return redirect(url_for("signup"))

        # Field presence
        if not username or not password or not role:
            return _signup_error("All fields required.")

        # Username format validation
        if not USERNAME_RE.match(username):
            return _signup_error(
                "Username must be 3-30 characters: letters, numbers, "
                "underscore, dot, hyphen only."
            )

        # Full name validation
        if len(full_name) < 2:
            return _signup_error("Full name is too short (min 2 characters).")
        if len(full_name) > 100:
            return _signup_error("Full name is too long (max 100 characters).")

        # Role validation
        if role not in ("Teacher", "Student"):
            return _signup_error("Invalid role.")

        # Uniqueness
        if find_user_by_username(username):
            return _signup_error("Username taken. Try another.")

        # Password strength
        if len(password) < 8:
            return _signup_error("Password must be at least 8 characters.")
        if not re.search(r"[A-Za-z]", password):
            return _signup_error("Password must contain at least one letter.")
        if not re.search(r"[0-9]", password):
            return _signup_error("Password must contain at least one number.")

        if not confirm:
            return _signup_error("Please confirm your password.")
        if password != confirm:
            return _signup_error("Passwords do not match.")

        if role == "Teacher":
            new_user = Teacher(username, password, full_name)
        else:
            new_user = Student(username, password, full_name)

        users.append(new_user)
        session.pop("signup_form", None)

        notify(new_user.id, "🎉 Welcome!",
               f"Your account ID is {new_user.id}. "
               f"Share this ID with students/teachers to connect.",
               link=f"/{new_user.role.lower()}#account",
               kind="info")

        session.clear()
        session["user_id"] = new_user.id
        session["role"] = new_user.role

        flash(f"Welcome, {new_user.full_name}! Your ID is {new_user.id}.",
              "success")
        return redirect(url_for("dashboard"))

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Logged out.", "success")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    def dashboard():
        u = current_user()
        if not u:
            return redirect(url_for("login"))
        if u.status == "deleted":
            session.clear()
            flash("This account has been deleted.", "error")
            return redirect(url_for("login"))
        t = u.dash()
        if t == "super_admin.html":
            return redirect(url_for("super_admin_page"))
        if t == "teacher.html":
            return redirect(url_for("teacher_page"))
        if t == "student.html":
            return redirect(url_for("student_page"))
        return redirect(url_for("login"))