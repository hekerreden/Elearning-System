# -*- coding: utf-8 -*-
"""Quiz submit + grading."""
import json as _json
import uuid
import os as _os
from flask import request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from storage import quiz_results, UPLOAD_DIR
from helpers import (current_user, find_study,
                     active_teachers_for_student, now_str, notify)
from decorators import role_required


def register(app):

    @app.route("/api/quiz/submit", methods=["POST"])
    @role_required("Student")
    def submit_quiz():
        actor = current_user()

        if request.is_json:
            data = request.get_json()
            study_id = data.get("study_id", "")
            answers = data.get("answers", [])
            total_time = int(data.get("total_time", 0))
            files_map = {}
        else:
            study_id = request.form.get("study_id", "")
            total_time = int(request.form.get("total_time", 0))
            try:
                meta = _json.loads(request.form.get("answers_meta", "[]"))
            except Exception:
                meta = []
            answers = []
            files_map = {}
            for item in meta:
                i = item.get("idx", 0)
                while len(answers) <= i:
                    answers.append(None)
                if item.get("type") == "file":
                    answers[i] = item.get("name", "")
                    key = "file_" + str(i)
                    if key in request.files:
                        f = request.files[key]
                        if f and f.filename:
                            safe = secure_filename(f.filename)
                            fname = uuid.uuid4().hex[:8] + "_" + safe
                            path = _os.path.join(UPLOAD_DIR, fname)
                            f.save(path)
                            files_map[i] = {
                                "name": safe, "stored": fname,
                                "url": "/uploads/" + fname,
                            }
                else:
                    answers[i] = item.get("value")

        study = find_study(study_id)
        if not study:
            return jsonify({"error": "Study not found."}), 404

        tids = {t.id for t in active_teachers_for_student(actor.id)}
        if study["teacher_id"] not in tids:
            return jsonify({"error": "Not connected to this teacher."}), 403
        if study.get("status") != "published":
            return jsonify({"error": "Study not yet available."}), 400

        already = [r for r in quiz_results
                   if r["student_id"] == actor.id and r["study_id"] == study_id]
        if already and not study.get("allow_retry"):
            return jsonify({"error": "Already submitted."}), 400

        pages = study.get("pages", [])
        if not pages:
            return jsonify({"error": "Study has no questions."}), 400

        stype = study.get("type", "identification")
        has_ppt = bool(study.get("slides"))
        study_secs = int(study.get("study_timer") or 0) if (
            study.get("mode") == "study_and_quiz" and has_ppt) else 3
        min_time = study_secs + int(study.get("question_timer") or 30) * len(pages)
        if total_time and total_time < min_time - 5:
            return jsonify({"error": "Submitted too fast."}), 400

        score_per = int(study.get("score") or 0)
        penalty_per = int(study.get("penalty") or 0)
        total_score = 0
        correct_count = 0
        has_manual = False
        details = []

        for i, p in enumerate(pages):
            ans = answers[i] if i < len(answers) else None
            is_correct = False
            pending = False
            display_your = ans
            display_correct = ""
            file_info = files_map.get(i)

            if stype == "identification":
                ua = (ans or "").strip().lower() if isinstance(ans, str) else ""
                ca = (p.get("correct_answer", "") or "").strip().lower()
                is_correct = bool(ca) and ua == ca
                display_your = ans or ""
                display_correct = p.get("correct_answer", "")
            elif stype == "multiple_choice":
                try:
                    uidx = int(ans) if ans is not None else -1
                except:
                    uidx = -1
                cidx = int(p.get("correct_index", 0))
                is_correct = (uidx == cidx)
                choices = p.get("choices", [])
                letters = ['A', 'B', 'C', 'D']
                display_your = (letters[uidx] + ". " + choices[uidx]) if (0 <= uidx < len(choices)) else "(blank)"
                display_correct = (letters[cidx] + ". " + choices[cidx]) if (0 <= cidx < len(choices)) else ""
            elif stype == "true_false":
                ua = str(ans).lower() if ans is not None else ""
                ca = "true" if p.get("correct_bool", True) else "false"
                is_correct = (ua == ca)
                display_your = "True" if ua == "true" else ("False" if ua == "false" else "(blank)")
                display_correct = "True" if ca == "true" else "False"
            elif stype in ("essay", "file_upload"):
                pending = True
                has_manual = True
                display_your = ans if ans else "(blank)"
                display_correct = "(teacher will grade)"

            if pending:
                pass
            elif is_correct:
                total_score += score_per
                correct_count += 1
            else:
                total_score -= penalty_per

            details.append({
                "idx": i,
                "question": p.get("question", ""),
                "your_answer": display_your,
                "correct_answer": display_correct,
                "correct": is_correct,
                "pending": pending,
                "file": file_info,
            })

        # ✅ Tinanggal ang medal at pct
        quiz_results.append({
            "id": uuid.uuid4().hex[:8],
            "student_id": actor.id, "student_name": actor.username,
            "study_id": study_id, "study_title": study["title"],
            "answer": str([a if not hasattr(a, 'filename') else a.filename for a in answers]),
            "correct": correct_count == len(pages),
            "score": total_score,
            "correct_count": correct_count,
            "total_questions": len(pages),
            "has_manual": has_manual,
            "graded": not has_manual,
            "details": details,
            "timestamp": now_str(), "adjusted": False,
        })

        study["has_attempts"] = True
        notify(study["teacher_id"], "Quiz Submitted",
               f"{actor.full_name} submitted '{study['title']}'"
               + (f" — needs grading." if has_manual
                  else f" — {correct_count}/{len(pages)} correct."),
               link="/teacher#history", kind="quiz")

        return jsonify({
            "ok": True,
            "score": total_score,
            "correct_count": correct_count,
            "total": len(pages),
            "has_manual": has_manual,
            "details": details,
        })

    @app.route("/api/results/<rid>/update", methods=["POST"])
    @role_required("Teacher")
    def update_result(rid):
        actor = current_user()
        result = next((r for r in quiz_results if r["id"] == rid), None)
        if not result:
            flash("Result not found.", "error")
            return redirect(url_for("teacher_page"))
        study = find_study(result["study_id"])
        if not study or study["teacher_id"] != actor.id:
            flash("Not your study.", "error")
            return redirect(url_for("teacher_page"))
        try:
            new_score = int(request.form.get("score", result["score"]))
        except ValueError:
            flash("Number required.", "error")
            return redirect(url_for("teacher_page"))
        result["score"] = new_score
        result["adjusted"] = True
        notify(result["student_id"], "Score Adjusted",
               f"Your score for '{study['title']}' was updated to {new_score}.",
               link="/student#history", kind="score")
        flash("Score updated.", "success")
        return redirect(url_for("teacher_page"))

    @app.route("/api/results/<rid>/grade-info")
    @role_required("Teacher")
    def grade_info(rid):
        actor = current_user()
        result = next((r for r in quiz_results if r["id"] == rid), None)
        if not result:
            return jsonify({"error": "Result not found."}), 404
        study = find_study(result["study_id"])
        if not study or study["teacher_id"] != actor.id:
            return jsonify({"error": "Not your study."}), 403
        return jsonify({
            "id": result["id"],
            "student_name": result.get("student_name", ""),
            "study_title": result.get("study_title", ""),
            "study_type": study.get("type", ""),
            "details": result.get("details", []),
            "graded": result.get("graded", True),
            "score": result.get("score", 0),
        })

    @app.route("/api/results/<rid>/grade", methods=["POST"])
    @role_required("Teacher")
    def grade_result(rid):
        actor = current_user()
        result = next((r for r in quiz_results if r["id"] == rid), None)
        if not result:
            return jsonify({"error": "Result not found."}), 404
        study = find_study(result["study_id"])
        if not study or study["teacher_id"] != actor.id:
            return jsonify({"error": "Not your study."}), 403

        data = request.get_json() or {}
        scores = data.get("scores", [])
        score_map = {s["idx"]: int(s["score"]) for s in scores}

        total = 0
        details = result.get("details", [])
        correct_count = 0

        for i, d in enumerate(details):
            if i in score_map:
                awarded = score_map[i]
                d["awarded_score"] = awarded
                d["correct"] = (awarded > 0)
                d["pending"] = False
                total += awarded
                if awarded > 0:
                    correct_count += 1

        result["details"] = details
        result["score"] = total
        result["graded"] = True
        result["adjusted"] = True
        result["correct_count"] = correct_count
        result["correct"] = (correct_count == len(details))

        notify(result["student_id"], "📝 Quiz Graded",
               f"Your submission for '{study['title']}' has been graded. Score: {total}.",
               link="/student#history", kind="score")

        return jsonify({"ok": True, "score": total})