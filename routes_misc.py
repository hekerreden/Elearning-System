# -*- coding: utf-8 -*-
"""Uploads."""
from flask import send_from_directory
from werkzeug.utils import secure_filename
from storage import UPLOAD_DIR
from decorators import role_required


def register(app):

    @app.route("/uploads/<fname>")
    @role_required("Teacher", "Student", "SuperAdmin")
    def serve_upload(fname):
        fname = secure_filename(fname)
        return send_from_directory(UPLOAD_DIR, fname)