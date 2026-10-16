# -*- coding: utf-8 -*-
"""Connection request/approve/reject."""
import uuid
from flask import request, redirect, url_for, flash
from storage import connections
from helpers import (current_user, find_user_by_id, role_home,
                     notify, now_str)
from decorators import role_required


def register(app):

    @app.route("/api/connections/request", methods=["POST"])
    @role_required("Teacher", "Student")
    def request_connection():
        actor = current_user()
        target = find_user_by_id(target_id)
        if not target:
            flash(f"No user found with ID {target_id}.", "error")
            return redirect(url_for(role_home(actor.role)))
        if target.status == "deleted":
            flash("This user is no longer available.", "error")
            return redirect(url_for(role_home(actor.role)))
        if target.status in ("pending_delete", "appealed"):
            flash("This user's account is under review.", "error")
            return redirect(url_for(role_home(actor.role)))
        if {actor.role, target.role} != {"Teacher", "Student"}:
            flash("Invalid connection request.", "error")
            return redirect(url_for(role_home(actor.role)))
        target = find_user_by_id(target_id)
        if not target:
            flash(f"No user found with ID {target_id}.", "error")
            return redirect(url_for(role_home(actor.role)))
        if {actor.role, target.role} != {"Teacher", "Student"}:
            flash("Invalid connection request.", "error")
            return redirect(url_for(role_home(actor.role)))

        if actor.role == "Student":
            student, teacher = actor, target
        else:
            student, teacher = target, actor

        for c in connections:
            if c["student_id"] == student.id and c["teacher_id"] == teacher.id:
                if c["status"] == "active":
                    flash("You are already connected.", "error")
                else:
                    flash("A pending request already exists.", "error")
                return redirect(url_for(role_home(actor.role)))

        conn = {
            "id": uuid.uuid4().hex[:8],
            "student_id": student.id,
            "teacher_id": teacher.id,
            "status": "pending",
            "requested_by": actor.role.lower(),
            "created_at": now_str(),
        }
        connections.append(conn)
        notify(target.id, "New Connection Request",
               f"{actor.full_name} (@{actor.username}) wants to connect with you.",
               link=f"/{target.role.lower()}#connect",
               kind="connection_request")
        flash(f"Request sent to {target.full_name}!", "success")
        return redirect(url_for(role_home(actor.role)))

    @app.route("/api/connections/<cid>/approve", methods=["POST"])
    @role_required("Teacher", "Student")
    def approve_connection(cid):
        actor = current_user()
        conn = next((c for c in connections if c["id"] == cid), None)
        if not conn:
            flash("Request not found.", "error")
            return redirect(url_for(role_home(actor.role)))
        if conn["requested_by"] == actor.role.lower():
            flash("You cannot approve your own request.", "error")
            return redirect(url_for(role_home(actor.role)))
        if actor.id not in (conn["student_id"], conn["teacher_id"]):
            flash("Not your request.", "error")
            return redirect(url_for(role_home(actor.role)))

        conn["status"] = "active"
        other_id = conn["teacher_id"] if actor.id == conn["student_id"] else conn["student_id"]
        other = find_user_by_id(other_id)
        if other and other.status == "active":
            target_section = "teachers" if other.role == "Student" else "students"
            notify(other_id, "Connection Approved",
                   f"{actor.full_name} accepted your connection request.",
                   link=f"/{other.role.lower()}#{target_section}",
                   kind="connection_approved")
        flash("Connection approved!", "success")
        return redirect(url_for(role_home(actor.role)))

    @app.route("/api/connections/<cid>/reject", methods=["POST"])
    @role_required("Teacher", "Student")
    def reject_connection(cid):
        actor = current_user()
        conn = next((c for c in connections if c["id"] == cid), None)
        if not conn:
            flash("Request not found.", "error")
            return redirect(url_for(role_home(actor.role)))
        if actor.id not in (conn["student_id"], conn["teacher_id"]):
            flash("Not your request.", "error")
            return redirect(url_for(role_home(actor.role)))

        other_id = conn["teacher_id"] if actor.id == conn["student_id"] else conn["student_id"]
        connections.remove(conn)
        other = find_user_by_id(other_id)
        if other:
            notify(other_id, "Connection Rejected",
                   f"{actor.full_name} declined your connection request.",
                   link=f"/{other.role.lower()}#connect",
                   kind="connection_rejected")
        flash("Request rejected.", "success")
        return redirect(url_for(role_home(actor.role))) 