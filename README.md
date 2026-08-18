# SupportPilot – AI Ticket Resolution Agent

SupportPilot is an AI-powered IT support platform with two role-based portals — one for **employees** raising issues, and one for **support staff** resolving them. It classifies incoming issues, suggests troubleshooting steps, retrieves relevant knowledge base articles, and tracks whether a suggested fix was actually tried before a ticket reaches a technician.

Built as part of an Infosys Springboard 7.0 internship project.

---

## Features

- **Two portals, one app** — Employee Portal (AI Assistant, Raise Ticket, My Tickets) and Support Portal (Dashboard, Ticket Queue, Reports), gated by role at sign-in
- **AI Assistant chatbot** — a guided, step-by-step flow (Report → Analysis → Similar → Solutions → Ticket → Tracking) that diagnoses an issue conversationally before a ticket is ever raised
- **Hybrid classification engine** — Ollama (Llama 3.2) for AI-driven analysis, with a transparent rule-based classifier as a fallback so the app still works without a local LLM running
- **Explainable AI** — every classification shows *why*: the matched keywords and signals behind the category/priority decision, not just the output
- **Knowledge base retrieval** — surfaces relevant troubleshooting articles with a relevance score
- **Similar ticket detection** — flags past tickets that resemble a new one, to avoid duplicate troubleshooting
- **Follow-through tracking** — records whether an employee attempted the AI's suggested fix *before* the ticket reaches a technician, so support staff aren't repeating steps that already failed
- **SQLite persistence** — tickets and users are stored in a shared database, not per-browser session state, so the Employee and Support portals see the same live data
- **Session-based sign-in** — Name + Employee ID for employees, plus a shared admin passcode for the Support Portal (see [Authentication](#authentication) below)
- **Support Dashboard & Reports** — live ticket metrics, category/priority/department breakdowns, and CSV export
- **Ticket detail view** — status timeline, AI diagnosis, similar issue match, and suggested fix in one place

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI / App framework | Python, Streamlit |
| AI classification | Ollama (Llama 3.2), with a rule-based fallback engine |
| Data storage | SQLite |
| Authentication | Session-based (Streamlit `session_state`), not token-based |

---

## Project Structure

```
SupportPilot/
├── app.py                 # Main Streamlit app — UI, routing, both portals
├── chatbot.py              # Conversational state machine for the AI Assistant
├── ollama_analyzer.py       # Classification engine (Ollama + rule-based fallback)
├── database.py              # SQLite persistence layer (users + tickets)
├── requirements.txt         # Python dependencies
└── README.md
```

*(If your local file names differ slightly — e.g. `analyzer.py` instead of `ollama_analyzer.py` — update the import in `chatbot.py` and this list to match.)*

---

## Getting Started

### Prerequisites

- Python 3.9+
- (Optional, for AI-driven classification) [Ollama](https://ollama.com) installed locally with the `llama3.2` model pulled — without it, the app automatically falls back to the rule-based classifier

### Installation

```bash
git clone https://github.com/Ashlesha1524/SupportPilot.git
cd SupportPilot
pip install -r requirements.txt
streamlit run app.py
```

### Running with Ollama (optional)

```bash
ollama pull llama3.2
ollama serve
```

With Ollama running, the app will use it for classification automatically. Without it, tickets are still classified via the rule-based engine — the app doesn't require Ollama to function.

---

## Usage

1. On first launch, sign in with your **Name** and **Employee ID**.
2. Choose **Employee** or **Support Staff** at sign-in — Support Staff also requires the admin passcode.
3. **As an Employee:** start with the AI Assistant, describe your issue, and follow the suggested fix. If it doesn't resolve things, raise a ticket directly from the chat — or use the Raise Ticket form. Track your own tickets under My Tickets.
4. **As Support Staff:** land on the Dashboard for an overview, then work through the Ticket Queue — each ticket shows the AI's diagnosis, the recommendation given to the employee, and whether they'd already tried it.

---

## Authentication

Sign-in is **session-based**, not token-based (no JWT). Employees identify with a Name + Employee ID (no password); Support Staff additionally need a shared admin passcode. `database.py` looks up or creates the user record, and `st.session_state` keeps that identity live for the current browser session. This is a reasonable fit for a single-server Streamlit app — a token-based (JWT) scheme would be the natural next step only if this were exposed as a separate REST API.

---

## Database

Tickets and users are persisted in a local SQLite database (`supportpilot.db`, created automatically on first run) so that data raised in the Employee Portal is visible in the Support Portal, even across different login sessions.

**Tickets** capture: category, priority, sentiment, assigned department, AI diagnosis, similar-issue match, suggested fix, status, SLA deadline, whether the recommendation was attempted, and a full activity log.

---

## Roadmap

- [ ] Jira integration for ticket lifecycle sync
- [ ] Real vector-database-backed knowledge retrieval (RAG)
- [ ] Email automation for ticket status notifications
- [ ] Deployment to Streamlit Community Cloud
- [ ] Token-based (JWT) authentication, if the app is exposed as an API beyond the current Streamlit UI

---

## Project Status

This project is under active development as part of an ongoing internship. Core ticket classification, the AI Assistant flow, role-based portals, and SQLite persistence are implemented; knowledge-base retrieval, dashboard analytics, and the follow-through tracking feature are functional in the current build. Jira integration and email automation are planned but not yet implemented.

---

## Author

**Ashlesha Mishra**
B.Tech Computer Science and Engineering (Data Science)
Infosys Springboard 7.0 Internship Project
