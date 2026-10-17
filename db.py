# -*- coding: utf-8 -*-
"""MongoDB connection and persistence."""
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

MONGO_URI = os.environ.get("MONGO_URI", "")
MONGO_DB = os.environ.get("MONGO_DB", "elearning")

_client = None
_db = None
_is_connected = False


def init_db():
    """Initialize MongoDB connection. Call this on app startup."""
    global _client, _db, _is_connected
    if not MONGO_URI:
        print("⚠️  MONGO_URI not set — running WITHOUT persistence!")
        return False
    try:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Test connection
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


# ═══════════════════════════════════════════════════════════════
# USER SERIALIZATION
# ═══════════════════════════════════════════════════════════════
def user_to_doc(user):
    """Convert User object → MongoDB document."""
    return {
        "id": user.id,
        "username": user.username,
        "username_history": getattr(user, 'username_history', []),  # ✅ IDAGDAG
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
        # Access mangled private name
        "_password_hash": getattr(user, "_User__password_hash", None),
    }


def doc_to_user(doc):
    """Convert MongoDB document → User object."""
    from models import SuperAdmin, Teacher, Student

    role = doc.get("role", "User")
    password_hash = doc.get("_password_hash")

    if role == "SuperAdmin":
        user = SuperAdmin(
            username=doc.get("username", ""),
            password_hash=password_hash,
            full_name=doc.get("full_name", "Super Admin"),
        )
    elif role == "Teacher":
        user = Teacher(
            username=doc.get("username", ""),
            password_hash=password_hash,
            full_name=doc.get("full_name"),
            status=doc.get("status", "active"),
        )
    elif role == "Student":
        user = Student(
            username=doc.get("username", ""),
            password_hash=password_hash,
            full_name=doc.get("full_name"),
            status=doc.get("status", "active"),
        )
    else:
        from models import User
        user = User(
            username=doc.get("username", ""),
            password_hash=password_hash,
            role=role,
            full_name=doc.get("full_name"),
            status=doc.get("status", "active"),
        )

    # Overwrite generated fields
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


# ═══════════════════════════════════════════════════════════════
# LOAD FROM MONGODB
# ═══════════════════════════════════════════════════════════════
def load_all(users, studies, quiz_results, attendance, notifications, connections):
    """Load all collections from MongoDB into in-memory lists."""
    if not _is_connected:
        print("⚠️  Skipping load — not connected")
        return

    # Users
    users.clear()
    for doc in _db["users"].find({}, {"_id": 0}):
        try:
            users.append(doc_to_user(doc))
        except Exception as e:
            print(f"⚠️  Failed to load user: {e}")
    print(f"   Loaded {len(users)} users")

    # Studies
    studies.clear()
    for doc in _db["studies"].find({}, {"_id": 0}):
        studies.append(doc)
    print(f"   Loaded {len(studies)} studies")

    # Quiz results
    quiz_results.clear()
    for doc in _db["quiz_results"].find({}, {"_id": 0}):
        quiz_results.append(doc)
    print(f"   Loaded {len(quiz_results)} quiz results")

    # Attendance
    attendance.clear()
    for doc in _db["attendance"].find({}, {"_id": 0}):
        attendance.append(doc)
    print(f"   Loaded {len(attendance)} attendance records")

    # Notifications
    notifications.clear()
    for doc in _db["notifications"].find({}, {"_id": 0}):
        notifications.append(doc)
    print(f"   Loaded {len(notifications)} notifications")

    # Connections
    connections.clear()
    for doc in _db["connections"].find({}, {"_id": 0}):
        connections.append(doc)
    print(f"   Loaded {len(connections)} connections")


# ═══════════════════════════════════════════════════════════════
# SAVE TO MONGODB
# ═══════════════════════════════════════════════════════════════
def _clean_doc(doc):
    """Remove problematic keys and ensure JSON-serializable."""
    if not isinstance(doc, dict):
        return doc
    return {k: v for k, v in doc.items() if k != "_id"}


def save_all(users, studies, quiz_results, attendance, notifications, connections):
    """Save all in-memory data back to MongoDB. Replaces everything."""
    if not _is_connected:
        return

    try:
        # Users
        coll = _db["users"]
        coll.delete_many({})
        docs = [user_to_doc(u) for u in users]
        if docs:
            coll.insert_many(docs)

        # Studies
        coll = _db["studies"]
        coll.delete_many({})
        if studies:
            coll.insert_many([_clean_doc(s) for s in studies])

        # Quiz results
        coll = _db["quiz_results"]
        coll.delete_many({})
        if quiz_results:
            coll.insert_many([_clean_doc(r) for r in quiz_results])

        # Attendance
        coll = _db["attendance"]
        coll.delete_many({})
        if attendance:
            coll.insert_many([_clean_doc(a) for a in attendance])

        # Notifications
        coll = _db["notifications"]
        coll.delete_many({})
        if notifications:
            coll.insert_many([_clean_doc(n) for n in notifications])

        # Connections
        coll = _db["connections"]
        coll.delete_many({})
        if connections:
            coll.insert_many([_clean_doc(c) for c in connections])

    except Exception as e:
        print(f"❌ Save to MongoDB failed: {e}")