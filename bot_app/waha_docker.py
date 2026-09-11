import os
import requests
from dotenv import load_dotenv

load_dotenv()

# ---------- CONFIG ----------
API_URL = os.getenv("WA_API_URL", "http://was.kushagragupta.co.in/send")
API_KEY = os.getenv("WA_API_KEY")
API_PHONE = os.getenv("WA_API_PHONE", "919269972395")
API_MESSAGE = os.getenv("WA_API_MESSAGE", "Health check ping")

# Store the last known state to prevent spamming the same alert
_API_DOWN = False


def is_whatsapp_api_working():
    """Send a health-check message via the WA API and report if it was accepted."""
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
        return 200 <= response.status_code < 300
    except requests.RequestException:
        return False


def whatsapp_api_alert():
    """Return an alert message only when the API first stops working."""
    global _API_DOWN

    working = is_whatsapp_api_working()

    if not working and not _API_DOWN:
        _API_DOWN = True
        return "⚠️ WhatsApp API is not working."

    if working and _API_DOWN:
        _API_DOWN = False

    return None