import os
import re
import time
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

MEALS = ["Breakfast", "Lunch", "Dinner", "Snack"]
CURRENT_GOALS_NAME = "Current Goals"
ANALYTICS_COLUMNS = ["Calories %", "Protein %", "Carbs %", "Fat %"]

# Module-level cache for Goals Database ID
GOALS_DB_ID = None

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


# Cache of the full food list to avoid re-fetching huge databases on every /eat
FOODS_CACHE = {"foods": None, "ts": 0}
FOODS_CACHE_TTL = 600  # seconds


def fetch_all_foods():
    """Fetches every food from the Food Database, paginating through all results."""
    title_prop = get_title_prop_name(FOOD_DB_ID)
    if not title_prop:
        return []

    url = f"https://api.notion.com/v1/databases/{FOOD_DB_ID}/query"
    body = {"page_size": 100}

    foods = []
    while True:
        response = requests.post(url, headers=HEADERS, json=body)
        data = response.json()
        results = data.get("results", [])

        for page in results:
            title_props = page["properties"].get(title_prop, {}).get("title", [])
            if title_props:
                # Join all title chunks to get the full food name
                full_name = " ".join(part["text"]["content"] for part in title_props).strip()
                foods.append({
                    "id": page["id"],
                    "name": full_name
                })

        # Notion returns at most 100 pages per request; keep fetching until done
        if not data.get("has_more"):
            break
        body["start_cursor"] = data.get("next_cursor")

    return foods


def get_all_foods():
    """Returns the full food list, using a time-based cache for large databases."""
    if FOODS_CACHE["foods"] is None or time.time() - FOODS_CACHE["ts"] > FOODS_CACHE_TTL:
        foods = fetch_all_foods()
        if foods:
            FOODS_CACHE["foods"] = foods
            FOODS_CACHE["ts"] = time.time()
        return foods
    return FOODS_CACHE["foods"]


def _normalize(text):
    """Lowercases and strips punctuation/extra spaces for robust comparison."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _food_score(query, name):
    """Scores how well a query matches a food name. Higher is better.

    Names made up of only the matching words score highest;
    extra non-matching words lower the score.
    """
    q = _normalize(query)
    n = _normalize(name)

    if q == n:
        return 5.0

    q_words = set(q.split())
    n_words = set(n.split())

    # Any whole word matches, e.g. "paneer" matches "Paneer Butter Masala"
    if q_words & n_words:
        # Ratio of matched words: 1.0 means the name has no extra words
        overlap = len(q_words & n_words) / max(len(q_words), len(n_words))
        return 3.0 + overlap

    # Partial word match, e.g. "paneers" matches "paneer"
    for qw in q_words:
        for nw in n_words:
            if len(qw) >= 4 and len(nw) >= 4 and (qw in nw or nw in qw):
                return 2.0

    return difflib.SequenceMatcher(None, q, n).ratio()


# Only auto-log when the name matches exactly or is made up of only the
# matching words (no extra words). Anything else shows selection options.
CONFIDENT_SCORE = 4.0
MIN_OPTION_SCORE = 1.5
MAX_OPTIONS = 5

# Pending food selections awaiting user confirmation: {key: {...}}
PENDING_FOOD_SELECTIONS = {}
_next_selection_key = [0]


def find_food_candidates(food_name):
    """Ranks foods against the query.

    Returns (best, options) where best is a confident match (or None),
    and options is the ranked list of top candidates for selection.
    """
    foods = get_all_foods()
    if not foods:
        return None, []

    scored = sorted(
        foods,
        key=lambda f: (_food_score(food_name, f["name"]), -len(f["name"].split())),
        reverse=True
    )

    best = scored[0] if _food_score(food_name, scored[0]["name"]) >= CONFIDENT_SCORE else None
    options = [f for f in scored[:MAX_OPTIONS] if _food_score(food_name, f["name"]) >= MIN_OPTION_SCORE]
    return best, options


def get_goals_db_id():
    """Retrieves the Goals Database ID dynamically from the Days Database properties."""
    global GOALS_DB_ID
    if GOALS_DB_ID:
        return GOALS_DB_ID

    url = f"https://api.notion.com/v1/databases/{DAYS_DB_ID}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        goals_prop = resp.json().get("properties", {}).get("Goals", {})
        if goals_prop.get("type") == "relation":
            GOALS_DB_ID = goals_prop.get("relation", {}).get("database_id")
            return GOALS_DB_ID
    return None


def get_current_goals_page_id():
    """Finds the 'Current Goals' page in the Goals Database."""
    goals_db_id = get_goals_db_id()
    if not goals_db_id:
        return None

    title_prop = get_title_prop_name(goals_db_id)
    if not title_prop:
        return None

    query_url = f"https://api.notion.com/v1/databases/{goals_db_id}/query"
    query_data = {
        "filter": {
            "property": title_prop,
            "title": {
                "equals": CURRENT_GOALS_NAME
            }
        }
    }

    resp = requests.post(query_url, headers=HEADERS, json=query_data)
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        if results:
            return results[0]["id"]
    return None


def get_or_create_today_page_id(day_title, today_iso):
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
                "equals": day_title
            }
        }
    }

    resp = requests.post(query_url, headers=HEADERS, json=query_data)
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        if results:
            return results[0]["id"]

    # Create the Day page if it doesn't exist, with Date and Current Goals pre-filled
    current_goals_page_id = get_current_goals_page_id()

    properties = {
        title_prop: {"title": [{"text": {"content": day_title}}]},
        "Date": {"date": {"start": today_iso}}
    }

    if current_goals_page_id:
        properties["Goals"] = {"relation": [{"id": current_goals_page_id}]}

    create_url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": DAYS_DB_ID},
        "properties": properties
    }
    create_resp = requests.post(create_url, headers=HEADERS, json=payload)
    if create_resp.status_code == 200:
        return create_resp.json()["id"]
    return None


def _extract_value(prop):
    """Extracts a value from a Notion property (number, string, formula, or rollup).

    Returns (value, is_number) or (None, False) if unavailable.
    """
    prop_type = prop.get("type")
    value = None

    if prop_type in ("number", "string"):
        value = prop.get(prop_type)
    elif prop_type == "formula":
        formula = prop.get("formula", {})
        value = formula.get("number", formula.get("string"))
    elif prop_type == "rollup":
        rollup = prop.get("rollup", {})
        value = rollup.get("number", rollup.get("string"))

    return value, isinstance(value, (int, float))


def get_day_analytics(day_page_id):
    """Fetches the Calories %, Protein %, Carbs %, Fat % columns from a Day page.

    Returns an analytics message string, or None if unavailable.
    """
    resp = requests.get(f"https://api.notion.com/v1/pages/{day_page_id}", headers=HEADERS)
    if resp.status_code != 200:
        return None

    props = resp.json().get("properties", {})

    lines = []
    for col in ANALYTICS_COLUMNS:
        value, is_number = _extract_value(props.get(col, {}))
        if is_number:
            lines.append(f"{col} {value:g}%")
        elif value:
            lines.append(value)
        else:
            lines.append(f"{col} —")

    if all(line.endswith("—") for line in lines):
        return None

    header = f"📊 Today ({datetime.now().strftime('%b %d, %Y')}):"
    return header + "\n" + "\n".join(lines)


def guess_meal():
    """Guesses the meal based on the current time of day."""
    hour = datetime.now().hour
    if hour < 12:
        return "Breakfast"
    elif hour < 17:
        return "Lunch"
    return "Dinner"


def get_nearest_meal(meal_name):
    """Finds the closest matching meal option out of the 4 fixed meals."""
    # Check for exact case-insensitive match first
    for meal in MEALS:
        if meal.strip().lower() == meal_name.strip().lower():
            return meal

    # Fuzzy match using difflib - always picks the closest of the 4
    return max(MEALS, key=lambda meal: difflib.SequenceMatcher(None, meal_name.lower(), meal.lower()).ratio())


def _parse_eat(text):
    """Parses an /eat input. Returns (food_name, quantity, meal) or an error string."""
    # regex looks for [Food Name] [Quantity] [Optional Meal Word]
    match = re.search(r"^(.*?)\s+(\d+(?:\.\d+)?)(?:\s+([a-zA-Z\s]+))?$", text.strip())

    if not match or not match.group(1).strip():
        return "⚠️ Format error! Use: /eat [Food Name] [Quantity] [Optional Meal]\nExample: /eat Paneer 150 Snacks"

    food_name = match.group(1).strip()
    quantity = float(match.group(2))
    user_meal = match.group(3).strip() if match.group(3) else None
    meal = get_nearest_meal(user_meal) if user_meal else guess_meal()

    return food_name, quantity, meal


def create_meal_log(food_name, food, quantity, meal):
    """Creates a Meal Log entry for the given food and returns the result message."""
    actual_food_name = food["name"]

    # Current date formatting
    now = datetime.now()
    today_iso = now.strftime("%Y-%m-%d")       # for the Date property
    day_title = now.strftime("%b %d, %Y")      # for the Days page title, e.g. "Aug 25, 2026"

    day_page_id = get_or_create_today_page_id(day_title, today_iso)
    if not day_page_id:
        return f"❌ Error: Could not find or create Day page for '{day_title}'."

    payload = {
        "parent": {"database_id": MEAL_LOG_DB_ID},
        "properties": {
            "Entry": {"title": [{"text": {"content": f"{actual_food_name} {quantity:g}g"}}]},
            "Date": {"date": {"start": today_iso}},
            "Meal": {"select": {"name": meal}},
            "Food": {"relation": [{"id": food["id"]}]},
            "Quantity": {"number": quantity},
            "Days": {"relation": [{"id": day_page_id}]}
        }
    }

    resp = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=payload)

    if resp.status_code == 200:
        notice = ""
        if actual_food_name.lower() != food_name.lower():
            notice = f" (matched to nearest food: {actual_food_name})"

        # Formulas/rollups can take a moment to recompute after the new log
        analytics = None
        for _ in range(3):
            time.sleep(1)
            analytics = get_day_analytics(day_page_id)
            if analytics:
                break

        msg = f"✅ Logged!\n🍽️ {actual_food_name}{notice}\n⚖️ {quantity:g}\n🍳 {meal}"
        if analytics:
            msg += f"\n\n{analytics}"
        return msg
    else:
        return f"❌ Notion Error: {resp.json().get('message', 'Unknown Error')}"


def log_food(text):
    """Handles /eat input.

    Returns (message, selection_or_None). When no confident food match is found,
    selection contains the pending options so the bot can show choice buttons.
    """
    parsed = _parse_eat(text)
    if isinstance(parsed, str):
        return parsed, None

    food_name, quantity, meal = parsed

    best, options = find_food_candidates(food_name)

    if best:
        return create_meal_log(food_name, best, quantity, meal), None

    if not options:
        return f"❌ Error: Could not find '{food_name}' in the Food Database.", None

    _next_selection_key[0] += 1
    key = str(_next_selection_key[0])
    PENDING_FOOD_SELECTIONS[key] = {
        "text": text,
        "options": options
    }

    msg = f"🤔 No confident match found for '{food_name}'. Select the right food:\n"
    msg += "\n".join(f"{i + 1}. {opt['name']}" for i, opt in enumerate(options))
    return msg, {"key": key, "options": options}


def consume_food_selection(key, index):
    """Retrieves and removes a pending selection. Returns (text, food) or None."""
    pending = PENDING_FOOD_SELECTIONS.pop(key, None)
    if not pending or index >= len(pending["options"]):
        return None

    food = pending["options"][index]

    parsed = _parse_eat(pending["text"])
    if isinstance(parsed, str):
        return None

    _, quantity, meal = parsed
    return create_meal_log(food["name"], food, quantity, meal)


def get_nutrition_stats():
    """Handles /stats. Returns today's analytics from the Days Database."""
    now = datetime.now()
    day_title = now.strftime("%b %d, %Y")
    today_iso = now.strftime("%Y-%m-%d")

    day_page_id = get_or_create_today_page_id(day_title, today_iso)
    if not day_page_id:
        return f"❌ Error: Could not find or create Day page for '{day_title}'."

    analytics = get_day_analytics(day_page_id)
    if not analytics:
        return f"❌ No analytics available yet for '{day_title}'. Log a meal first with /eat."
    return analytics
