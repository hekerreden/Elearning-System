# -*- coding: utf-8 -*-
"""Notifications + search API."""
from flask import jsonify, request
from storage import notifications
from helpers import current_user, unread_count, search_users
from helpers import now_str  # noqa


def register(app):

    @app.route("/api/notifications")
    def api_notifications():
        u = current_user()
        if not u:
            return jsonify([])
        mine = [n for n in notifications if n["user_id"] == u.id]

        # Unread muna, tapos latest
        unread = [n for n in mine if not n.get("read")]
        read = [n for n in mine if n.get("read")]
        unread.sort(key=lambda n: n["created_at"], reverse=True)
        read.sort(key=lambda n: n["created_at"], reverse=True)

        return jsonify((unread + read)[:30])

    @app.route("/api/notifications/<nid>/read", methods=["POST"])
    def mark_read(nid):
        u = current_user()
        if not u:
            return jsonify({"ok": False}), 401
        n = next((x for x in notifications
                  if x["id"] == nid and x["user_id"] == u.id), None)
        if n:
            n["read"] = True
        return jsonify({"ok": True})

    @app.route("/api/notifications/read-all", methods=["POST"])
    def mark_all_read():
        u = current_user()
        if not u:
            return jsonify({"ok": False}), 401
        for n in notifications:
            if n["user_id"] == u.id:
                n["read"] = True
        return jsonify({"ok": True})

    @app.route("/api/search")
    def api_search():
        u = current_user()
        if not u:
            return jsonify([])
        q = request.args.get("q", "").strip()
        if not q:
            return jsonify([])
        found = search_users(q, u)
        return jsonify([x.to_dict(viewer=u) for x in found])
        
    @app.route("/api/notifications/<nid>/delete", methods=["POST"])
    def delete_notification(nid):
        u = current_user()
        if not u:
            return jsonify({"ok": False}), 401
            
        # Hanapin ang notification
        target = None
        for n in notifications:
            if n["id"] == nid and n["user_id"] == u.id:
                target = n
                break
                
        if target:
            notifications.remove(target)
            # ✅ Explicit save para mawala agad sa MongoDB
            try:
                from storage import save_to_mongo
                save_to_mongo()
            except Exception as e:
                print(f"⚠️ Delete notif save failed: {e}")
                
        return jsonify({"ok": True})