# -*- coding: utf-8 -*-
"""Auth routes: login, signup, logout, dashboard, system-console."""
import re
from flask import render_template, request, redirect, url_for, session, flash
from storage import users, save_to_mongo
from helpers import (find_user_by_username, find_user_by_id, notify, 
                     get_login_candidates, role_home, current_user)
from models import SuperAdmin, Teacher, Student

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]{3,30}$")


def register(app):

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username_input = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            # 1. Hanapin ang user (kasama ang mga lumang username sa history)
            candidates = get_login_candidates(username_input)
            
            if not candidates:
                flash("Invalid username or password.", "error")
                return render_template("login.html")

            # 2. Kunin ang tamang user object
            user = candidates[0]

            # 3. CHECK KUNG TAMA ANG PASSWORD (Current o Temp)
            if user.check_password(password):
                # ✅ FIX: I-clear ang session bago mag-set ng bagong user (Security)
                session.clear()
                session["user_id"] = user.id
                
                # Check kung temp password pa lang ang gamit
                if getattr(user, "reset_pending", False):
                    session["force_password_change"] = True
                    session["current_temp_password"] = user.temp_password
                    return redirect(url_for("dashboard"))
                
                # Check kung lumang username ang ginamit
                if user.username.lower() != username_input.lower():
                    flash(f"Welcome back! Note: You logged in using an old username. Your current username is @{user.username}.", "info")

                return redirect(url_for("dashboard"))

            # 4. CHECK KUNG LUMANG PASSWORD ANG TINYPE
            elif user.check_old_password(password) and getattr(user, "temp_password", None):
                # ✅ NAG-RESET SI ADMIN: Ipakita ang modal
                return render_template(
                    "login.html",
                    show_temp=True,
                    temp_username=user.username,
                    temp_password=user.temp_password,
                    temp_full_name=user.full_name
                )

            # 5. MALI TALAGA
            else:
                flash("Invalid username or password.", "error")
                return render_template("login.html")

        # GET Request
        return render_template("login.html")
        
    @app.route("/system-console", methods=["GET", "POST"])
    def super_admin_login():
        if request.method == "POST":
            username_input = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            if not username_input or not password:
                flash("Username and password required.", "error")
                return redirect(url_for("super_admin_login"))

            # ✅ FIX: Gamitin ang get_login_candidates para suportahan ang lumang username
            candidates = get_login_candidates(username_input)
            if not candidates:
                flash("Invalid credentials.", "error")
                return redirect(url_for("super_admin_login"))

            user = candidates[0]

            if user.role != "SuperAdmin":
                flash("Access denied.", "error")
                return redirect(url_for("super_admin_login"))

            if user.status == "deleted":
                flash("This account has been deleted.", "error")
                return redirect(url_for("super_admin_login"))

            # ✅ CHECK CURRENT OR TEMP PASSWORD
            if user.check_password(password):
                session.clear()
                session["user_id"] = user.id
                session["role"] = user.role
                
                # Check kung temp password (kung may nag-reset ng SuperAdmin password)
                if getattr(user, "reset_pending", False):
                    session["force_password_change"] = True
                    session["current_temp_password"] = user.temp_password

                flash(f"Welcome, {user.full_name}.", "success")
                return redirect(url_for("super_admin_page"))

            # ✅ CHECK KUNG LUMANG PASSWORD (Para sa reset logic)
            elif user.check_old_password(password) and getattr(user, "temp_password", None):
                return render_template(
                    "super_admin_login.html",
                    show_temp=True,
                    temp_username=user.username,
                    temp_password=user.temp_password,
                    temp_full_name=user.full_name
                )

            else:
                flash("Invalid credentials.", "error")
                return redirect(url_for("super_admin_login"))

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

        if not username or not password or not role:
            return _signup_error("All fields required.")

        if not USERNAME_RE.match(username):
            return _signup_error(
                "Username must be 3-30 characters: letters, numbers, "
                "underscore, dot, hyphen only."
            )

        if len(full_name) < 2:
            return _signup_error("Full name is too short (min 2 characters).")
        if len(full_name) > 100:
            return _signup_error("Full name is too long (max 100 characters).")

        if role not in ("Teacher", "Student"):
            return _signup_error("Invalid role.")

        if find_user_by_username(username):
            return _signup_error("Username taken. Try another.")

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

        # ✅ FIX: I-save agad sa DB pagka-signup
        try: save_to_mongo()
        except: pass

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