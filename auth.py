"""
auth.py
Authentication gate for SupportPilot.

This uses an in-memory user store with hashed passwords — enough to
demonstrate a real login/authentication flow (matching the Users table in
your database schema diagram), but note: the store resets whenever the
Streamlit server restarts, since there's no real database wired up yet.
For persistence across restarts, swap USER_STORE for a database call or
the artifact storage API.
"""
import sqlite3
import hashlib

from database import get_connection, DB_NAME

USER_STORE = {
    "admin": {
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
        "role": "Administrator",
        "display_name": "Admin",
    },
    "employee": {
        "password_hash": hashlib.sha256("employee123".encode()).hexdigest(),
        "role": "Employee",
        "display_name": "Employee",
    },
}


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_login(username, password):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id,name,password,role
        FROM users
        WHERE name=?
    """, (username,))

    user = cursor.fetchone()

    conn.close()

    if user:

        db_id, db_name, db_password, db_role = user

        if db_password == _hash(password):

            return {
                "id": db_id,
                "display_name": db_name,
                "role": db_role
            }

    return None


def get_or_create_user(name: str, role: str = "Employee"):
    """
    Look up a user purely by display name (used by the lightweight sign-in
    form: Name + Employee ID + Department + role picker, no password).
    Creates the user on first sign-in; on later sign-ins, updates their role
    to whatever was picked this time (so the same demo account can be used
    to view either portal).
    """
    name = name.strip()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, role FROM users WHERE name=?", (name,))
    row = cursor.fetchone()

    if row:
        user_id, db_name, _ = row
        cursor.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
        conn.commit()
        conn.close()
        return {"id": user_id, "display_name": db_name, "role": role}

    email = name.lower().replace(" ", ".") + "@supportpilot.com"
    try:
        cursor.execute(
            "INSERT INTO users(name, email, password, role) VALUES (?, ?, ?, ?)",
            (name, email, "", role),
        )
    except sqlite3.IntegrityError:
        # email collision (e.g. two people typed the same name) — make it unique
        cursor.execute(
            "INSERT INTO users(name, email, password, role) VALUES (?, ?, ?, ?)",
            (name, f"{email}.{datetime_suffix()}", "", role),
        )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"id": new_id, "display_name": name, "role": role}


def datetime_suffix():
    from datetime import datetime
    return datetime.now().strftime("%H%M%S")


def register_user(username, password, role="Employee"):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO users(name,email,password,role)
            VALUES(?,?,?,?)
        """,
        (
            username,
            username.lower() + "@supportpilot.com",
            _hash(password),
            role
        ))

        conn.commit()
        conn.close()

        return True

    except sqlite3.IntegrityError:
        conn.close()
        return False