import os
import re
import difflib
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
MEAL_LOG_DB_ID = os.getenv("MEAL_LOG_DB_ID")
FOOD_DB_ID = os.getenv("FOOD_DB_ID")
DAYS_DB_ID = os.getenv("DAYS_DB_ID")

MEALS = ["Breakfast", "Lunch", "Dinner", "Snacks"]

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}


def get_title_prop_name(db_id):
    """Finds the title property name of a database dynamically."""
    url = f"https://api.notion.com/v1/databases/{db_id}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        for prop_name, prop in resp.json().get("properties", {}).items():
            if prop.get("type") == "title":
                return prop_name
    return None


def get_nearest_food(food_name):
    """Fetches all foods and finds the closest matching one using SequenceMatcher."""
    title_prop = get_title_prop_name(FOOD_DB_ID)
    if not title_prop:
        return None, None

    url = f"https://api.notion.com/v1/databases/{FOOD_DB_ID}/query"
    response = requests.post(url, headers=HEADERS)
    results = response.json().get("results", [])

    foods = []
    for page in results:
        title_props = page["properties"].get(title_prop, {}).get("title", [])
        if title_props:
            foods.append({
                "id": page["id"],
                "name": title_props[0]["text"]["content"]
            })

    if not foods:
        return None, None

    # Check for exact case-insensitive match first
    for food in foods:
        if food["name"].strip().lower() == food_name.strip().lower():
            return food["id"], food["name"]

    # Fuzzy match using difflib
    best_match = None
    best_score = -1.0
    for food in foods:
        score = difflib.SequenceMatcher(None, food_name.lower(), food["name"].lower()).ratio()
        if score > best_score:
            best_score = score
            best_match = food

    if best_match:
        return best_match["id"], best_match["name"]
    return None, None


def get_or_create_today_page_id(today):
    """Checks if a Day page exists for today; creates it if not."""
    title_prop = get_title_prop_name(DAYS_DB_ID)
    if not title_prop:
        return None

    # Query for the page with the title matching today's date
    query_url = f"https://api.notion.com/v1/databases/{DAYS_DB_ID}/query"
    query_data = {
        "filter": {
            "property": title_prop,
            "title": {
                "equals": today
            }
        }
    }

    resp = requests.post(query_url, headers=HEADERS, json=query_data)
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        if results:
            return results[0]["id"]

    # Create the Day page if it doesn't exist
    create_url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": DAYS_DB_ID},
        "properties": {
            title_prop: {"title": [{"text": {"content": today}}]}
        }
    }
    create_resp = requests.post(create_url, headers=HEADERS, json=payload)
    if create_resp.status_code == 200:
        return create_resp.json()["id"]
    return None


def guess_meal():
    """Guesses the meal based on the current time of day."""
    hour = datetime.now().hour
    if hour < 12:
        return "Breakfast"
    elif hour < 17:
        return "Lunch"
    return "Dinner"


def get_nearest_meal(meal_name):
    """Validates the given meal name against known meal options."""
    # Check for exact case-insensitive match first
    for meal in MEALS:
        if meal.strip().lower() == meal_name.strip().lower():
            return meal

    # Fuzzy match using difflib
    best_match = None
    best_score = -1.0
    for meal in MEALS:
        score = difflib.SequenceMatcher(None, meal_name.lower(), meal.lower()).ratio()
        if score > best_score:
            best_score = score
            best_match = meal

    if best_match:
        return best_match
    return None


def log_food(text):
    text = text.strip()

    # regex looks for [Food Name] [Quantity] [Optional Meal Word]
    match = re.search(r"^(.*?)\s+(\d+(?:\.\d+)?)(?:\s+([a-zA-Z\s]+))?$", text)

    if not match:
        return "⚠️ Format error! Use: /eat [Food Name] [Quantity] [Optional Meal]\nExample: /eat Paneer 150 Snacks"

    food_name = match.group(1).strip()
    quantity = float(match.group(2))
    user_meal = match.group(3).strip() if match.group(3) else None

    selected_food_id, actual_food_name = get_nearest_food(food_name)
    if not selected_food_id:
        return f"❌ Error: Could not find '{food_name}' in the Food Database."

    meal = get_nearest_meal(user_meal) if user_meal else guess_meal()
    if not meal:
        return f"❌ Error: Unknown meal '{user_meal}'. Options: {', '.join(MEALS)}."

    # Current date formatting
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    day_page_id = get_or_create_today_page_id(today)
    if not day_page_id:
        return f"❌ Error: Could not find or create Day page for '{today}'."

    payload = {
        "parent": {"database_id": MEAL_LOG_DB_ID},
        "properties": {
            "Entry": {"title": [{"text": {"content": f"{actual_food_name} {quantity:g}g"}}]},
            "Date": {"date": {"start": today}},
            "Meal": {"select": {"name": meal}},
            "Food": {"relation": [{"id": selected_food_id}]},
            "Quantity": {"number": quantity},
            "Days": {"relation": [{"id": day_page_id}]}
        }
    }

    resp = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=payload)

    if resp.status_code == 200:
        notice = ""
        if actual_food_name.lower() != food_name.lower():
            notice = f" (matched to nearest food: {actual_food_name})"
        return f"✅ Logged!\n🍽️ {actual_food_name}{notice}\n⚖️ {quantity:g}\n🍳 {meal}"
    else:
        return f"❌ Notion Error: {resp.json().get('message', 'Unknown Error')}"
