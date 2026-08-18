"""
analyzer.py
Rule-based "AI" analysis engine for SupportPilot.
Swap the body of analyze_ticket() with a real LLM/API call later —
the return shape (dict) is what app.py expects, so nothing else needs to change.
"""

import re
import difflib

# ---------------------------------------------------
# Keyword banks
# ---------------------------------------------------

CATEGORY_KEYWORDS = {
    # weight, keyword — a higher weight lets a strong signal (e.g. "overheat")
    # outrank several weak signals (e.g. "train", "model", "render") from another category.
    "Hardware": [(3, "overheat"), (3, "over heat"), (2, "laptop"), (1, "hardware"),
                 (2, "printer"), (1, "battery"), (1, "screen"), (1, "keyboard"),
                 (1, "mouse"), (1, "device"), (1, "monitor"), (1, "cooling"), (1, "fan")],
    "Network": [(2, "vpn"), (1, "network"), (1, "wifi"), (1, "wi-fi"),
                (1, "internet"), (2, "connection"), (1, "connectivity"),
                (1, "timeout"), (1, "disconnect")],
    "Software": [(1, "software"), (1, "install"), (1, "installation"),
                 (1, "application"), (1, "app"), (1, "crash"), (1, "bug"),
                 (1, "update"), (1, "license"), (1, "train"), (1, "training"),
                 (1, "model"), (1, "render"), (1, "rendering")],
    "Access": [(2, "password"), (1, "login"), (1, "log in"), (1, "account"),
               (2, "reset"), (1, "access"), (2, "locked out"),
               (1, "credentials"), (1, "authentication")],
}

DEPARTMENT_MAP = {
    "Hardware": "Hardware Team",
    "Network": "Network Team",
    "Software": "IT Support",
    "Access": "IT Support",
}

NEGATIVE_WORDS = ["not working", "couldn't", "can't", "cannot", "failed",
                  "failure", "stopped", "error", "issue", "problem", "broken",
                  "overheating", "crash", "unable", "down", "urgent", "critical"]

CRITICAL_WORDS = ["critical", "urgent", "down", "outage", "overheat",
                  "overheating", "data loss", "security", "breach"]
HIGH_WORDS = ["stopped", "failed", "cannot", "can't", "blocked", "crash"]

# Canned troubleshooting playbooks, keyed by a trigger keyword found in the description.
RESOLUTION_PLAYBOOKS = {
    "overheat": [
        "Check the laptop's cooling system (fans, vents) for obstructions.",
        "Monitor system resource usage — high CPU/RAM from other processes can add to heat load.",
        "Adjust rendering/training settings — lower resolution or batch size to reduce heat generation.",
        "Check for dust buildup in vents, which can block airflow and cause overheating.",
        "Try a cooler or external cooling pad to help dissipate heat while running heavy workloads.",
    ],
    "vpn": [
        "Verify corporate firewall settings allow VPN traffic on the required ports.",
        "Check VPN client configuration for correct server address and authentication method.",
        "Restart the VPN service and clear any cached credentials.",
        "If the issue persists, try connecting from a different network to isolate the problem.",
    ],
    "password": [
        "Confirm the account isn't locked due to repeated failed attempts.",
        "Use the self-service password reset portal to generate a new password.",
        "Clear saved/cached credentials in the browser or client before retrying.",
        "If reset emails aren't arriving, check spam folder and verify the registered email address.",
    ],
    "printer": [
        "Confirm the printer is powered on and connected to the network.",
        "Restart the print spooler service on the workstation.",
        "Reinstall or update the printer driver.",
        "Try printing a test page directly from the printer's control panel.",
    ],
    "default": [
        "Restart the affected application or device to rule out a temporary glitch.",
        "Check for pending software or driver updates.",
        "Verify network connectivity if the issue involves accessing a remote service.",
        "If the issue persists after these steps, escalate to the relevant support team.",
    ],
}

# ---------------------------------------------------
# Knowledge Base — a small curated set of articles standing in for the
# "enterprise knowledge base" / vector DB described in the architecture doc.
# Each article has a category tag and a list of keywords used for retrieval.
# ---------------------------------------------------

KNOWLEDGE_BASE = [
    {
        "title": "VPN Connection Timeout Troubleshooting Guide",
        "category": "Network",
        "keywords": ["vpn", "timeout", "connection", "disconnect"],
        "content": "Step-by-step instructions for resolving VPN connection issues including timeout errors.",
        "last_updated": "2 days ago",
    },
    {
        "title": "Corporate Network Firewall Configuration",
        "category": "Network",
        "keywords": ["firewall", "vpn", "network", "port"],
        "content": "Firewall settings that may block VPN connections on the corporate network.",
        "last_updated": "1 week ago",
    },
    {
        "title": "Laptop Overheating & Thermal Management",
        "category": "Hardware",
        "keywords": ["overheat", "laptop", "cooling", "fan", "thermal"],
        "content": "Guidance on diagnosing and resolving laptop overheating during heavy workloads.",
        "last_updated": "3 days ago",
    },
    {
        "title": "Printer Not Responding — Common Fixes",
        "category": "Hardware",
        "keywords": ["printer", "spooler", "driver"],
        "content": "Common fixes for printers that are unresponsive or fail to print.",
        "last_updated": "5 days ago",
    },
    {
        "title": "Self-Service Password Reset Guide",
        "category": "Access",
        "keywords": ["password", "reset", "account", "locked"],
        "content": "How employees can reset their own password without IT intervention.",
        "last_updated": "1 day ago",
    },
    {
        "title": "Software Installation Failure Checklist",
        "category": "Software",
        "keywords": ["install", "installation", "software", "application"],
        "content": "Checklist for resolving failed or stuck software installations.",
        "last_updated": "4 days ago",
    },
]


def search_knowledge_base(text: str, category: str, top_n: int = 2):
    """
    Retrieve the most relevant knowledge base articles for a ticket.
    Scores articles by keyword overlap, boosted if the article's category
    matches the ticket's detected category — a lightweight stand-in for
    the semantic/vector search described in the architecture doc.
    """
    text = text.lower()
    scored = []
    for article in KNOWLEDGE_BASE:
        hits = sum(1 for kw in article["keywords"] if kw in text)
        if hits == 0:
            continue
        score = hits * 20
        if article["category"] == category:
            score += 15
        score = min(score, 99)
        scored.append((article, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]


def generate_email_notification(employee_name: str, ticket_id: str, analysis: dict) -> str:
    """
    Draft the automated email notification that would be sent to the employee.
    Stands in for the doc's Email Automation module — no SMTP is wired up,
    this just produces the message text for preview/demo purposes.
    """
    return (
        f"To: {employee_name}\n"
        f"Subject: Your support ticket {ticket_id} has been received\n\n"
        f"Hi {employee_name},\n\n"
        f"Your support ticket {ticket_id} has been received. Our AI system has "
        f"classified this as a {analysis['priority']} priority {analysis['category']} issue "
        f"and assigned it to the {analysis['department']}.\n\n"
        f"Suggested first step: {analysis['resolution_steps'][0]}\n\n"
        f"You'll receive updates as we progress on this ticket.\n\n"
        f"— SupportPilot"
    )


def _detect_category(text: str):
    """Returns (category, matched_keywords, all_scores) for explainability."""
    scores = {}
    matches = {}
    for cat, kws in CATEGORY_KEYWORDS.items():
        hits = [kw for weight, kw in kws if kw in text]
        scores[cat] = sum(weight for weight, kw in kws if kw in text)
        matches[cat] = hits

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        best = "Software"
    return best, matches[best], scores


def _detect_sentiment(text: str) -> str:
    hits = sum(1 for w in NEGATIVE_WORDS if w in text)
    return "Negative" if hits > 0 else "Neutral"


def _detect_priority(text: str):
    """Returns (priority, confidence, reason_words) for explainability."""
    critical_hits = [w for w in CRITICAL_WORDS if w in text]
    if critical_hits:
        return "Critical", 96, critical_hits

    high_hits = [w for w in HIGH_WORDS if w in text]
    if high_hits:
        return "High", 90, high_hits

    if len(text.split()) < 6:
        return "Low", 80, ["very short description, likely minor"]

    return "Medium", 85, ["no strong urgency signals detected"]


def _pick_playbook(text: str):
    for key in ["overheat", "vpn", "password", "printer"]:
        if key in text:
            return RESOLUTION_PLAYBOOKS[key]
    return RESOLUTION_PLAYBOOKS["default"]


def analyze_ticket(description: str, title: str = "") -> dict:
    """
    Analyze a support ticket description and return a structured result.
    """
    text = f"{title} {description}".lower().strip()

    if not text:
        text = "general issue"

    category, matched_keywords, category_scores = _detect_category(text)
    sentiment = _detect_sentiment(text)
    priority, confidence, priority_reason = _detect_priority(text)
    department = DEPARTMENT_MAP.get(category, "IT Support")
    steps = _pick_playbook(text)
    kb_results = search_knowledge_base(text, category)

    resolution_time_map = {"Critical": "1 Hour", "High": "2 Hours",
                            "Medium": "4 Hours", "Low": "1 Day"}

    summary = description.strip()
    if len(summary) > 160:
        summary = summary[:157].rstrip() + "..."

    recommendation = (
        f"This sounds like a {category.lower()} issue. "
        f"Based on the details provided, I'd recommend routing this to the {department}."
    )

    return {
        "category": category,
        "sentiment": sentiment,
        "priority": priority,
        "confidence": f"{confidence}%",
        "department": department,
        "severity": priority,  # kept for backward-compat with dashboards expecting 'severity'
        "resolution_time": resolution_time_map.get(priority, "4 Hours"),
        "recommendation": recommendation,
        "summary": summary,
        "resolution_steps": steps,
        "matched_keywords": matched_keywords,
        "category_scores": category_scores,
        "priority_reason": priority_reason,
        "kb_results": kb_results,
    }


def find_similar_tickets(description: str, past_tickets: list, top_n: int = 3, threshold: float = 0.22):
    """
    Compare a new ticket description against previously logged tickets and return
    the most similar ones. Blends word-overlap (Jaccard) with sequence similarity
    so it catches both "same topic, different words" and "near-duplicate phrasing".

    past_tickets: list of dicts, each expected to have a "description" key.
    Returns: list of (ticket_dict, score) sorted by score descending.
    """
    def tokenize(t):
        return set(re.findall(r"[a-z]+", t.lower()))

    new_tokens = tokenize(description)
    if not new_tokens:
        return []

    scored = []
    for ticket in past_tickets:
        past_desc = ticket.get("description", "")
        past_tokens = tokenize(past_desc)
        if not past_tokens:
            continue

        union = new_tokens | past_tokens
        jaccard = len(new_tokens & past_tokens) / len(union) if union else 0
        seq_ratio = difflib.SequenceMatcher(None, description.lower(), past_desc.lower()).ratio()
        score = 0.5 * jaccard + 0.5 * seq_ratio

        if score >= threshold:
            scored.append((ticket, round(score * 100, 1)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]