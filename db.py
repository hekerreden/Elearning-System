# -*- coding: utf-8 -*-
"""MongoDB connection and persistence."""
import os
from pymongo import MongoClient, ReplaceOne, DeleteMany
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

MONGO_URI = os.environ.get("MONGO_URI", "")
MONGO_DB = os.environ.get("MONGO_DB", "elearning")

_client = None
_db = None
_is_connected = False


def init_db():
    global _client, _db, _is_connected
    if not MONGO_URI:
        print("⚠️  MONGO_URI not set — running WITHOUT persistence!")
        return False
    try:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        _client.admin.command("ping")
        _db = _client[MONGO_DB]
        _is_connected = True
        print(f"✅ Connected to MongoDB: {MONGO_DB}")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"❌ MongoDB connection failed: {e}")
        _is_connected = False
        return False


def get_db():
    return _db if _is_connected else None


def is_connected():
    return _is_connected


def user_to_doc(user):
    return {
        "id": user.id,
        "username": user.username,
        "username_history": getattr(user, 'username_history', []),
        "role": user.role,
        "full_name": user.full_name,
        "status": user.status,
        "created_at": user.created_at,
        "delete_requested_at": user.delete_requested_at,
        "delete_grace_until": user.delete_grace_until,
        "delete_reason": user.delete_reason or "",
        "reset_pending": user.reset_pending,
        "temp_password": user.temp_password,
        "old_password_hash": user.old_password_hash,
        "reset_by": user.reset_by,
        "reset_at": user.reset_at,
        "_password_hash": getattr(user, "_User__password_hash", None),
    }


def doc_to_user(doc):
    from models import SuperAdmin, Teacher, Student, User
    role = doc.get("role", "User")
    password_hash = doc.get("_password_hash")

    if role == "SuperAdmin":
        user = SuperAdmin(username=doc.get("username", ""), password_hash=password_hash, full_name=doc.get("full_name", "Super Admin"))
    elif role == "Teacher":
        user = Teacher(username=doc.get("username", ""), password_hash=password_hash, full_name=doc.get("full_name"), status=doc.get("status", "active"))
    elif role == "Student":
        user = Student(username=doc.get("username", ""), password_hash=password_hash, full_name=doc.get("full_name"), status=doc.get("status", "active"))
    else:
        user = User(username=doc.get("username", ""), password_hash=password_hash, role=role, full_name=doc.get("full_name"), status=doc.get("status", "active"))

    user.id = doc.get("id", user.id)
    user.username_history = doc.get("username_history") or []
    user.created_at = doc.get("created_at", user.created_at)
    user.delete_requested_at = doc.get("delete_requested_at")
    user.delete_grace_until = doc.get("delete_grace_until")
    user.delete_reason = doc.get("delete_reason", "")
    user.reset_pending = doc.get("reset_pending", False)
    user.temp_password = doc.get("temp_password")
    user.old_password_hash = doc.get("old_password_hash")
    user.reset_by = doc.get("reset_by")
    user.reset_at = doc.get("reset_at")
    return user


def load_all(users, studies, quiz_results, attendance, notifications, connections):
    if not _is_connected: return
    users.clear()
    for doc in _db["users"].find({}, {"_id": 0}):
        try: users.append(doc_to_user(doc))
        except Exception as e: pass
    studies.clear(); studies.extend(list(_db["studies"].find({}, {"_id": 0})))
    quiz_results.clear(); quiz_results.extend(list(_db["quiz_results"].find({}, {"_id": 0})))
    attendance.clear(); attendance.extend(list(_db["attendance"].find({}, {"_id": 0})))
    notifications.clear(); notifications.extend(list(_db["notifications"].find({}, {"_id": 0})))
    connections.clear(); connections.extend(list(_db["connections"].find({}, {"_id": 0})))


def _clean_doc(doc):
    if not isinstance(doc, dict): return doc
    return {k: v for k, v in doc.items() if k != "_id"}


def save_all(users, studies, quiz_results, attendance, notifications, connections):
    """✅ OPTIMIZED: Gumagamit ng bulk_write para isang bagsakan lang ang save."""
    if not _is_connected: return

    try:
        # 1. USERS
        ops = []
        current_ids = [u.id for u in users]
        ops.append(DeleteMany({"id": {"$nin": current_ids}}))
        for u in users:
            ops.append(ReplaceOne({"id": u.id}, user_to_doc(u), upsert=True))
        if ops: _db["users"].bulk_write(ops, ordered=False)

        # 2. STUDIES
        ops = []
        current_ids = [s["id"] for s in studies]
        ops.append(DeleteMany({"id": {"$nin": current_ids}}))
        for s in studies:
            ops.append(ReplaceOne({"id": s["id"]}, _clean_doc(s), upsert=True))
        if ops: _db["studies"].bulk_write(ops, ordered=False)

        # 3. QUIZ RESULTS
        ops = []
        current_ids = [r["id"] for r in quiz_results]
        ops.append(DeleteMany({"id": {"$nin": current_ids}}))
        for r in quiz_results:
            ops.append(ReplaceOne({"id": r["id"]}, _clean_doc(r), upsert=True))
        if ops: _db["quiz_results"].bulk_write(ops, ordered=False)

        # 4. ATTENDANCE
        ops = []
        current_ids = [a["id"] for a in attendance]
        ops.append(DeleteMany({"id": {"$nin": current_ids}}))
        for a in attendance:
            ops.append(ReplaceOne({"id": a["id"]}, _clean_doc(a), upsert=True))
        if ops: _db["attendance"].bulk_write(ops, ordered=False)

        # 5. NOTIFICATIONS
        ops = []
        current_ids = [n["id"] for n in notifications]
        ops.append(DeleteMany({"id": {"$nin": current_ids}}))
        for n in notifications:
            ops.append(ReplaceOne({"id": n["id"]}, _clean_doc(n), upsert=True))
        if ops: _db["notifications"].bulk_write(ops, ordered=False)

        # 6. CONNECTIONS
        ops = []
        current_ids = [c["id"] for c in connections]
        ops.append(DeleteMany({"id": {"$nin": current_ids}}))
        for c in connections:
            ops.append(ReplaceOne({"id": c["id"]}, _clean_doc(c), upsert=True))
        if ops: _db["connections"].bulk_write(ops, ordered=False)

    except Exception as e:
        print(f"❌ Save to MongoDB failed: {e}")