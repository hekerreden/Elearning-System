# -*- coding: utf-8 -*-
"""Security helpers and constants."""
import os, hashlib, secrets

PASSWORD_PEPPER = os.environ.get("PASSWORD_PEPPER", "pepper-2024")
DELETE_GRACE_DAYS = 7

PBKDF2_ITERATIONS = 200_000
PBKDF2_ALGO = "sha256"
SALT_BYTES = 16
USER_ID_BYTES = 6


def hash_password(password, salt=None):
    if password is None:
        password = ""
    if salt is None:
        salt = secrets.token_hex(SALT_BYTES)
    combined = (PASSWORD_PEPPER + str(password)).encode("utf-8")
    derived = hashlib.pbkdf2_hmac(
        PBKDF2_ALGO, combined, salt.encode("utf-8"), PBKDF2_ITERATIONS,
    )
    return "pbkdf2${}${}${}".format(PBKDF2_ITERATIONS, salt, derived.hex())


def verify_password(password, stored_hash):
    if not stored_hash:
        return False
    if password is None:
        password = ""
    if len(stored_hash) == 64 and "$" not in stored_hash:
        legacy = hashlib.sha256(
            (PASSWORD_PEPPER + str(password)).encode()
        ).hexdigest()
        return secrets.compare_digest(legacy, stored_hash)
    try:
        parts = stored_hash.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected = parts[3]
    except (ValueError, IndexError):
        return False
    combined = (PASSWORD_PEPPER + str(password)).encode("utf-8")
    actual = hashlib.pbkdf2_hmac(
        PBKDF2_ALGO, combined, salt.encode("utf-8"), iterations,
    ).hex()
    return secrets.compare_digest(actual, expected)


def generate_user_id():
    return secrets.token_hex(USER_ID_BYTES).upper()


def generate_temp_password():
    return "TMP-" + secrets.token_hex(3).upper()