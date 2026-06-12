import os
import requests
import re
import difflib
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
EXPENSE_DB_ID = os.getenv("EXPENSE_DB_ID")
INCOME_DB_ID = os.getenv("INCOME_DB_ID")
CATEGORY_DB_ID = os.getenv("CATEGORY_DB_ID")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# Module-level cache for Month Database ID
MONTH_DB_ID = None

def get_month_db_id():
    """Retrieves the Month Database ID dynamically from the Expense Database properties."""
    global MONTH_DB_ID
    if MONTH_DB_ID:
        return MONTH_DB_ID
    
    url = f"https://api.notion.com/v1/databases/{EXPENSE_DB_ID}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        month_prop = resp.json().get("properties", {}).get("Month", {})
        if month_prop.get("type") == "relation":
            MONTH_DB_ID = month_prop.get("relation", {}).get("database_id")
            return MONTH_DB_ID
    return None

def get_or_create_month_page_id(month_name):
    """Checks if a month page exists in the Month Database; creates it if not."""
    month_db_id = get_month_db_id()
    if not month_db_id:
        return None
        
    # Query for the page with the title matching month_name
    query_url = f"https://api.notion.com/v1/databases/{month_db_id}/query"
    query_data = {
        "filter": {
            "property": "Name",
            "title": {
                "equals": month_name
            }
        }
    }
    
    resp = requests.post(query_url, headers=HEADERS, json=query_data)
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        if results:
            return results[0]["id"]
            
    # Create the month page if it doesn't exist
    create_url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": month_db_id},
        "properties": {
            "Name": {"title": [{"text": {"content": month_name}}]}
        }
    }
    create_resp = requests.post(create_url, headers=HEADERS, json=payload)
    if create_resp.status_code == 200:
        return create_resp.json()["id"]
    return None

def get_nearest_category(category_name):
    """Fetches all categories and finds the closest matching one using SequenceMatcher."""
    url = f"https://api.notion.com/v1/databases/{CATEGORY_DB_ID}/query"
    response = requests.post(url, headers=HEADERS)
    results = response.json().get("results", [])
    
    categories = []
    for page in results:
        title_props = page["properties"].get("Category", {}).get("title", [])
        if title_props:
            categories.append({
                "id": page["id"],
                "name": title_props[0]["text"]["content"]
            })
            
    if not categories:
        return None, None
        
    # Check for exact case-insensitive match first
    for cat in categories:
        if cat["name"].strip().lower() == category_name.strip().lower():
            return cat["id"], cat["name"]
            
    # Fuzzy match using difflib
    best_match = None
    best_score = -1.0
    for cat in categories:
        score = difflib.SequenceMatcher(None, category_name.lower(), cat["name"].lower()).ratio()
        if score > best_score:
            best_score = score
            best_match = cat
            
    if best_match:
        return best_match["id"], best_match["name"]
    return None, None

def get_nearest_source(source_name):
    """Fetches available sources options from Income DB schema and finds the closest matching one."""
    url = f"https://api.notion.com/v1/databases/{INCOME_DB_ID}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        return None
        
    source_prop = resp.json().get("properties", {}).get("Source", {})
    if source_prop.get("type") != "select":
        return None
        
    options = source_prop.get("select", {}).get("options", [])
    if not options:
        return None
        
    # Check for exact case-insensitive match first
    for opt in options:
        if opt["name"].strip().lower() == source_name.strip().lower():
            return opt["name"]
            
    # Fuzzy match using difflib
    best_match = None
    best_score = -1.0
    for opt in options:
        score = difflib.SequenceMatcher(None, source_name.lower(), opt["name"].lower()).ratio()
        if score > best_score:
            best_score = score
            best_match = opt
            
    if best_match:
        return best_match["name"]
    return None

def list_categories():
    """Fetches and displays all available categories from the Category DB."""
    url = f"https://api.notion.com/v1/databases/{CATEGORY_DB_ID}/query"
    response = requests.post(url, headers=HEADERS)
    results = response.json().get("results", [])
    
    categories = []
    for page in results:
        # Get the title from the 'Category' property of each page
        title_props = page["properties"].get("Category", {}).get("title", [])
        if title_props:
            categories.append(title_props[0]["text"]["content"])
    
    if not categories:
        return "📂 No categories found yet."
    else:
        # Sort and display them
        msg = "📂 **Current Categories:**\n" + "\n".join([f"• {c}" for c in sorted(categories)])
        return msg

def add_to_notion(text):
    text = text.strip()
    
    # regex looks for [Name] [Last Number] [Optional Category Word]
    match = re.search(r"^(.*?)\s+(\d+(?:\.\d+)?)(?:\s+([a-zA-Z\s]+))?$", text)

    if not match:
        return "⚠️ Format error! Use: /ex [Item Name] [Amount] [Category]\nExample: /ex coffee on 24 June 54 Food"

    item_name = match.group(1).strip()
    amount = float(match.group(2))
    user_cat_name = match.group(3).strip() if match.group(3) else "Food & Dining"

    selected_cat_id, actual_cat_name = get_nearest_category(user_cat_name)
    if not selected_cat_id:
        return f"❌ Error: Could not find any category in Category Database."

    # Current date and month formatting
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_month_name = now.strftime("%B %Y") # e.g. "June 2026"

    month_page_id = get_or_create_month_page_id(current_month_name)
    if not month_page_id:
        return f"❌ Error: Could not find or create Month page for '{current_month_name}'."

    payload = {
        "parent": {"database_id": EXPENSE_DB_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": item_name}}]},
            "Amount": {"number": amount},
            "Date": {"date": {"start": today}},
            "Month": {"relation": [{"id": month_page_id}]},
            "Category": {"relation": [{"id": selected_cat_id}]}
        }
    }

    resp = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=payload)
    
    if resp.status_code == 200:
        notice = ""
        if actual_cat_name.lower() != user_cat_name.lower():
            notice = f" (matched to nearest category: {actual_cat_name})"
        return f"✅ Logged!\n📝 {item_name}\n💰 {amount}\n📂 {actual_cat_name}{notice}"
    else:
        return f"❌ Notion Error: {resp.json().get('message', 'Unknown Error')}"

def add_income_to_notion(text):
    text = text.strip()
    
    # regex looks for [Name] [Last Number] [Optional Source Word]
    match = re.search(r"^(.*?)\s+(\d+(?:\.\d+)?)(?:\s+([a-zA-Z\s]+))?$", text)

    if not match:
        return "⚠️ Format error! Use: /in [Item Name] [Amount] [Source]\nExample: /in TCS 14500 Salary"

    item_name = match.group(1).strip()
    amount = float(match.group(2))
    user_source_name = match.group(3).strip() if match.group(3) else "Salary"

    actual_source_name = get_nearest_source(user_source_name)
    if not actual_source_name:
        return f"❌ Error: Could not find closest source in Database options."

    # Current date and month formatting
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_month_name = now.strftime("%B %Y") # e.g. "June 2026"

    month_page_id = get_or_create_month_page_id(current_month_name)
    if not month_page_id:
        return f"❌ Error: Could not find or create Month page for '{current_month_name}'."

    payload = {
        "parent": {"database_id": INCOME_DB_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": item_name}}]},
            "Amount": {"number": amount},
            "Date": {"date": {"start": today}},
            "Month": {"relation": [{"id": month_page_id}]},
            "Source": {"select": {"name": actual_source_name}}
        }
    }

    resp = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=payload)
    
    if resp.status_code == 200:
        notice = ""
        if actual_source_name.lower() != user_source_name.lower():
            notice = f" (matched to nearest source: {actual_source_name})"
        return f"✅ Logged Income!\n📝 {item_name}\n💰 {amount}\n📂 {actual_source_name}{notice}"
    else:
        return f"❌ Notion Error: {resp.json().get('message', 'Unknown Error')}"