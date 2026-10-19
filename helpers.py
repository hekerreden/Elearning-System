# -*- coding: utf-8 -*-
"""Helper functions."""
import uuid
from datetime import datetime, timedelta
from flask import session, request
from storage import (users, studies, quiz_results,
                     notifications, connections)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def now_dt():
    return datetime.now()


def find_user_by_username(u):
    if not u:
        return None
    for x in users:
        if x.username.lower() == u.lower():
            return x
    return None


def find_user_by_id(uid):
    for x in users:
        if x.id == uid:
            return x
    return None


def find_study(stid):
    for s in studies:
        if s["id"] == stid:
            return s
    return None


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return find_user_by_id(uid)


def role_home(role):
    return {"SuperAdmin": "super_admin_page",
            "Teacher": "teacher_page",
            "Student": "student_page"}.get(role, "login")


def active_teachers_for_student(sid):
    out = []
    for c in connections:
        if c["student_id"] == sid and c["status"] == "active":
            t = find_user_by_id(c["teacher_id"])
            if t:
                out.append(t)
    return out


def active_students_for_teacher(tid):
    out = []
    for c in connections:
        if c["teacher_id"] == tid and c["status"] == "active":
            s = find_user_by_id(c["student_id"])
            if s:
                out.append(s)
    return out


def classmates_of(student):
    tids = [c["teacher_id"] for c in connections
            if c["student_id"] == student.id and c["status"] == "active"]
    out = []
    seen = set()
    for c in connections:
        if c["teacher_id"] in tids and c["status"] == "active":
            if c["student_id"] == student.id:
                continue
            if c["student_id"] in seen:
                continue
            seen.add(c["student_id"])
            s = find_user_by_id(c["student_id"])
            if s:
                out.append(s)
    return out


def can_view_user(viewer, target):
    if not viewer or not target:
        return False
    if viewer.id == target.id:
        return True
    if viewer.role == "SuperAdmin":
        return True
    for c in connections:
        if c["status"] != "active":
            continue
        if (c["student_id"] == viewer.id and c["teacher_id"] == target.id) or \
           (c["teacher_id"] == viewer.id and c["student_id"] == target.id):
            return True
    if viewer.role == "Student" and target.role == "Student":
        vts = {c["teacher_id"] for c in connections
               if c["student_id"] == viewer.id and c["status"] == "active"}
        tts = {c["teacher_id"] for c in connections
               if c["student_id"] == target.id and c["status"] == "active"}
        if vts & tts:
            return True
    return False


def notify(user_id, title, message, link=None, kind="info"):
    notifications.append({
        "id": uuid.uuid4().hex[:8],
        "user_id": user_id,
        "title": title,
        "message": message,
        "link": link or "",
        "read": False,
        "created_at": now_str(),
        "kind": kind,
    })


def unread_count(uid):
    return sum(1 for n in notifications if n["user_id"] == uid and not n["read"])


def search_users(query, viewer, limit=20):
    if not query:
        return []
    q = query.lower()
    out = []
    for u in users:
        if q not in u.username.lower() and q not in (u.full_name or "").lower():
            continue
        if viewer.role == "SuperAdmin":
            out.append(u)
        elif can_view_user(viewer, u):
            out.append(u)
        if len(out) >= limit:
            break
    return out
    
def get_login_candidates(username_input):
    """
    Returns a list of users who match the username 
    (either currently, or in their history).
    """
    if not username_input:
        return []
    
    u_lower = username_input.lower()
    candidates = []
    
    for x in users:
        # 1. Check current username
        if x.username.lower() == u_lower:
            candidates.append(x)
        # 2. Check history
        elif hasattr(x, 'username_history') and x.username_history:
            for old_u in x.username_history:
                if old_u and old_u.lower() == u_lower:
                    candidates.append(x)
                    break  # Break inner loop, go to next user
                    
    return candidates


def get_int(name, default=0):
    val = request.form.get(name, "")
    if val == "" or val is None:
        return default
    try:
        return int(val)
    except:
        return default


def cleanup_empty_drafts(teacher_id):
    to_remove = []
    for s in studies:
        if s.get("teacher_id") != teacher_id:
            continue
        if s.get("status") != "draft":
            continue
        if s.get("published_at"):
            continue
        has_content = any(
            (p.get("question", "") or "").strip()
            for p in s.get("pages", [])
        )
        has_slides = bool(s.get("slides"))
        if not has_content and not has_slides:
            to_remove.append(s)
    for s in to_remove:
        studies.remove(s)
    return len(to_remove)


def cleanup_expired_sessions(study):
    if study.get("has_attempts"):
        study["active_sessions"] = {}
        return 0
    now = now_dt()
    sessions = study.get("active_sessions") or {}
    expired = []
    for sid, info in sessions.items():
        try:
            last = datetime.strptime(info["last_ping"], "%Y-%m-%d %H:%M:%S")
            if (now - last).total_seconds() > 30:
                expired.append(sid)
        except (ValueError, KeyError, TypeError):
            expired.append(sid)
    for sid in expired:
        del sessions[sid]
    study["active_sessions"] = sessions
    return len(sessions)


def get_active_session_count(study):
    return cleanup_expired_sessions(study)


def is_study_locked(study):
    if study.get("has_attempts"):
        return True
    if get_active_session_count(study) > 0:
        return True
    return False


def cleanup_stale_editing(teacher_id):
    restored = 0
    now = now_dt()
    for s in studies:
        if s.get("teacher_id") != teacher_id:
            continue
        if s.get("status") != "editing":
            continue
        last_activity = s.get("edit_started_at") or s.get("updated_at")
        if not last_activity:
            continue
        try:
            try:
                dt = datetime.strptime(last_activity, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                dt = datetime.strptime(last_activity, "%Y-%m-%d %H:%M")
            elapsed = (now - dt).total_seconds()
            entered = s.get("entered_activity", False)
            threshold = 120 if entered else 30
            if elapsed > threshold:
                s["status"] = "published"
                s["visible_from"] = (
                    now_dt() + timedelta(seconds=10)
                ).strftime("%Y-%m-%d %H:%M:%S")
                s["updated_at"] = now_str()
                s.pop("edit_started_at", None)
                s.pop("entered_activity", None)
                restored += 1
        except (ValueError, TypeError):
            continue
    return restored