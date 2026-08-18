"""
database.py
SQLite persistence layer for SupportPilot.

Holds the schema (users / tickets / ai_history / chat_history) plus a small
set of CRUD helpers for tickets. Tickets are persisted here (instead of only
living in st.session_state) so that a ticket raised in the Employee Portal
is visible to technicians in the Support Portal, even in a different
browser session / login.
"""

import sqlite3
import json
from datetime import datetime

DB_NAME = "supportpilot.db"

# Columns tickets should have, beyond the original minimal schema.
# Stored as a (name, sql_type) list so migrate_schema() can ALTER TABLE
# any that are missing on an existing (older) database file.
TICKET_EXTRA_COLUMNS = [
    ("employee_name", "TEXT"),
    ("employee_id", "TEXT"),
    ("sentiment", "TEXT"),
    ("confidence", "TEXT"),
    ("resolution_time", "TEXT"),
    ("recommendation", "TEXT"),
    ("resolution_steps", "TEXT"),      # JSON list
    ("matched_keywords", "TEXT"),      # JSON list
    ("kb_results", "TEXT"),            # JSON list
    ("attempted_recommendation", "TEXT"),  # "Yes" / "No" / "Not specified"
    ("ai_resolved", "TEXT"),           # "Yes" / "No" / "Pending"
    ("source", "TEXT"),                # "AI Assistant" / "Raise Ticket Form"
    ("ai_engine", "TEXT"),
    ("sla_deadline", "TEXT"),
    ("technician_notes", "TEXT"),
    ("activity_log", "TEXT"),          # JSON list of strings
    ("updated_at", "TIMESTAMP"),
]


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def create_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickets(
        ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT,
        description TEXT,
        category TEXT,
        priority TEXT,
        department TEXT,
        status TEXT,
        assigned_to TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER,
        user_query TEXT,
        ai_summary TEXT,
        recommendation TEXT,
        resolved TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        question TEXT,
        answer TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


def migrate_schema():
    """Add any TICKET_EXTRA_COLUMNS missing from an existing tickets table."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(tickets)")
    existing = {row["name"] for row in cursor.fetchall()}

    for col_name, col_type in TICKET_EXTRA_COLUMNS:
        if col_name not in existing:
            cursor.execute(f"ALTER TABLE tickets ADD COLUMN {col_name} {col_type}")

    conn.commit()
    conn.close()


# ---------------------------------------------------
# Ticket CRUD
# ---------------------------------------------------

def insert_ticket(data: dict) -> int:
    """
    Insert a new ticket. `data` may contain any subset of the tickets columns;
    list/dict values (resolution_steps, matched_keywords, kb_results,
    activity_log) are JSON-encoded automatically.
    Returns the new ticket_id.
    """
    row = dict(data)
    for json_field in ("resolution_steps", "matched_keywords", "kb_results", "activity_log"):
        if json_field in row and not isinstance(row[json_field], str):
            row[json_field] = json.dumps(row[json_field])

    row.setdefault("status", "Open")
    row.setdefault("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    row.setdefault("updated_at", row["created_at"])

    columns = list(row.keys())
    placeholders = ",".join("?" for _ in columns)
    sql = f"INSERT INTO tickets ({','.join(columns)}) VALUES ({placeholders})"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, [row[c] for c in columns])
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def _deserialize_ticket(row) -> dict:
    d = dict(row)
    for json_field in ("resolution_steps", "matched_keywords", "kb_results", "activity_log"):
        raw = d.get(json_field)
        if raw:
            try:
                d[json_field] = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                d[json_field] = []
        else:
            d[json_field] = []
    return d


def get_all_tickets() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets ORDER BY ticket_id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [_deserialize_ticket(r) for r in rows]


def get_tickets_for_user(user_id=None, employee_name=None) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    if user_id is not None:
        cursor.execute("SELECT * FROM tickets WHERE user_id=? ORDER BY ticket_id DESC", (user_id,))
    else:
        cursor.execute("SELECT * FROM tickets WHERE employee_name=? ORDER BY ticket_id DESC", (employee_name,))
    rows = cursor.fetchall()
    conn.close()
    return [_deserialize_ticket(r) for r in rows]


def get_ticket(ticket_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets WHERE ticket_id=?", (ticket_id,))
    row = cursor.fetchone()
    conn.close()
    return _deserialize_ticket(row) if row else None


def update_ticket(ticket_id: int, **fields):
    """Update arbitrary columns on a ticket (status, assigned_to, technician_notes, ...)."""
    if not fields:
        return
    row = dict(fields)
    for json_field in ("resolution_steps", "matched_keywords", "kb_results", "activity_log"):
        if json_field in row and not isinstance(row[json_field], str):
            row[json_field] = json.dumps(row[json_field])
    row["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    set_clause = ",".join(f"{k}=?" for k in row.keys())
    sql = f"UPDATE tickets SET {set_clause} WHERE ticket_id=?"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, [*row.values(), ticket_id])
    conn.commit()
    conn.close()


def append_activity(ticket_id: int, entry: str):
    ticket = get_ticket(ticket_id)
    if not ticket:
        return
    log = ticket.get("activity_log") or []
    log.append(entry)
    update_ticket(ticket_id, activity_log=log)


create_database()
migrate_schema()

if __name__ == "__main__":
    print("Database created / migrated successfully!")