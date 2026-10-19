# -*- coding: utf-8 -*-
"""Dashboard pages: super admin, teacher, student."""
from flask import render_template
from storage import (users, studies, quiz_results, attendance, connections, load_from_mongo)
from helpers import (current_user, now_dt, today_str, classmates_of,
                     active_teachers_for_student, active_students_for_teacher,
                     cleanup_empty_drafts,
                     cleanup_stale_editing, is_study_locked,
                     get_active_session_count, find_user_by_id)
from decorators import role_required
from datetime import datetime
from db import is_connected

def register(app):

    @app.route("/super-admin")
    @role_required("SuperAdmin")
    def super_admin_page():
        u = current_user()
        # ✅ SYNC: Kunin ang pinakabagong data mula MongoDB
        if is_connected():
            load_from_mongo()

        pending_deletes = [x for x in users
                           if x.status in ("pending_delete", "appealed")]

        def user_with_reset_info(x):
            d = x.to_dict(viewer=u)
            d["reset_pending"] = x.reset_pending
            d["reason"] = x.delete_reason or ""
            d["grace_until"] = x.delete_grace_until or ""
            d["requested_at"] = x.delete_requested_at or ""
            return d

        return render_template(
            "super_admin.html",
            user=u,
            all_users=[user_with_reset_info(x) for x in users
                       if x.status != "deleted"],
            teachers=[user_with_reset_info(x) for x in users
                      if x.role == "Teacher" and x.status == "active"],
            students=[user_with_reset_info(x) for x in users
                      if x.role == "Student" and x.status == "active"],
            studies=studies,
            results=quiz_results,
            attendance=attendance,
            pending_deletes=[user_with_reset_info(x) for x in pending_deletes],
            all_users=users, 
            total_notifications=0,
        )
        
    @app.route("/teacher")
    @role_required("Teacher")
    def teacher_page():
        u = current_user()
        # ✅ SYNC: Kunin ang pinakabagong data mula MongoDB
        if is_connected():
            load_from_mongo()
        removed = cleanup_empty_drafts(u.id)
        restored = cleanup_stale_editing(u.id)

        # Persist cleanup changes sa MongoDB (kasi GET ito, hindi auto-save)
        if removed or restored:
            try:
                from storage import save_to_mongo
                save_to_mongo()
                print(f"Cleanup saved: {removed} drafts removed, {restored} restored")
            except Exception as e:
                print(f"⚠️ Cleanup save failed: {e}")

        my_students = active_students_for_teacher(u.id)
        pending_in = [c for c in connections
                      if c["teacher_id"] == u.id and c["status"] == "pending"
                      and c["requested_by"] == "student"]
        pending_out = [c for c in connections
                       if c["teacher_id"] == u.id and c["status"] == "pending"
                       and c["requested_by"] == "teacher"]

        my_studies = [
            s for s in studies
            if s["teacher_id"] == u.id
            and s.get("status") in ("published", "editing")
        ]
        my_studies.sort(key=lambda s: s.get("updated_at", ""), reverse=True)

        for s in my_studies:
            s["is_locked"] = is_study_locked(s)
            s["active_count"] = get_active_session_count(s)

        visible_ids = {s["id"] for s in my_studies}
        my_results = [r for r in quiz_results if r["study_id"] in visible_ids]
        my_results.sort(key=lambda r: r["timestamp"], reverse=True)
        my_attendance = [a for a in attendance if a["teacher_id"] == u.id]
        my_attendance.sort(key=lambda a: a["timestamp"], reverse=True)

        pending_in_details = []
        for c in pending_in:
            s = find_user_by_id(c["student_id"])
            if s:
                pending_in_details.append({"conn": c,
                                           "student": s.to_dict(viewer=u)})
        pending_out_details = []
        for c in pending_out:
            s = find_user_by_id(c["student_id"])
            if s:
                pending_out_details.append({"conn": c,
                                            "student": s.to_dict(viewer=u)})

        return render_template(
            "teacher.html",
            user=u,
            students=[s.to_dict(viewer=u) for s in my_students],
            pending_in=pending_in_details,
            pending_out=pending_out_details,
            studies=my_studies,
            results=my_results,
            attendance=my_attendance,
            today=today_str(),
            my_id=u.id,
        )

    @app.route("/student")
    @role_required("Student")
    def student_page():
        u = current_user()
        # ✅ SYNC: Kunin ang pinakabagong data mula MongoDB
        if is_connected():
            load_from_mongo()
        my_teachers = active_teachers_for_student(u.id)
        classmates = classmates_of(u)
        pending_in = [c for c in connections
                      if c["student_id"] == u.id and c["status"] == "pending"
                      and c["requested_by"] == "teacher"]
        pending_out = [c for c in connections
                       if c["student_id"] == u.id and c["status"] == "pending"
                       and c["requested_by"] == "student"]

        pending_in_details = []
        for c in pending_in:
            t = find_user_by_id(c["teacher_id"])
            if t:
                pending_in_details.append({"conn": c,
                                           "teacher": t.to_dict(viewer=u)})
        pending_out_details = []
        for c in pending_out:
            t = find_user_by_id(c["teacher_id"])
            if t:
                pending_out_details.append({"conn": c,
                                            "teacher": t.to_dict(viewer=u)})

        teacher_ids = {t.id for t in my_teachers}
        now = now_dt()

        def _is_visible(s):
            if s["teacher_id"] not in teacher_ids:
                return False
            if s.get("status") != "published":
                return False
            vf = s.get("visible_from")
            if vf:
                try:
                    if datetime.strptime(vf, "%Y-%m-%d %H:%M:%S") > now:
                        return False
                except (ValueError, TypeError):
                    pass
            return True

        visible_studies = [s for s in studies if _is_visible(s)]
        attempted_ids = {r["study_id"] for r in quiz_results
                         if r["student_id"] == u.id}

        safe_studies = []
        for s in visible_studies:
            safe_pages = [
                {"question": p.get("question", ""),
                 "description": p.get("description", "")}
                for p in s.get("pages", [])
            ]
            safe_slides = []
            for sl in (s.get("slides") or []):
                if isinstance(sl, str):
                    safe_slides.append({"text": sl})
                elif isinstance(sl, dict):
                    safe_slides.append({"text": sl.get("text", "")})

            safe_studies.append({
                "id": s["id"],
                "title": s["title"],
                "type": s.get("type", "identification"),
                "direction": s.get("direction", ""),
                "study_timer": int(s.get("study_timer") or 0),
                "question_timer": int(s.get("question_timer") or 30),
                "max_back": int(s.get("max_back") or 0),
                "score": int(s.get("score") or 0),
                "penalty": int(s.get("penalty") or 0),
                "teacher_name": s.get("teacher_name", ""),
                "pages": safe_pages,
                "has_ppt": bool(safe_slides),
                "slides": safe_slides,
                "already_done": s["id"] in attempted_ids,
            })

        my_results = [r for r in quiz_results if r["student_id"] == u.id]
        my_results.sort(key=lambda r: r["timestamp"], reverse=True)
        my_attendance = [a for a in attendance if a["student_id"] == u.id]
        my_attendance.sort(key=lambda a: a["date"], reverse=True)

        return render_template(
            "student.html",
            user=u,
            teachers=[t.to_dict(viewer=u) for t in my_teachers],
            classmates=[c.to_dict(viewer=u) for c in classmates],
            pending_in=pending_in_details,
            pending_out=pending_out_details,
            studies=safe_studies,
            results=my_results,
            attendance=my_attendance,
            my_id=u.id,
            show_temp_reset=u.reset_pending,
            temp_password=u.temp_password if u.reset_pending else None,
        )