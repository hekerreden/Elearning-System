# -*- coding: utf-8 -*-
"""In-memory data storage with MongoDB persistence."""
import os as _os

UPLOAD_DIR = _os.path.join(
    _os.path.dirname(_os.path.abspath(__file__)), "uploads"
)
_os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory lists (loaded from MongoDB on startup)
users = []
studies = []
quiz_results = []
attendance = []
notifications = []
connections = []
activities_list = []
temp_question = []


def load_from_mongo():
    """Load all data from MongoDB into memory. Called on startup."""
    import db
    db.load_all(users, studies, quiz_results,
                attendance, notifications, connections)


def save_to_mongo():
    """Save all in-memory data to MongoDB. Called after mutations."""
    import db
    db.save_all(users, studies, quiz_results,
                attendance, notifications, connections)