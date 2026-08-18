"""
chatbot.py
Conversational front-end for SupportPilot's AI Assistant.

Wraps analyzer.py's classification + knowledge-base retrieval so the same
"brain" that powers the Raise Ticket form also powers a chat interface.
This is a lightweight rule-based state machine — no external LLM API needed,
consistent with the rest of the analyzer's approach.
"""

from ollama_analyzer import analyze_ticket

GREETING_WORDS = {"hi", "hello", "hey", "hii", "helo", "yo", "hlo"}
AFFIRM_WORDS = ("yes", "yeah", "yep", "sure", "ok", "okay", "please", "y")
DENY_WORDS = ("no", "nope", "nah", "not now", "n")


def new_chat_state(employee_name: str = None, employee_id: str = None) -> dict:
    """Fresh conversation state for a new chat session.
    If the employee's name/ID are already known (e.g. from sign-in), pass
    them in so the bot doesn't ask again before raising a ticket.
    """
    return {
        "stage": "awaiting_description",
        "description": None,
        "analysis": None,
        "employee_name": employee_name,
        "employee_id": employee_id,
        "attempted_recommendation": "Not specified",
    }


def _looks_like_greeting(text: str) -> bool:
    return text.strip().lower() in GREETING_WORDS


def _is_affirmative(text: str) -> bool:
    t = text.strip().lower()
    return any(t == w or t.startswith(w) for w in AFFIRM_WORDS)


def _is_negative(text: str) -> bool:
    t = text.strip().lower()
    return any(t == w or t.startswith(w) for w in DENY_WORDS)


def handle_message(state: dict, message: str):
    """
    Advance the conversation by one turn.

    Returns:
        bot_reply (str): what the assistant says back
        updated_state (dict): the new conversation state to store in session_state
        ticket_ready (bool): True once enough info has been collected —
            the caller (app.py) should then create a real ticket using
            state["description"], state["employee_name"], state["employee_id"],
            and state["analysis"].
    """
    stage = state["stage"]

    # ---- Stage: waiting for an issue description ----
    if stage == "awaiting_description":
        if _looks_like_greeting(message):
            return (
                "Hi! I'm the SupportPilot assistant. Describe the issue you're "
                "facing and I'll help diagnose it and suggest a fix.",
                state,
                False,
            )

        analysis = analyze_ticket(message)
        state["description"] = message
        state["analysis"] = analysis

        lines = [
            f"That sounds like a **{analysis['category']}** issue "
            f"(**{analysis['priority']}** priority, sentiment: {analysis['sentiment']}).",
            "",
            "Here's what I'd suggest first:",
        ]
        for i, step in enumerate(analysis["resolution_steps"][:3], start=1):
            lines.append(f"{i}. {step}")

        if analysis["kb_results"]:
            top_article, score = analysis["kb_results"][0]
            lines.append("")
            lines.append(f"Related knowledge base article: **{top_article['title']}** ({score}% relevance).")

        lines.append("")
        lines.append("Before we go further — have you already tried any of these steps? (yes/no)")

        state["stage"] = "awaiting_attempted"
        return "\n".join(lines), state, False

    # ---- Stage: waiting for yes/no on whether the steps were tried ----
    if stage == "awaiting_attempted":
        if _is_affirmative(message):
            state["attempted_recommendation"] = "Yes"
        elif _is_negative(message):
            state["attempted_recommendation"] = "No"
        else:
            return (
                "Just to confirm — did you already try the suggested steps? (yes/no)",
                state,
                False,
            )

        state["stage"] = "awaiting_confirm"
        return "Got it. Would you like me to raise a support ticket for this? (yes/no)", state, False

    # ---- Stage: waiting for yes/no on raising a ticket ----
    if stage == "awaiting_confirm":
        if _is_affirmative(message):
            if state.get("employee_name") and state.get("employee_id"):
                state["stage"] = "done"
                return "Got it — raising your ticket now...", state, True
            state["stage"] = "awaiting_name"
            return "Sure — what's your name?", state, False
        if _is_negative(message):
            state["stage"] = "awaiting_description"
            return "No problem. Let me know if anything else comes up.", state, False
        return "Just to confirm — should I raise a ticket for this? (yes/no)", state, False

    # ---- Stage: collecting name ----
    if stage == "awaiting_name":
        state["employee_name"] = message.strip()
        state["stage"] = "awaiting_id"
        return "Thanks. What's your Employee ID?", state, False

    # ---- Stage: collecting employee ID -> ready to create the ticket ----
    if stage == "awaiting_id":
        state["employee_id"] = message.strip()
        state["stage"] = "done"
        return "Got it — raising your ticket now...", state, True

    # ---- Fallback / after a ticket has been created ----
    state["stage"] = "awaiting_description"
    return "Anything else I can help with? Describe a new issue any time.", state, False