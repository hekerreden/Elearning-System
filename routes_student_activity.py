# -*- coding: utf-8 -*-
"""Student activity page + heartbeat ping."""
from datetime import datetime
from flask import render_template, redirect, url_for, flash, jsonify
from storage import quiz_results, save_to_mongo
from helpers import (current_user, find_study, now_dt, now_str,
                     active_teachers_for_student, notify,
                     get_active_session_count)
from decorators import role_required


def register(app):

    @app.route("/student/activity/<stid>")
    @role_required("Student")
    def student_activity(stid):
        actor = current_user()
        study = find_study(stid)
        if not study:
            flash("Study not found.", "error")
            return redirect(url_for("student_page"))

        tids = {t.id for t in active_teachers_for_student(actor.id)}
        if study["teacher_id"] not in tids:
            flash("Not connected to this teacher.", "error")
            return redirect(url_for("student_page"))

        if study.get("status") != "published":
            flash("Study is not yet available.", "error")
            return redirect(url_for("student_page"))

        vf = study.get("visible_from")
        if vf:
            try:
                if datetime.strptime(vf, "%Y-%m-%d %H:%M:%S") > now_dt():
                    flash("Study is not yet available. Please wait a few seconds.", "error")
                    return redirect(url_for("student_page"))
            except (ValueError, TypeError):
                pass

        already = next((r for r in quiz_results
                        if r["student_id"] == actor.id and r["study_id"] == stid), None)
        if already and not study.get("allow_retry"):
            flash("Already submitted.", "error")
            return redirect(url_for("student_page"))

        # ✅ FIX: Track session + persist changes agad
        if not study.get("has_attempts"):
            if "active_sessions" not in study:
                study["active_sessions"] = {}
            was_empty = len(study["active_sessions"]) == 0
            study["active_sessions"][actor.id] = {
                "last_ping": now_dt().strftime("%Y-%m-%d %H:%M:%S"),
                "started_at": study["active_sessions"].get(actor.id, {}).get(
                    "started_at", now_str()
                ),
            }
            study["updated_at"] = now_str()

            if was_empty:
                notify(study["teacher_id"], "🔒 Study In Use",
                       f"May student na nagsimula ng '{study['title']}'.",
                       link="/teacher#studies", kind="info")

            # ✅ Force save to MongoDB (kasi GET ito)
            try:
                save_to_mongo()
            except Exception as e:
                print(f"⚠️ student_activity save failed: {e}")

        stype = study.get("type", "identification")

        # ✅ FIX: Skip slides na walang laman
        safe_pages = []
        for p in study.get("pages", []):
            sp = {"question": p.get("question", "")}
            if stype == "multiple_choice":
                sp["choices"] = list(p.get("choices", []))
            elif stype == "file_upload":
                sp["instruction"] = p.get("instruction", "")
            safe_pages.append(sp)

        safe_slides = []
        for s in (study.get("slides") or []):
            if isinstance(s, str):
                text = s.strip()
                if text:
                    safe_slides.append({"text": text})
            elif isinstance(s, dict):
                text = (s.get("text") or "").strip()
                if text:
                    safe_slides.append({"text": text})

        safe_study = {
            "id": study["id"],
            "title": study["title"],
            "type": stype,
            "mode": study.get("mode", "direct_quiz"),
            "direction": study.get("direction", ""),
            "study_timer": int(study.get("study_timer") or 0),
            "question_timer": int(study.get("question_timer") or 30),
            "max_back": int(study.get("max_back") or 0),
            "mc_options": int(study.get("mc_options") or 0),
            "total_pages": len(safe_pages),  # ✅ Fixed: quiz pages only
            "pages": safe_pages,
            "score": int(study.get("score") or 0),
            "penalty": int(study.get("penalty") or 0),
            "has_ppt": bool(safe_slides),
            "slides": safe_slides,
        }

        return render_template("student_activity.html",
                               user=actor, study=safe_study, my_id=actor.id)

    @app.route("/api/studies/<stid>/ping", methods=["POST"])
    @role_required("Student")
    def ping_study(stid):
        actor = current_user()
        study = find_study(stid)
        if not study:
            return jsonify({"ok": False, "error": "Not found"}), 404
        if study.get("has_attempts"):
            return jsonify({"ok": True, "locked": True})
        if "active_sessions" not in study:
            study["active_sessions"] = {}
        study["active_sessions"][actor.id] = {
            "last_ping": now_dt().strftime("%Y-%m-%d %H:%M:%S"),
            "started_at": study["active_sessions"].get(actor.id, {}).get(
                "started_at", now_str()
            ),
        }
        
        # ✅ SAVE SA DB (Para malaman ng teacher na active pa ang student)
        try: save_to_mongo()
        except Exception as e: print(f"⚠️ Ping save failed: {e}")
        
        return jsonify({"ok": True, "active": get_active_session_count(study)})