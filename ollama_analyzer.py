import ollama
import json
import threading

# Import the old analyzer as a fallback
from analyzer import analyze_ticket as rule_based_analyzer

MODEL = "llama3.2:3b"
DEBUG = False  # set True to print the raw Ollama response on every call, not just failures
TIMEOUT_SECONDS = 45  # hard cap so a slow/unresponsive Ollama service can never hang the app

# Fields the app requires to render the analysis. If Ollama returns any of
# these empty (which small models sometimes do — just echoing the schema
# back unfilled), we treat the response as invalid and fall back.
REQUIRED_FIELDS = [
    "category", "sentiment", "priority", "confidence", "department",
    "severity", "resolution_time", "recommendation", "summary", "resolution_steps",
]

PROMPT_TEMPLATE = """You are an IT Support Engineer classifying a support ticket.

Title: {title}
Description: {description}

Respond with ONLY a valid JSON object (no other text, no markdown) using exactly
these fields. Every field must contain a real, filled-in value based on the
ticket above — never leave a field blank or return the schema unfilled:

{{
  "category": one of ["Hardware", "Network", "Software", "Access"],
  "sentiment": one of ["Negative", "Neutral", "Positive"],
  "priority": one of ["Critical", "High", "Medium", "Low"],
  "confidence": a percentage string like "90%",
  "department": one of ["Hardware Team", "Network Team", "IT Support"],
  "severity": same value as priority,
  "resolution_time": an estimate like "2 Hours",
  "recommendation": one sentence recommending the next action,
  "summary": one sentence summarizing the issue,
  "resolution_steps": a list of 3-4 concrete troubleshooting steps as strings
}}

Example (for a VPN connectivity complaint — do NOT copy these values, they are
only to show the expected shape):
{{
  "category": "Network",
  "sentiment": "Negative",
  "priority": "High",
  "confidence": "88%",
  "department": "Network Team",
  "severity": "High",
  "resolution_time": "2 Hours",
  "recommendation": "Route this to the Network Team to check VPN configuration and firewall rules.",
  "summary": "User cannot connect to the VPN.",
  "resolution_steps": ["Restart the VPN client", "Verify network credentials", "Check firewall settings", "Escalate to Network Team if unresolved"]
}}

Now analyze the actual ticket given above and return real values for it.
"""

def _is_valid(data: dict) -> bool:
    """Reject responses where the model echoed the schema instead of filling it in."""
    if not isinstance(data, dict):
        return False
    for field in REQUIRED_FIELDS:
        value = data.get(field)
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        if isinstance(value, list) and len(value) == 0:
            return False
    return True


def _call_ollama(prompt: str):
    """The actual blocking network call, run inside a worker thread so it can be timed out."""
    response = ollama.chat(
        model=MODEL,
        format="json",          # IMPORTANT
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        options={"temperature": 0.2},  # lower temperature = more consistent structured output
    )
    return response["message"]["content"]


def analyze_ticket(description, title=""):

    prompt = PROMPT_TEMPLATE.format(title=title or "N/A", description=description)
    reason = None
    outcome = {}

    def worker():
        try:
            outcome["raw"] = _call_ollama(prompt)
        except Exception as e:
            outcome["error"] = e

    # A dedicated daemon thread per call: if Ollama truly hangs, this thread
    # just dies quietly with the process later — it never blocks other
    # requests (unlike a shared thread pool, which a hung call would
    # permanently occupy a slot in) and never blocks app shutdown.
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout=TIMEOUT_SECONDS)

    if thread.is_alive():
        reason = (
            f"Ollama didn't respond within {TIMEOUT_SECONDS}s "
            f"(is `ollama serve` running, and is `{MODEL}` pulled?)"
        )
    elif "error" in outcome:
        e = outcome["error"]
        reason = f"{type(e).__name__}: {e}"
    else:
        try:
            raw = outcome.get("raw")
            if DEBUG:
                print("OLLAMA RESPONSE:")
                print(raw)

            data = json.loads(raw)

            if not _is_valid(data):
                raise ValueError(f"Ollama returned an incomplete/empty response: {data}")

            # Add keys expected by app.py
            data.setdefault("matched_keywords", [])
            data.setdefault("priority_reason", [])
            data.setdefault("kb_results", [])
            data["ai_engine"] = "ollama"

            return data
        except Exception as e:
            reason = f"{type(e).__name__}: {e}"

    # Always print the reason for a fallback, even with DEBUG off — a silent
    # fallback is impossible to diagnose from the Streamlit UI alone.
    print(f"[ollama_analyzer] Falling back to rule-based analyzer — {reason}")

    result = rule_based_analyzer(description, title)
    result["ai_engine"] = "rule-based-fallback"
    result["ai_engine_detail"] = reason
    return result