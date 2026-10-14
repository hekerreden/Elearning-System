# -*- coding: utf-8 -*-
"""Uploads + leaderboard."""
from flask import jsonify, send_from_directory
from werkzeug.utils import secure_filename
from storage import UPLOAD_DIR
from helpers import current_user, build_leaderboard
from decorators import role_required


def register(app):

    @app.route("/uploads/<fname>")
    @role_required("Teacher", "Student", "SuperAdmin")
    def serve_upload(fname):
        fname = secure_filename(fname)
        return send_from_directory(UPLOAD_DIR, fname)

    @app.route("/api/leaderboard")
    def api_leaderboard():
        u = current_user()
        if not u:
            return jsonify([])
        return jsonify(build_leaderboard())