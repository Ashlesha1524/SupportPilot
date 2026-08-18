import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
from analyzer import find_similar_tickets, generate_email_notification
from ollama_analyzer import analyze_ticket
from chatbot import new_chat_state, handle_message
from auth import verify_login, register_user, get_or_create_user
import database as db

# Roles that get the Support Portal instead of the Employee Portal.
STAFF_ROLES = {"Administrator", "Support", "Technician"}

STATUS_OPTIONS = ["Open", "In Progress", "Resolved", "Escalated"]

# Simple shared passcode so not just anyone can sign in as a Support Admin.
# Fine for a local demo — replace with real auth before deploying for real.
ADMIN_PASSCODE = "admin123"

PRIORITY_COLORS = {
    "Critical": "#e03131",
    "High": "#f08c00",
    "Medium": "#1971c2",
    "Low": "#2f9e44",
}


def priority_badge(priority: str) -> str:
    color = PRIORITY_COLORS.get(priority, "#495057")
    return (
        f'<span style="background-color:{color}; color:white; padding:4px 12px; '
        f'border-radius:12px; font-weight:600; font-size:0.85rem;">{priority}</span>'
    )


def check_ollama_reachable() -> bool:
    try:
        import ollama as _probe
        _probe.list()
        return True
    except Exception:
        return False


def run_agent_pipeline():
    """Fake the multi-agent trace from the architecture diagram, one stage at a time."""
    stages = [
        ("Diagnosis Agent", "Analyzing ticket description..."),
        ("Knowledge Retrieval Agent", "Searching knowledge base for similar issues..."),
        ("Resolution Agent", "Generating troubleshooting steps..."),
        ("Escalation Agent", "Checking if human escalation is required..."),
    ]
    placeholder = st.empty()
    log_lines = []
    for name, msg in stages:
        log_lines.append(f"**{name}** — {msg}")
        placeholder.markdown("  \n".join(log_lines))
        time.sleep(0.6)
    log_lines[-1] = log_lines[-1].replace(
        "Checking if human escalation is required...",
        "Checking if human escalation is required... done",
    )
    placeholder.markdown("  \n".join(log_lines))
    time.sleep(0.3)
    placeholder.empty()

# ---------------------------------------------------
# Page Configuration
# ---------------------------------------------------

st.set_page_config(
    page_title="SupportPilot",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------
# Session State Initialization
# ---------------------------------------------------

if "current_analysis" not in st.session_state:
    st.session_state.current_analysis = None   # analysis of the ticket just raised

if "current_ticket_meta" not in st.session_state:
    st.session_state.current_ticket_meta = None  # title/description of that ticket

if "similar_tickets" not in st.session_state:
    st.session_state.similar_tickets = []

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {"role": "assistant", "content": "Hi! Describe the issue you're facing and I'll help diagnose it."}
    ]

if "chat_state" not in st.session_state:
    st.session_state.chat_state = new_chat_state()

# ---------------------------------------------------
# Authentication Gate
# ---------------------------------------------------

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "current_user" not in st.session_state:
    st.session_state.current_user = None

if not st.session_state.authenticated:

    st.markdown(
        """
        <style>
        #MainMenu, header, footer {visibility: hidden;}

        .stApp {
            background-color: #f2f4f8;
        }

        .block-container {
            max-width: 560px;
            margin: 0 auto;
            padding-top: 3rem;
            padding-bottom: 3rem;
        }

        .login-logo {
            width: 68px;
            height: 68px;
            border-radius: 18px;
            background: linear-gradient(135deg, #1971c2, #0b3d78);
            color: #ffffff !important;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 1.7rem;
            margin: 0 auto 1.1rem auto;
        }

        .login-title {
            text-align: center;
            font-size: 2rem;
            font-weight: 700;
            color: #1a1a2e !important;
            margin-bottom: 0.2rem;
        }

        .login-subtitle {
            text-align: center;
            color: #5f6b7a !important;
            font-size: 1rem;
            margin-bottom: 1.8rem;
        }

        /* ---- The card itself ---- */
        div[data-testid="stForm"] {
            background-color: #ffffff !important;
            padding: 2.4rem 2.6rem 1.6rem 2.6rem;
            border-radius: 20px;
            box-shadow: 0 14px 36px rgba(20, 30, 60, 0.12);
            border: 1px solid #eef0f3;
        }

        /* ---- Tabs: force readable colors in both light & dark mode ---- */
        div[data-testid="stTabs"] {
            margin-bottom: 0.5rem;
        }
        div[data-testid="stTabs"] button[role="tab"] p {
            color: #6c757d !important;
            font-weight: 600;
            font-size: 1.05rem;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] p {
            color: #1971c2 !important;
        }
        div[data-baseweb="tab-highlight"] {
            background-color: #1971c2 !important;
        }
        div[data-baseweb="tab-border"] {
            background-color: #e2e5ea !important;
        }

        /* ---- Input labels and fields: force readable regardless of theme ---- */
        div[data-testid="stForm"] label p {
            color: #33394a !important;
            font-weight: 600;
            font-size: 0.95rem;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] input {
            background-color: #f8f9fb !important;
            color: #1a1a2e !important;
            caret-color: #1971c2 !important;
            border: 1px solid #d5d9e0 !important;
            border-radius: 8px;
            padding: 0.6rem 0.8rem;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] input::placeholder {
            color: #9aa1ac !important;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] input:focus {
            border-color: #1971c2 !important;
            box-shadow: 0 0 0 1px #1971c2 !important;
        }

        /* ---- Select / dropdown fields: force readable regardless of theme ---- */
        div[data-testid="stForm"] div[data-baseweb="select"] > div {
            background-color: #f8f9fb !important;
            color: #1a1a2e !important;
            border: 1px solid #d5d9e0 !important;
            border-radius: 8px;
        }
        div[data-testid="stForm"] div[data-baseweb="select"] span {
            color: #1a1a2e !important;
        }
        /* the select has a hidden input for keyboard a11y — neutralize it so it
           never renders as a stray bordered box floating inside the control */
        div[data-testid="stForm"] div[data-baseweb="select"] input {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
        }
        /* the options popover renders outside the form in a portal, so this is unscoped */
        ul[data-baseweb="menu"] {
            background-color: #ffffff !important;
        }
        ul[data-baseweb="menu"] li {
            color: #1a1a2e !important;
        }
        ul[data-baseweb="menu"] li:hover {
            background-color: #eef3fb !important;
        }

        /* ---- Radio options (Sign in as) ---- */
        div[data-testid="stForm"] label[data-baseweb="radio"] div {
            color: #1a1a2e !important;
        }
        div[data-testid="stRadio"] label[data-baseweb="radio"] div {
            color: #1a1a2e !important;
            font-weight: 600;
        }

        /* ---- Submit button ---- */
        div[data-testid="stFormSubmitButton"] button {
            background-color: #1971c2 !important;
            color: #ffffff !important;
            border-radius: 8px;
            border: none;
            font-weight: 600;
            font-size: 1.02rem;
            padding: 0.6rem 0;
            margin-top: 0.4rem;
        }
        div[data-testid="stFormSubmitButton"] button:hover {
            background-color: #0b3d78 !important;
            color: #ffffff !important;
        }
        div[data-testid="stFormSubmitButton"] button p {
            color: #ffffff !important;
        }

        /* ---- Caption text below the card (demo accounts, etc.) ---- */
        div[data-testid="stCaptionContainer"] p {
            color: #5f6b7a !important;
            text-align: center;
        }

        /* ---- Alerts (error/warning/success) keep readable text ---- */
        div[data-testid="stAlertContentError"] p,
        div[data-testid="stAlertContentWarning"] p,
        div[data-testid="stAlertContentSuccess"] p {
            color: inherit !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="login-logo">SP</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-title">SupportPilot</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="login-subtitle">Sign in to raise tickets or triage the queue</div>',
        unsafe_allow_html=True,
    )

    # Outside the form so the Department / passcode fields below can react
    # immediately when this changes (widgets inside a form only update on submit).
    sign_in_as = st.radio(
        "Sign in as",
        ["Employee", "Support Admin"],
        horizontal=True,
        label_visibility="collapsed",
    )

    with st.form("signin_form"):
        name = st.text_input("Name")
        employee_id = st.text_input("Employee ID")

        department = None
        admin_passcode = ""
        if sign_in_as == "Support Admin":
            department = st.selectbox(
                "Department you support",
                ["Select a department...", "IT", "Network", "HR", "Finance", "Hardware"],
                index=0,
            )
            admin_passcode = st.text_input("Admin passcode", type="password")

        continue_clicked = st.form_submit_button("Continue →", use_container_width=True)

    if continue_clicked:
        if not name.strip() or not employee_id.strip():
            st.warning("Please enter your name and employee ID.")
        elif sign_in_as == "Support Admin" and department == "Select a department...":
            st.warning("Please choose which department you support.")
        elif sign_in_as == "Support Admin" and admin_passcode != ADMIN_PASSCODE:
            st.error("Incorrect admin passcode. Ask your IT lead for it if you don't have it.")
        else:
            role = "Administrator" if sign_in_as == "Support Admin" else "Employee"
            user = get_or_create_user(name, role)
            st.session_state.authenticated = True
            st.session_state.current_user = {
                **user,
                "employee_id": employee_id.strip(),
                "department": department,
            }
            st.session_state.chat_state = new_chat_state(
                employee_name=user["display_name"],
                employee_id=employee_id.strip(),
            )
            st.rerun()

    st.caption(
        "New here? Just fill in your details and hit Continue — your account is created "
        "automatically, whether you're a first-time employee or a first-time Support Admin."
    )

    st.stop()  # nothing below this line runs until the person signs in

# ---------------------------------------------------
# Sidebar
# ---------------------------------------------------

is_staff = st.session_state.current_user["role"] in STAFF_ROLES

st.sidebar.title("SupportPilot")
st.sidebar.caption("Support Portal" if is_staff else "Employee Portal")
st.sidebar.markdown("---")
st.sidebar.write(f"Signed in as **{st.session_state.current_user['display_name']}**")
st.sidebar.caption(st.session_state.current_user["role"])
if not is_staff and st.session_state.current_user.get("employee_id"):
    st.sidebar.caption(f"Employee ID: {st.session_state.current_user['employee_id']}")
if is_staff and st.session_state.current_user.get("department"):
    st.sidebar.caption(f"Supports: {st.session_state.current_user['department']}")
if st.sidebar.button("Log Out", use_container_width=True):
    st.session_state.authenticated = False
    st.session_state.current_user = None
    st.rerun()
st.sidebar.markdown("---")

if is_staff:
    nav_options = ["Home", "Ticket Queue", "Dashboard", "About"]
else:
    nav_options = ["Home", "AI Assistant", "Raise Ticket", "My Tickets", "About"]

if "nav_page" not in st.session_state or st.session_state.nav_page not in nav_options:
    st.session_state.nav_page = "Home"

# A button elsewhere (e.g. Home page quick actions) can request a page change
# by setting nav_target + st.rerun().
if "nav_target" in st.session_state:
    target = st.session_state.pop("nav_target")
    st.session_state.nav_page = target if target in nav_options else "Home"

# Plain buttons instead of st.radio: each run, every button's active/inactive
# style is recomputed fresh from nav_page (the single source of truth), so
# there's no separate widget-echo state that can visually desync from the
# actual page — the class of bug st.radio is prone to when its value is
# changed programmatically rather than by a direct user click on it.
for opt in nav_options:
    is_active = opt == st.session_state.nav_page
    if st.sidebar.button(
        opt,
        key=f"navbtn_{opt}",
        use_container_width=True,
        type="primary" if is_active else "secondary",
    ):
        st.session_state.nav_page = opt
        st.rerun()

page = st.session_state.nav_page

st.sidebar.markdown("---")
total_tickets = len(db.get_all_tickets())
st.sidebar.caption(f"Total tickets in system: {total_tickets}")
st.sidebar.caption("Version 1.0")

# ---------------------------------------------------
# HOME
# ---------------------------------------------------

if page == "Home":

    display_name = st.session_state.current_user["display_name"]
    first_name = display_name.split()[0] if display_name else display_name

    if is_staff:
        # ================= SUPPORT PORTAL HOME =================
        all_tickets = db.get_all_tickets()
        total = len(all_tickets)
        open_count = sum(1 for t in all_tickets if t["status"] == "Open")
        in_progress = sum(1 for t in all_tickets if t["status"] == "In Progress")
        escalated = sum(1 for t in all_tickets if t["status"] == "Escalated")
        resolved = sum(1 for t in all_tickets if t["status"] == "Resolved")
        resolution_rate = round((resolved / total) * 100) if total else 0
        attempted_first = sum(1 for t in all_tickets if t.get("attempted_recommendation") == "Yes")

        st.markdown(
            f"""
            <div style="padding:1.75rem 2rem;border-radius:16px;margin-bottom:1.25rem;
                 background:linear-gradient(120deg, rgba(224,49,49,0.14), rgba(25,113,194,0.12));
                 border:1px solid rgba(255,255,255,0.08);">
              <div style="font-size:0.78rem;letter-spacing:0.12em;text-transform:uppercase;color:#9aa1ac;">
                Support Portal
              </div>
              <div style="font-size:2rem;font-weight:700;margin-top:0.3rem;">
                Welcome back, {first_name}
              </div>
              <div style="color:#c7cdd6;margin-top:0.35rem;font-size:0.95rem;">
                {open_count} open · {in_progress} in progress · {escalated} escalated · {resolution_rate}% resolved overall
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tiles = [
            ("Total Tickets", total, PRIORITY_COLORS["Medium"]),
            ("Open", open_count, PRIORITY_COLORS["High"]),
            ("Escalated", escalated, PRIORITY_COLORS["Critical"]),
            ("Tried AI Steps First", attempted_first, PRIORITY_COLORS["Low"]),
        ]
        cols = st.columns(4)
        for col, (label, value, color) in zip(cols, tiles):
            with col:
                st.markdown(
                    f"""
                    <div style="border-left:4px solid {color}; padding:0.85rem 1rem;
                         background:rgba(255,255,255,0.03); border-radius:8px; min-height:88px;">
                      <div style="font-size:0.78rem; color:#9aa1ac;">{label}</div>
                      <div style="font-size:1.7rem; font-weight:700; margin-top:0.2rem;">{value}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.write("")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🎫 Go to Ticket Queue", use_container_width=True):
                st.session_state.nav_target = "Ticket Queue"
                st.rerun()
        with c2:
            if st.button("📊 View Dashboard", use_container_width=True):
                st.session_state.nav_target = "Dashboard"
                st.rerun()

        st.divider()
        st.markdown("### Needs attention")
        urgent = [t for t in all_tickets if t["status"] in ("Open", "Escalated")]
        priority_rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        urgent.sort(key=lambda t: priority_rank.get(t["priority"], 4))

        if not urgent:
            st.info("Nothing urgent right now — the queue is clear.")
        else:
            for t in urgent[:5]:
                row = st.columns([5, 1.3, 1.3])
                row[0].markdown(f"**TK-{t['ticket_id']:04d}** — {t['title']}")
                row[1].markdown(priority_badge(t["priority"]), unsafe_allow_html=True)
                row[2].caption(t["status"])
            if len(urgent) > 5:
                st.caption(f"+ {len(urgent) - 5} more in the queue.")

    else:
        # ================= EMPLOYEE PORTAL HOME =================
        my_tickets = db.get_tickets_for_user(user_id=st.session_state.current_user["id"])
        my_open = sum(1 for t in my_tickets if t["status"] in ("Open", "In Progress"))
        my_resolved = sum(1 for t in my_tickets if t["status"] == "Resolved")

        st.markdown(
            f"""
            <div style="padding:1.75rem 2rem;border-radius:16px;margin-bottom:1.25rem;
                 background:linear-gradient(120deg, rgba(25,113,194,0.16), rgba(47,158,68,0.10));
                 border:1px solid rgba(255,255,255,0.08);">
              <div style="font-size:0.78rem;letter-spacing:0.12em;text-transform:uppercase;color:#9aa1ac;">
                Employee Portal
              </div>
              <div style="font-size:2rem;font-weight:700;margin-top:0.3rem;">
                Hi {first_name}, what's going on?
              </div>
              <div style="color:#c7cdd6;margin-top:0.35rem;font-size:0.95rem;">
                Describe your issue and get instant AI-guided steps — raise a ticket only if it's still not fixed.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                """
                <div style="border-left:4px solid #1971c2; padding:0.9rem 1rem;
                     background:rgba(255,255,255,0.03); border-radius:8px; min-height:96px;">
                  <div style="font-weight:600;">💬 Ask the AI Assistant</div>
                  <div style="font-size:0.82rem; color:#9aa1ac; margin-top:0.25rem;">
                    Chat through your issue and get suggested fixes in real time.
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open AI Assistant", use_container_width=True, key="home_ai_btn"):
                st.session_state.nav_target = "AI Assistant"
                st.rerun()
        with c2:
            st.markdown(
                """
                <div style="border-left:4px solid #f08c00; padding:0.9rem 1rem;
                     background:rgba(255,255,255,0.03); border-radius:8px; min-height:96px;">
                  <div style="font-weight:600;">🎫 Raise a Ticket</div>
                  <div style="font-size:0.82rem; color:#9aa1ac; margin-top:0.25rem;">
                    Fill in the details directly if you already know it needs support.
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open Raise Ticket", use_container_width=True, key="home_raise_btn"):
                st.session_state.nav_target = "Raise Ticket"
                st.rerun()
        with c3:
            st.markdown(
                f"""
                <div style="border-left:4px solid #2f9e44; padding:0.9rem 1rem;
                     background:rgba(255,255,255,0.03); border-radius:8px; min-height:96px;">
                  <div style="font-weight:600;">📋 My Tickets</div>
                  <div style="font-size:0.82rem; color:#9aa1ac; margin-top:0.25rem;">
                    {my_open} open · {my_resolved} resolved so far.
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("View My Tickets", use_container_width=True, key="home_mytickets_btn"):
                st.session_state.nav_target = "My Tickets"
                st.rerun()

        st.divider()
        if my_tickets:
            latest = my_tickets[0]
            st.markdown("### Your most recent ticket")
            row = st.columns([4, 1.5, 1.5, 1.5])
            row[0].markdown(f"**TK-{latest['ticket_id']:04d}** — {latest['title']}")
            row[1].markdown(priority_badge(latest["priority"]), unsafe_allow_html=True)
            row[2].caption(latest["status"])
            row[3].caption(latest.get("department") or "")
        else:
            st.info("You haven't raised any tickets yet — try the AI Assistant above.")

    # ---- Live system status strip (same checks as About page) ----
    st.write("")
    ollama_ok = check_ollama_reachable()
    db_ok = True
    try:
        db.get_all_tickets()
    except Exception:
        db_ok = False
    st.caption(
        f"{'🟢' if ollama_ok else '🟡'} Ollama service: {'reachable' if ollama_ok else 'not reachable (using rule-based fallback)'}"
        f"   ·   {'🟢' if db_ok else '🔴'} Database: {'connected' if db_ok else 'not connected'}"
    )

# ---------------------------------------------------
# AI ASSISTANT (CHATBOT)
# ---------------------------------------------------

elif page == "AI Assistant":

    st.title("AI Assistant")
    st.write("Chat with SupportPilot to describe your issue and get help in real time.")
    st.divider()

    # Render chat history
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Describe your issue...")

    if user_input:
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking... (first response on a cold local model can take up to 30-45s)"):
                reply, updated_state, ticket_ready = handle_message(st.session_state.chat_state, user_input)
        st.session_state.chat_state = updated_state

        if ticket_ready:
            analysis = updated_state["analysis"]
            description = updated_state["description"]
            employee_name = updated_state["employee_name"] or "Unknown"
            employee_id = updated_state["employee_id"] or "N/A"
            attempted = updated_state.get("attempted_recommendation", "Not specified")

            sla_hours = {"Critical": 1, "High": 2, "Medium": 4, "Low": 24}.get(analysis["priority"], 4)
            deadline = datetime.now() + timedelta(hours=sla_hours)
            now_str = datetime.now().strftime("%H:%M:%S")

            new_ticket_id = db.insert_ticket({
                "user_id": st.session_state.current_user["id"],
                "employee_name": employee_name,
                "employee_id": employee_id,
                "title": description[:40] + ("..." if len(description) > 40 else ""),
                "description": description,
                "category": analysis["category"],
                "sentiment": analysis["sentiment"],
                "priority": analysis["priority"],
                "confidence": analysis["confidence"],
                "department": analysis["department"],
                "resolution_time": analysis["resolution_time"],
                "recommendation": analysis["recommendation"],
                "resolution_steps": analysis["resolution_steps"],
                "matched_keywords": analysis["matched_keywords"],
                "kb_results": analysis["kb_results"],
                "attempted_recommendation": attempted,
                "ai_resolved": "No",  # they're raising a ticket, so the AI suggestion alone didn't resolve it
                "source": "AI Assistant",
                "ai_engine": analysis.get("ai_engine", "rule-based"),
                "status": "Open",
                "sla_deadline": deadline.strftime("%Y-%m-%d %H:%M"),
                "activity_log": [
                    f"{now_str} — Ticket created via AI Assistant chat by {employee_name}",
                    f"{now_str} — AI classified as {analysis['category']} / {analysis['priority']} priority",
                    f"{now_str} — Employee reported recommendation attempted: {attempted}",
                    f"{now_str} — Routed to {analysis['department']}",
                ],
            })

            reply += (
                f"\n\nYour ticket **TK-{new_ticket_id:04d}** has been created and routed to the "
                f"{analysis['department']}. You can track it under **My Tickets**."
            )
            # reset the conversation so the person can raise another ticket right after
            st.session_state.chat_state = new_chat_state(
                employee_name=st.session_state.current_user["display_name"],
                employee_id=st.session_state.current_user.get("employee_id"),
            )

        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()

# ---------------------------------------------------
# RAISE TICKET
# ---------------------------------------------------

elif page == "Raise Ticket":

    st.title("Raise Support Ticket")
    st.write(
        "Describe your issue and get an AI analysis first. If the suggested "
        "steps don't resolve it, you can submit the ticket straight to the support team."
    )
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        employee_name = st.text_input("Employee Name", value=st.session_state.current_user["display_name"])
        employee_id = st.text_input("Employee ID", value=st.session_state.current_user.get("employee_id", ""))
        department = st.selectbox(
            "Department",
            ["IT", "Network", "HR", "Finance", "Hardware"],
            index=["IT", "Network", "HR", "Finance", "Hardware"].index(
                st.session_state.current_user.get("department", "IT")
            ) if st.session_state.current_user.get("department") in ["IT", "Network", "HR", "Finance", "Hardware"] else 0,
        )
    with col2:
        ticket_title = st.text_input("Ticket Title")
        st.file_uploader("Upload Screenshot (optional)", type=["png", "jpg", "jpeg", "pdf"])

    description = st.text_area("Describe Your Issue", height=150)

    analyze_clicked = st.button("Analyze with AI", type="primary", use_container_width=True)

    if analyze_clicked:
        if not description.strip():
            st.warning("Please describe your issue before analyzing.")
        else:
            # Look for similar past tickets, sourced from the persistent ticket store
            similar = find_similar_tickets(description, db.get_all_tickets())

            run_agent_pipeline()
            try:
                with st.spinner("Waiting on the AI model — first response on a cold local model can take up to 30-45s..."):
                    analysis = analyze_ticket(description, ticket_title)
            except Exception as e:
                st.error(f"Analysis failed unexpectedly: {e}")
                st.stop()

            if analysis.get("ai_engine") == "rule-based-fallback":
                st.caption(
                    f"⚠️ Ollama wasn't used for this one — {analysis.get('ai_engine_detail', 'unknown reason')}. "
                    "Fell back to the rule-based classifier so you still got a result."
                )

            sla_hours = {"Critical": 1, "High": 2, "Medium": 4, "Low": 24}.get(analysis["priority"], 4)
            deadline = datetime.now() + timedelta(hours=sla_hours)

            st.session_state.current_analysis = analysis
            st.session_state.current_ticket_meta = {
                "employee_name": employee_name or "Unknown",
                "employee_id": employee_id or "N/A",
                "title": ticket_title or "Untitled Issue",
                "description": description,
                "department_selected": department,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "sla_deadline": deadline,
            }
            st.session_state.similar_tickets = similar
            st.session_state.ticket_submitted = False

            st.success("Ticket analyzed successfully!")

    # ---- AI Ticket Analysis section (shown once a ticket has been analyzed) ----
    if st.session_state.current_analysis:
        analysis = st.session_state.current_analysis
        meta = st.session_state.current_ticket_meta

        st.divider()
        st.subheader("AI Ticket Analysis")
        _engine_labels = {
            "ollama": "🧠 Analyzed by Ollama (llama3.2:3b)",
            "rule-based-fallback": "⚠️ Ollama unavailable — used rule-based fallback",
            "rule-based": "Analyzed by rule-based classifier",
        }
        st.caption(_engine_labels.get(analysis.get("ai_engine", "rule-based"), "Analyzed by rule-based classifier"))

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Category", analysis["category"])
            st.metric("Sentiment", analysis["sentiment"])
        with c2:
            st.markdown("**Priority**")
            st.markdown(priority_badge(analysis["priority"]), unsafe_allow_html=True)
            st.write("")
            st.metric("Department", analysis["department"])
        with c3:
            st.metric("Confidence", analysis["confidence"])
            st.metric("Est. Resolution Time", analysis["resolution_time"])

        # ---- SLA countdown ----
        remaining = meta["sla_deadline"] - datetime.now()
        remaining_mins = max(int(remaining.total_seconds() // 60), 0)
        st.markdown(
            f"**SLA Deadline (if escalated):** {meta['sla_deadline'].strftime('%I:%M %p')} "
            f"(~{remaining_mins} min remaining)"
        )

        st.info(analysis["recommendation"])

        # ---- Explainability ----
        engine = analysis.get("ai_engine", "rule-based")
        with st.expander("Why did the AI classify it this way?"):
            st.markdown(f"**Category -> {analysis['category']}**")
            if analysis.get("matched_keywords"):
                st.write("Matched signal words: " + ", ".join(f"`{k}`" for k in analysis["matched_keywords"]))
            elif engine == "rule-based":
                st.write("No strong keyword match — defaulted to Software.")

            st.markdown(f"**Priority -> {analysis['priority']}**")
            if analysis.get("priority_reason"):
                st.write("Based on: " + ", ".join(f"`{r}`" for r in analysis["priority_reason"]))

            if engine == "ollama":
                st.caption("Classified by a local LLM (Ollama, llama3.2:3b).")
            elif engine == "rule-based-fallback":
                st.caption(
                    "Ollama wasn't reachable, so this fell back to the transparent "
                    "rule-based classifier."
                )
            else:
                st.caption(
                    "This is a transparent, rule-based classifier for demo purposes — "
                    "in production this step would be a fine-tuned LLM classification call."
                )

        # ---- Knowledge Base retrieval ----
        if analysis["kb_results"]:
            st.markdown("#### Knowledge Base Articles Retrieved")
            for article, score in analysis["kb_results"]:
                st.markdown(
                    f"**{article['title']}** — *{score}% relevance*  \n"
                    f"{article['content']}  \n"
                    f"<span style='color:gray; font-size:0.85em;'>Last updated {article['last_updated']}</span>",
                    unsafe_allow_html=True,
                )

        # ---- Similar past tickets (lightweight RAG-style retrieval) ----
        if st.session_state.similar_tickets:
            st.markdown("#### Similar Tickets Found")
            st.caption("Retrieved from past tickets using text similarity — mirrors the Knowledge Retrieval step in the architecture.")
            for ticket, score in st.session_state.similar_tickets:
                st.markdown(
                    f"- **TK-{ticket['ticket_id']:04d}** — {ticket['title']} "
                    f"({score}% similar, status: {ticket['status']})"
                )

        st.markdown("#### Suggested Resolution Steps")
        for i, step in enumerate(analysis["resolution_steps"], start=1):
            st.markdown(f"**{i}.** {step}")

        st.markdown("#### Ticket Summary")
        st.success(analysis["summary"])

        st.divider()
        st.write("**Have you tried the suggested steps above?**")
        attempted = st.radio(
            "Attempted check",
            ["Not yet", "Yes, I tried them"],
            horizontal=True,
            label_visibility="collapsed",
            key="attempted_radio",
        )

        resolved = None
        if attempted == "Yes, I tried them":
            st.write("**Did that resolve the issue?**")
            resolved = st.radio(
                "Resolution check",
                ["Yes", "No"],
                horizontal=True,
                label_visibility="collapsed",
                key="resolved_radio",
            )

        if resolved == "Yes":
            st.success("Great! Glad the suggested steps sorted it out — no need to raise a ticket.")
        else:
            st.warning("Let's get this in front of the support team.")
            if st.session_state.get("ticket_submitted"):
                st.info("This ticket has already been submitted to the support team.")
            elif st.button("Submit Ticket to Support Team", type="primary", use_container_width=True):
                attempted_value = "Yes" if attempted == "Yes, I tried them" else "No"
                now_str = datetime.now().strftime("%H:%M:%S")
                new_ticket_id = db.insert_ticket({
                    "user_id": st.session_state.current_user["id"],
                    "employee_name": meta["employee_name"],
                    "employee_id": meta["employee_id"],
                    "title": meta["title"],
                    "description": meta["description"],
                    "category": analysis["category"],
                    "sentiment": analysis["sentiment"],
                    "priority": analysis["priority"],
                    "confidence": analysis["confidence"],
                    "department": analysis["department"],
                    "resolution_time": analysis["resolution_time"],
                    "recommendation": analysis["recommendation"],
                    "resolution_steps": analysis["resolution_steps"],
                    "matched_keywords": analysis["matched_keywords"],
                    "kb_results": analysis["kb_results"],
                    "attempted_recommendation": attempted_value,
                    "ai_resolved": "No",
                    "source": "Raise Ticket Form",
                    "ai_engine": analysis.get("ai_engine", "rule-based"),
                    "status": "Open",
                    "sla_deadline": meta["sla_deadline"].strftime("%Y-%m-%d %H:%M"),
                    "activity_log": [
                        f"{now_str} — Ticket created by {meta['employee_name']}",
                        f"{now_str} — AI classified as {analysis['category']} / {analysis['priority']} priority",
                        f"{now_str} — Employee reported recommendation attempted: {attempted_value}",
                        f"{now_str} — Routed to {analysis['department']}",
                    ],
                })
                st.session_state.ticket_submitted = True
                st.success(f"Ticket **TK-{new_ticket_id:04d}** submitted to the {analysis['department']}.")
                st.rerun()

# ---------------------------------------------------
# MY TICKETS (Employee Portal)
# ---------------------------------------------------

elif page == "My Tickets":

    st.title("My Tickets")
    st.write("Tickets you've raised, and their current status with the support team.")
    st.divider()

    my_tickets = db.get_tickets_for_user(user_id=st.session_state.current_user["id"])

    if not my_tickets:
        st.info("You haven't raised any tickets yet. Try the **AI Assistant** or **Raise Ticket** page.")
    else:
        for t in my_tickets:
            header = f"TK-{t['ticket_id']:04d} — {t['title']}  ·  {t['status']}"
            with st.expander(header):
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Category:** {t['category']}")
                c1.markdown(priority_badge(t['priority']), unsafe_allow_html=True)
                c2.markdown(f"**Department:** {t['department']}")
                c2.markdown(f"**Status:** {t['status']}")
                c3.markdown(f"**Attempted AI steps first:** {t.get('attempted_recommendation') or 'Not specified'}")
                c3.markdown(f"**Raised via:** {t.get('source') or 'N/A'}")

                st.write(t["description"])

                if t.get("recommendation"):
                    st.info(t["recommendation"])

                if t.get("resolution_steps"):
                    st.markdown("**Suggested steps:**")
                    for i, step in enumerate(t["resolution_steps"], start=1):
                        st.markdown(f"{i}. {step}")

                if t.get("technician_notes"):
                    st.markdown("**Note from support:**")
                    st.success(t["technician_notes"])

# ---------------------------------------------------
# TICKET QUEUE (Support Portal)
# ---------------------------------------------------

elif page == "Ticket Queue":

    st.title("Ticket Queue")
    st.write("All tickets raised by employees, with the AI analysis and recommendations already shown to them.")
    st.divider()

    all_tickets = db.get_all_tickets()

    if not all_tickets:
        st.info("No tickets in the system yet.")
    else:
        status_filter = st.multiselect("Filter by status", STATUS_OPTIONS, default=STATUS_OPTIONS)
        visible = [t for t in all_tickets if t["status"] in status_filter]

        st.caption(f"Showing {len(visible)} of {len(all_tickets)} tickets.")

        for t in visible:
            attempted = t.get("attempted_recommendation") or "Not specified"
            attempted_flag = "✅ Attempted" if attempted == "Yes" else ("⚠️ Not attempted" if attempted == "No" else "— Not specified")
            header = f"TK-{t['ticket_id']:04d} — {t['title']}  ·  {t['priority']}  ·  {t['status']}  ·  {attempted_flag}"

            with st.expander(header):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f"**Employee:** {t.get('employee_name') or 'Unknown'} ({t.get('employee_id') or 'N/A'})")
                    st.markdown(f"**Category:** {t['category']}")
                    st.markdown(f"**Sentiment:** {t.get('sentiment') or '—'}")
                with c2:
                    st.markdown("**Priority**")
                    st.markdown(priority_badge(t['priority']), unsafe_allow_html=True)
                    st.markdown(f"**Department:** {t['department']}")
                with c3:
                    st.markdown(f"**Source:** {t.get('source') or 'N/A'}")
                    st.markdown(f"**Confidence:** {t.get('confidence') or '—'}")
                    st.markdown(f"**Raised:** {t.get('created_at') or '—'}")

                _engine_labels = {
                    "ollama": "🧠 Ollama (llama3.2:3b)",
                    "rule-based-fallback": "⚠️ Rule-based (Ollama was unavailable)",
                    "rule-based": "Rule-based classifier",
                }
                st.caption(
                    "AI engine: " + _engine_labels.get(t.get("ai_engine") or "rule-based", "Rule-based classifier")
                )

                st.markdown("**Employee's description:**")
                st.write(t["description"])

                st.markdown(f"**Recommendation already shown to employee:** {t.get('recommendation') or '—'}")

                if t.get("resolution_steps"):
                    st.markdown("**Suggested resolution steps shown to employee:**")
                    for i, step in enumerate(t["resolution_steps"], start=1):
                        st.markdown(f"{i}. {step}")

                if attempted == "Yes":
                    st.warning("Employee reports they **already tried** the steps above — they did not resolve the issue.")
                elif attempted == "No":
                    st.info("Employee has **not yet tried** the suggested steps.")
                else:
                    st.caption("No attempted-recommendation data recorded for this ticket.")

                if t.get("kb_results"):
                    with st.expander("Knowledge base articles retrieved"):
                        for article, score in t["kb_results"]:
                            st.markdown(f"**{article['title']}** — {score}% relevance")

                if t.get("activity_log"):
                    with st.expander("Activity log"):
                        for entry in t["activity_log"]:
                            st.write(entry)

                st.divider()
                st.markdown("**Technician actions**")
                col_a, col_b = st.columns(2)
                with col_a:
                    new_status = st.selectbox(
                        "Update status",
                        STATUS_OPTIONS,
                        index=STATUS_OPTIONS.index(t["status"]) if t["status"] in STATUS_OPTIONS else 0,
                        key=f"status_{t['ticket_id']}",
                    )
                with col_b:
                    assign_to = st.text_input(
                        "Assign to",
                        value=t.get("assigned_to") or st.session_state.current_user["display_name"],
                        key=f"assign_{t['ticket_id']}",
                    )
                notes = st.text_area(
                    "Technician notes (visible to the employee)",
                    value=t.get("technician_notes") or "",
                    key=f"notes_{t['ticket_id']}",
                )

                if st.button("Save changes", key=f"save_{t['ticket_id']}"):
                    db.update_ticket(
                        t["ticket_id"],
                        status=new_status,
                        assigned_to=assign_to,
                        technician_notes=notes,
                    )
                    db.append_activity(
                        t["ticket_id"],
                        f"{datetime.now().strftime('%H:%M:%S')} — "
                        f"{st.session_state.current_user['display_name']} updated status to {new_status}",
                    )
                    st.success("Ticket updated.")
                    st.rerun()

# ---------------------------------------------------
# DASHBOARD
# ---------------------------------------------------

elif page == "Dashboard":

    st.title("Dashboard")
    st.write("Live analytics computed from all tickets in the system.")
    st.divider()

    tickets = db.get_all_tickets()

    if not tickets:
        st.info("No tickets yet.")
    else:
        df = pd.DataFrame(tickets)

        total = len(df)
        resolved = (df["status"] == "Resolved").sum()
        escalated = (df["status"] == "Escalated").sum()
        resolution_rate = round((resolved / total) * 100, 1) if total else 0
        attempted_first = (df["attempted_recommendation"] == "Yes").sum()

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Tickets", total)
        c2.metric("Resolved", int(resolved))
        c3.metric("Escalated", int(escalated))
        c4.metric("Resolution Rate", f"{resolution_rate}%")
        c5.metric("Tried AI Steps First", int(attempted_first))

        st.divider()

        left, right = st.columns(2)
        with left:
            st.subheader("Tickets by Category")
            st.bar_chart(df["category"].value_counts())
        with right:
            st.subheader("Tickets by Department")
            st.bar_chart(df["department"].value_counts())

        c_left, c_right = st.columns(2)
        with c_left:
            st.subheader("Priority Distribution")
            st.bar_chart(df["priority"].value_counts())
        with c_right:
            st.subheader("Attempted Recommendation Before Ticket")
            st.bar_chart(df["attempted_recommendation"].fillna("Not specified").value_counts())

# ---------------------------------------------------
# ABOUT
# ---------------------------------------------------

elif page == "About":

    st.title("About SupportPilot")
    st.write(
        "**SupportPilot** is an AI-powered Ticket Resolution Agent I built to automate "
        "ticket classification, knowledge retrieval, solution generation, and "
        "resolution workflows for IT support teams."
    )

    st.markdown("### Key Capabilities")
    st.markdown(
        "- Automated ticket intake and categorization\n"
        "- Intelligent severity & priority classification\n"
        "- AI-generated troubleshooting recommendations\n"
        "- Ticket lifecycle tracking\n"
        "- Escalation to human support when needed"
    )

    st.caption("Version 1.0 — built with Streamlit")

    st.divider()
    st.markdown("### System Status")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Database**")
        try:
            all_tickets = db.get_all_tickets()
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users")
            user_count = cur.fetchone()[0]
            conn.close()
            st.success(f"Connected — `{db.DB_NAME}`")
            st.caption(f"{user_count} user(s), {len(all_tickets)} ticket(s) stored.")
        except Exception as e:
            st.error("Not connected")
            st.caption(str(e))

    with col2:
        st.markdown("**AI Analysis Engine**")
        st.info("Currently wired: **Ollama LLM** (`ollama_analyzer.py`, model `llama3.2:3b`)")
        st.caption(
            "app.py and chatbot.py both import `analyze_ticket` from `ollama_analyzer`. "
            "It automatically falls back to the rule-based classifier if Ollama isn't reachable."
        )
        if check_ollama_reachable():
            st.success("Ollama service is reachable on this machine")
        else:
            st.warning("Ollama service not reachable — tickets will use the rule-based fallback")

        try:
            engine_counts = pd.Series(
                [t.get("ai_engine") or "rule-based" for t in db.get_all_tickets()]
            ).value_counts()
            if not engine_counts.empty:
                st.caption("Engine used across stored tickets: " + ", ".join(
                    f"{engine} ({count})" for engine, count in engine_counts.items()
                ))
        except Exception:
            pass