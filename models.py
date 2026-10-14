# -*- coding: utf-8 -*-
"""User class hierarchy."""
from config import hash_password, verify_password, generate_user_id
from config import generate_temp_password
from helpers import now_str


class User:
    def __init__(self, username, password=None, role="User",
                 full_name=None, status="active", password_hash=None):
        self.id = generate_user_id()
        self.username = username
        if password_hash:
            self.__password_hash = password_hash
        else:
            self.__password_hash = hash_password(password)
        self.role = role
        self.full_name = full_name or username
        self.status = status
        self.created_at = now_str()
        self.delete_requested_at = None
        self.delete_grace_until = None
        self.delete_reason = ""
        self.reset_pending = False
        self.temp_password = None
        self.old_password_hash = None
        self.reset_by = None
        self.reset_at = None

    def check_password(self, p):
        return verify_password(p, self.__password_hash)

    def set_password(self, p):
        self.__password_hash = hash_password(p)

    def reset_with_temp(self):
        self.old_password_hash = self.__password_hash
        self.temp_password = generate_temp_password()
        self.__password_hash = hash_password(self.temp_password)
        self.reset_pending = True
        self.reset_at = now_str()
        return self.temp_password

    def check_old_password(self, p):
        if not self.old_password_hash:
            return False
        return verify_password(p, self.old_password_hash)

    def finalize_password_change(self):
        self.reset_pending = False
        self.temp_password = None
        self.old_password_hash = None
        self.reset_by = None
        self.reset_at = None

    def is_active(self):
        return self.status == "active"

    def is_deleted(self):
        return self.status == "deleted"

    def dash(self):
        return "login"

    def to_dict(self, viewer=None, include_id=False):
        d = {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "full_name": self.full_name,
            "status": self.status,
            "created_at": self.created_at,
        }
        if self.role in ("Teacher", "Student"):
            if (viewer and viewer.id == self.id) or include_id:
                d["public_id"] = self.id
        return d


class SuperAdmin(User):
    def __init__(self, username, password=None, full_name="Super Admin", password_hash=None):
        super().__init__(username, password, "SuperAdmin", full_name,
                         "active", password_hash)

    def dash(self):
        return "super_admin.html"


class Teacher(User):
    def __init__(self, username, password=None, full_name=None,
                 status="active", password_hash=None):
        super().__init__(username, password, "Teacher",
                         full_name or username, status, password_hash)

    def dash(self):
        return "teacher.html"


class Student(User):
    def __init__(self, username, password=None, full_name=None,
                 status="active", password_hash=None):
        super().__init__(username, password, "Student",
                         full_name or username, status, password_hash)

    def dash(self):
        return "student.html"