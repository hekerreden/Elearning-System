# -*- coding: utf-8 -*-
"""Studies CRUD + activity builder."""
import uuid
from datetime import timedelta
from flask import (request, redirect, url_for, flash, jsonify,
                   render_template)
from storage import studies, quiz_results
from helpers import (current_user, find_study, is_study_locked,
                     now_str, now_dt, get_int,
                     active_students_for_teacher, notify)
from decorators import role_required


def can_edit_study(actor, study):
    """True kung study owner si actor OR SuperAdmin."""
    if not study:
        return False
    if study["teacher_id"] == actor.id:
        return True
    if actor.role == "SuperAdmin":
        return True
    return False


def register(app):

    @app.route("/api/studies/create_draft", methods=["POST"])
    @role_required("Teacher")
    def create_draft():
        actor = current_user()
        title = request.form.get("title", "").strip() or "Untitled Study"
        study_type = request.form.get("type", "identification").strip()
        mode = request.form.get("mode", "direct_quiz").strip()
        direction = request.form.get("direction", "").strip()

        if study_type not in ("identification", "multiple_choice",
                              "true_false", "essay", "file_upload"):
            study_type = "identification"
        if mode not in ("direct_quiz", "study_and_quiz"):
            mode = "direct_quiz"

        score = get_int("score", 1)
        penalty = get_int("penalty", 0)
        study_timer = get_int("study_timer", 0) if mode == "study_and_quiz" else 0
        question_timer = get_int("question_timer", 10)
        max_back = get_int("max_back", 0)
        total_pages = max(1, get_int("total_pages", 1))
        mc_options = get_int("mc_options", 4)
        if mc_options not in (3, 4):
            mc_options = 4

        if question_timer <= 0:
            return jsonify({"error": "Question timer must be positive."}), 400

        def empty_page():
            p = {"question": ""}
            if study_type == "identification":
                p["correct_answer"] = ""
            elif study_type == "multiple_choice":
                p["choices"] = ["" for _ in range(mc_options)]
                p["correct_index"] = 0
            elif study_type == "true_false":
                p["correct_bool"] = True
            elif study_type == "essay":
                p["reference"] = ""
            elif study_type == "file_upload":
                p["instruction"] = ""
            return p

        new_id = uuid.uuid4().hex[:8]
        new_study = {
            "id": new_id,
            "teacher_id": actor.id,
            "teacher_name": actor.username,
            "title": title,
            "type": study_type,
            "mode": mode,
            "direction": direction,
            "study_timer": max(0, study_timer),
            "question_timer": max(1, question_timer),
            "max_back": max(0, max_back),
            "total_pages": total_pages,
            "mc_options": mc_options if study_type == "multiple_choice" else 0,
            "pages": [empty_page() for _ in range(total_pages)],
            "slides": [],
            "score": max(0, score),
            "penalty": max(0, penalty),
            "allow_retry": False,
            "status": "draft",
            "has_attempts": False,
            "locked": False,
            "locked_at": None,
            "locked_until": None,
            "active_sessions": {},
            "published_at": None,
            "visible_from": None,
            "created_at": now_str(),
            "updated_at": now_str(),
        }
        studies.append(new_study)
        return jsonify({"id": new_id})

    @app.route("/api/studies/<stid>/update", methods=["POST"])
    @role_required("Teacher", "SuperAdmin")
    def update_study(stid):
        actor = current_user()
        study = find_study(stid)
        if not can_edit_study(actor, study):
            flash("Not found or not yours.", "error")
            return redirect(url_for("teacher_page"))

        title = request.form.get("title", "").strip() or study.get("title", "Untitled Study")
        study_type = request.form.get("type", study.get("type", "identification")).strip()
        if study_type not in ("identification", "multiple_choice",
                              "true_false", "essay", "file_upload"):
            study_type = study.get("type", "identification")
        mode = request.form.get("mode", study.get("mode", "direct_quiz")).strip()
        if mode not in ("direct_quiz", "study_and_quiz"):
            mode = study.get("mode", "direct_quiz")

        mc_options = get_int("mc_options", study.get("mc_options", 4))
        if mc_options not in (3, 4):
            mc_options = 4

        study.update({
            "title": title,
            "type": study_type,
            "mode": mode,
            "direction": request.form.get("direction", study.get("direction", "")).strip(),
            "study_timer": max(0, get_int("study_timer", study.get("study_timer", 0))),
            "question_timer": max(1, get_int("question_timer", study.get("question_timer", 30))),
            "max_back": max(0, get_int("max_back", study.get("max_back", 0))),
            "score": max(0, get_int("score", study.get("score", 0))),
            "penalty": max(0, get_int("penalty", study.get("penalty", 0))),
            "mc_options": mc_options if study_type == "multiple_choice" else 0,
            "updated_at": now_str(),
        })
        flash("Settings updated. Now edit questions.", "success")
        if actor.role == "SuperAdmin":
            return redirect(url_for("super_admin_page"))
        return redirect(url_for("teacher_page"))

    @app.route("/api/studies/<stid>/save_page/<int:page_idx>", methods=["POST"])
    @role_required("Teacher", "SuperAdmin")
    def save_page(stid, page_idx):
        actor = current_user()
        study = find_study(stid)
        if not can_edit_study(actor, study):
            flash("Study not found.", "error")
            return redirect(url_for("teacher_page"))
        if is_study_locked(study):
            flash("🔒 Cannot edit — may student na nagsimula.", "error")
            return redirect(url_for("teacher_page"))

        new_title = request.form.get("title", "").strip()
        if new_title:
            study["title"] = new_title
        if "direction" in request.form:
            study["direction"] = request.form.get("direction", "").strip()

        while len(study["pages"]) <= page_idx:
            study["pages"].append({"question": ""})

        page = study["pages"][page_idx]
        page["question"] = request.form.get("question", "").strip()
        stype = study["type"]

        if stype == "identification":
            page["correct_answer"] = request.form.get("correct_answer", "").strip()
        elif stype == "multiple_choice":
            n = study.get("mc_options", 4)
            page["choices"] = [request.form.get(f"choice_{i}", "").strip() for i in range(n)]
            try:
                page["correct_index"] = int(request.form.get("correct_index", 0))
            except ValueError:
                page["correct_index"] = 0
        elif stype == "true_false":
            val = request.form.get("correct_bool", "true")
            page["correct_bool"] = (val == "true")
        elif stype == "essay":
            page["reference"] = request.form.get("reference", "").strip()
        elif stype == "file_upload":
            page["instruction"] = request.form.get("instruction", "").strip()

        study["updated_at"] = now_str()

        if page_idx + 1 < study["total_pages"]:
            return redirect(f"/teacher/activity/{stid}/{page_idx + 1}")
        return redirect(f"/teacher/activity/{stid}/preview")

    @app.route("/teacher/activity/<stid>/<int:page_idx>", methods=["GET", "POST"])
    @role_required("Teacher", "SuperAdmin")
    def activity_builder(stid, page_idx):
        actor = current_user()
        study = find_study(stid)
        if not can_edit_study(actor, study):
            flash("Study not found or not yours.", "error")
            return redirect(url_for("teacher_page"))
        if is_study_locked(study):
            flash("🔒 Cannot edit — may student na nagsimula ng quiz. "
                  "Wait for them to finish or lock to expire.", "error")
            return redirect(url_for("teacher_page"))

        if study.get("status") == "published":
            study["status"] = "editing"
            study["updated_at"] = now_str()
            notify(actor.id, "✏️ Study Hidden",
                   f"'{study['title']}' is temporarily hidden from students while you edit it.",
                   link="/teacher#studies", kind="info")

        if study.get("status") == "editing":
            study["edit_started_at"] = now_dt().strftime("%Y-%m-%d %H:%M:%S")
            study["entered_activity"] = True

        return render_template(
            "activity.html",
            study=study,
            page_idx=page_idx,
            is_admin=(actor.role == "SuperAdmin"),
        )

    @app.route("/teacher/activity/<stid>/preview", methods=["GET", "POST"])
    @role_required("Teacher", "SuperAdmin")
    def activity_preview(stid):
        actor = current_user()
        study = find_study(stid)
        if not can_edit_study(actor, study):
            flash("Study not found or not yours.", "error")
            return redirect(url_for("teacher_page"))
        if is_study_locked(study):
            flash("🔒 Cannot edit — may student na nagsimula ng quiz.", "error")
            return redirect(url_for("teacher_page"))

        if study.get("status") == "published":
            study["status"] = "editing"
            study["updated_at"] = now_str()

        if study.get("status") == "editing":
            study["edit_started_at"] = now_dt().strftime("%Y-%m-%d %H:%M:%S")
            study["entered_activity"] = True

        return render_template(
            "activity.html",
            study=study,
            is_preview=True,
            is_admin=(actor.role == "SuperAdmin"),
        )

    @app.route("/api/studies/<stid>/publish", methods=["POST"])
    @role_required("Teacher", "SuperAdmin")
    def publish_study(stid):
        actor = current_user()
        study = find_study(stid)
        if not can_edit_study(actor, study):
            flash("Study not found.", "error")
            return redirect(url_for("teacher_page"))
        if is_study_locked(study):
            flash("🔒 Cannot publish — may student na nagsimula ng quiz.", "error")
            return redirect(url_for("teacher_page"))

        stype = study.get("type", "identification")
        for i, p in enumerate(study["pages"]):
            if not p.get("question"):
                flash(f"Cannot publish — page {i+1} has no question.", "error")
                return redirect(f"/teacher/activity/{stid}/preview")
            if stype == "identification" and not p.get("correct_answer"):
                flash(f"Cannot publish — page {i+1} has no answer.", "error")
                return redirect(f"/teacher/activity/{stid}/preview")
            if stype == "multiple_choice":
                if not p.get("choices") or any(not c for c in p["choices"]):
                    flash(f"Cannot publish — page {i+1} has empty choices.", "error")
                    return redirect(f"/teacher/activity/{stid}/preview")

        study["status"] = "published"
        study["has_attempts"] = False
        study["published_at"] = now_str()
        study["visible_from"] = (now_dt() + timedelta(seconds=10)).strftime("%Y-%m-%d %H:%M:%S")
        study["updated_at"] = now_str()

        # Notify students of the ORIGINAL teacher (study owner)
        for s in active_students_for_teacher(study["teacher_id"]):
            notify(s.id, "📚 New Study Posted",
                   f"'{study['title']}' is now available. Check it in 10 seconds.",
                   link="/student#studies", kind="study")

        # If admin nag-publish, notify yung teacher
        if actor.role == "SuperAdmin" and study["teacher_id"] != actor.id:
            notify(study["teacher_id"], "✏️ Study Updated by Admin",
                   f"'{study['title']}' was edited and re-published by SuperAdmin.",
                   link="/teacher#studies", kind="info")

        flash(f"'{study['title']}' published! Students will see it in 10 seconds.", "success")
        if actor.role == "SuperAdmin":
            return redirect(url_for("super_admin_page"))
        return redirect(url_for("teacher_page"))

    @app.route("/api/studies/<stid>/save_slides", methods=["POST"])
    @role_required("Teacher", "SuperAdmin")
    def save_slides(stid):
        actor = current_user()
        study = find_study(stid)
        if not can_edit_study(actor, study):
            return jsonify({"ok": False, "error": "Not found"}), 404
        if is_study_locked(study):
            return jsonify({"ok": False, "error": "Study is locked."}), 403

        data = request.get_json(silent=True) or {}
        slides = data.get("slides", [])
        clean = []
        for s in slides:
            if isinstance(s, str):
                if s.strip():
                    clean.append({"text": s.strip()})
            elif isinstance(s, dict) and s.get("text"):
                clean.append({"text": str(s["text"]).strip()})

        study["slides"] = clean
        study["updated_at"] = now_str()
        return jsonify({"ok": True, "count": len(clean)})

    @app.route("/api/studies/<stid>/start_edit", methods=["POST"])
    @role_required("Teacher", "SuperAdmin")
    def start_edit_study(stid):
        actor = current_user()
        study = find_study(stid)
        if not can_edit_study(actor, study):
            return jsonify({"ok": False, "error": "Not found"}), 404
        if is_study_locked(study):
            return jsonify({"ok": False, "error": "Study is locked."}), 403

        if study.get("status") == "published":
            study["status"] = "editing"
            study["edit_started_at"] = now_dt().strftime("%Y-%m-%d %H:%M:%S")
            study["entered_activity"] = False
            study["updated_at"] = now_str()
            # Notify students of the original teacher
            for s in active_students_for_teacher(study["teacher_id"]):
                notify(s.id, "📚 Study Update",
                       f"'{study['title']}' is being updated. Please wait.",
                       link="/student#studies", kind="info")
        return jsonify({"ok": True, "status": study["status"]})

    @app.route("/api/studies/<stid>/cancel_edit", methods=["POST"])
    @role_required("Teacher", "SuperAdmin")
    def cancel_edit_study(stid):
        actor = current_user()
        study = find_study(stid)
        if not can_edit_study(actor, study):
            return jsonify({"ok": False, "error": "Not found"}), 404

        if study.get("status") == "editing":
            if study.get("has_attempts"):
                return jsonify({"ok": False, "error": "Has attempts — permanent."}), 400
            study["status"] = "published"
            study["visible_from"] = (now_dt() + timedelta(seconds=10)).strftime("%Y-%m-%d %H:%M:%S")
            study["updated_at"] = now_str()
            study.pop("edit_started_at", None)
            study.pop("entered_activity", None)
        return jsonify({"ok": True, "status": study["status"]})

    @app.route("/api/studies/<stid>/cancel", methods=["POST"])
    @role_required("Teacher", "SuperAdmin")
    def cancel_study(stid):
        actor = current_user()
        study = find_study(stid)
        if not can_edit_study(actor, study):
            return jsonify({"ok": False, "error": "Not found"}), 404

        has_content = any(
            (p.get("question", "") or "").strip()
            for p in study.get("pages", [])
        )
        has_slides = bool(study.get("slides"))
        if has_content or has_slides:
            return jsonify({"ok": True, "kept": True})
        studies.remove(study)
        return jsonify({"ok": True, "kept": False})

    @app.route("/api/studies/<stid>/delete", methods=["POST"])
    @role_required("Teacher", "SuperAdmin")
    def delete_study(stid):
        actor = current_user()
        study = find_study(stid)
        if not can_edit_study(actor, study):
            flash("Not found.", "error")
            return redirect(url_for("teacher_page"))
        if study.get("has_attempts"):
            flash("Cannot delete — may student attempts na. Archive na lang.", "error")
            return redirect(url_for("teacher_page"))

        studies.remove(study)
        quiz_results[:] = [r for r in quiz_results if r["study_id"] != stid]
        flash("Study deleted.", "success")
        if actor.role == "SuperAdmin":
            return redirect(url_for("super_admin_page"))
        return redirect(url_for("teacher_page"))