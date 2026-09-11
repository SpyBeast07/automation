import os
import requests
from dotenv import load_dotenv

load_dotenv()

# ---------- CONFIG ----------
API_URL = os.getenv("WA_API_URL", "http://was.kushagragupta.co.in/send")
API_KEY = os.getenv("WA_API_KEY")
API_PHONE = os.getenv("WA_API_PHONE", "919269972395")
API_MESSAGE = os.getenv("WA_API_MESSAGE", "Health check ping")

# Alert only after this many consecutive failed checks,
# so a single hiccup never triggers a false alarm
FAILURE_THRESHOLD = 1

# Sticky state to avoid spamming the same alert
_fail_count = 0
_api_down = False


def probe_whatsapp_api():
    """Try sending a health-check message. Return (ok, reason)."""
    try:
        response = requests.post(
            API_URL,
            headers={
                "x-api-key": API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "phone": API_PHONE,
                "message": API_MESSAGE,
            },
            timeout=20,
        )
    except requests.RequestException as e:
        return False, f"request failed: {e}"

    if not 200 <= response.status_code < 300:
        return False, f"HTTP {response.status_code}: {response.text[:150]}"

    # Successful sends return a JSON body carrying the message id (e.g. {"id": "true_..."})
    try:
        data = response.json()
        if data and data.get("id"):
            return True, ""
        return False, f"no message id returned: {response.text[:150]}"
    except ValueError:
        return False, f"invalid response: {response.text[:150]}"


def whatsapp_api_alert():
    """Return an alert message only once the API stays down past the threshold."""
    global _fail_count, _api_down

    ok, reason = probe_whatsapp_api()

    if ok:
        _fail_count = 0
        _api_down = False
        return None

    _fail_count += 1

    if _fail_count < FAILURE_THRESHOLD:
        return None

    if _api_down:
        return None

    _api_down = True
    return f"⚠️ WhatsApp API is not working ({_fail_count} consecutive failures, last error: {reason})."