# -*- coding: utf-8 -*-
"""Attendance routes."""
import re
import uuid
from datetime import datetime
from flask import request, redirect, url_for, flash
from storage import attendance, connections
from helpers import (current_user, find_user_by_id, today_str, now_str)
from decorators import role_required


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_STATUS = ("Present", "Absent", "Late")


def _valid_date(date_str):
    """Returns (ok, error_msg)"""
    if not DATE_RE.match(date_str):
        return False, "Invalid date format (use YYYY-MM-DD)."
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return False, "Invalid date."
    return True, ""


def register(app):

    @app.route("/api/attendance/mark", methods=["POST"])
    @role_required("Teacher")
    def mark_attendance():
        actor = current_user()
        student_id = request.form.get("student_id", "")
        status = request.form.get("status", "Present")
        date = request.form.get("date") or today_str()

        student = find_user_by_id(student_id)
        if not student or student.role != "Student":
            flash("Invalid student.", "error")
            return redirect(url_for("teacher_page"))

        if not any(c["student_id"] == student_id and c["teacher_id"] == actor.id
                   and c["status"] == "active" for c in connections):
            flash("Not connected to this student.", "error")
            return redirect(url_for("teacher_page"))

        if status not in VALID_STATUS:
            flash("Invalid status.", "error")
            return redirect(url_for("teacher_page"))

        # ✅ FIX: Validate date format
        ok, err = _valid_date(date)
        if not ok:
            flash(err, "error")
            return redirect(url_for("teacher_page"))

        existing = next((a for a in attendance
                         if a["student_id"] == student_id
                         and a["date"] == date
                         and a["teacher_id"] == actor.id), None)
        if existing:
            existing["status"] = status
            existing["timestamp"] = now_str()
        else:
            attendance.append({
                "id": uuid.uuid4().hex[:8],
                "student_id": student_id, "student_name": student.username,
                "teacher_id": actor.id, "teacher_name": actor.username,
                "date": date, "status": status, "timestamp": now_str(),
            })
        flash(f"Attendance recorded for {student.username}.", "success")
        return redirect(url_for("teacher_page"))

    @app.route("/api/attendance/<aid>/update", methods=["POST"])
    @role_required("Teacher")
    def update_attendance(aid):
        actor = current_user()
        rec = next((a for a in attendance if a["id"] == aid), None)
        if not rec or rec["teacher_id"] != actor.id:
            flash("Not found.", "error")
            return redirect(url_for("teacher_page"))

        status = request.form.get("status", "")
        if status not in VALID_STATUS:
            flash("Invalid status.", "error")
            return redirect(url_for("teacher_page"))

        rec["status"] = status
        rec["timestamp"] = now_str()
        flash("Attendance updated.", "success")
        return redirect(url_for("teacher_page"))

    @app.route("/api/attendance/<aid>/delete", methods=["POST"])
    @role_required("Teacher")
    def delete_attendance(aid):
        actor = current_user()
        rec = next((a for a in attendance if a["id"] == aid), None)
        if not rec or rec["teacher_id"] != actor.id:
            flash("Not found.", "error")
            return redirect(url_for("teacher_page"))

        attendance.remove(rec)
        flash("Attendance deleted.", "success")
        return redirect(url_for("teacher_page"))