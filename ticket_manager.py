import sqlite3

DB_NAME = "supportpilot.db"

# Function to get a connection to the database

def get_connection():
    return sqlite3.connect(DB_NAME)
def create_ticket(
    user_id,
    title,
    description,
    category,
    priority,
    department,
    status="Open",
    assigned_to=None
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO tickets(
            user_id,
            title,
            description,
            category,
            priority,
            department,
            status,
            assigned_to
        )
        VALUES(?,?,?,?,?,?,?,?)
    """, (
        user_id,
        title,
        description,
        category,
        priority,
        department,
        status,
        assigned_to
    ))

    conn.commit()
    conn.close()

#Retrieve all tickets

def get_all_tickets():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tickets")

    tickets = cursor.fetchall()

    conn.close()

    return tickets
#Retrieve tickets for one user
def get_user_tickets(user_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM tickets
        WHERE user_id=?
    """, (user_id,))

    tickets = cursor.fetchall()

    conn.close()

    return tickets

#Update ticket status
def update_ticket_status(ticket_id, status):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE tickets
        SET status=?
        WHERE ticket_id=?
    """, (status, ticket_id))

    conn.commit()
    conn.close()
#Assign a ticket
def assign_ticket(ticket_id, technician):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE tickets
        SET assigned_to=?
        WHERE ticket_id=?
    """, (technician, ticket_id))

    conn.commit()
    conn.close()