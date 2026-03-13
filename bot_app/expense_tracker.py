import os
import requests
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
EXPENSE_DB_ID = os.getenv("EXPENSE_DB_ID")
CATEGORY_DB_ID = os.getenv("CATEGORY_DB_ID")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def get_or_create_category_id(category_name):
    url = f"https://api.notion.com/v1/databases/{CATEGORY_DB_ID}/query"
    query_data = {"filter": {"property": "Name", "title": {"equals": category_name}}}
    response = requests.post(url, headers=HEADERS, json=query_data)
    results = response.json().get("results", [])
    
    if results:
        return results[0]["id"], False
    else:
        # Create new category
        create_url = "https://api.notion.com/v1/pages"
        payload = {
            "parent": {"database_id": CATEGORY_DB_ID},
            "properties": {"Name": {"title": [{"text": {"content": category_name}}]}}
        }
        res = requests.post(create_url, headers=HEADERS, json=payload)
        return res.json()["id"], True

def list_categories():
    """Fetches and displays all available categories from the Category DB."""
    url = f"https://api.notion.com/v1/databases/{CATEGORY_DB_ID}/query"
    response = requests.post(url, headers=HEADERS)
    results = response.json().get("results", [])
    
    categories = []
    for page in results:
        # Get the title from the 'Name' property of each page
        title_props = page["properties"].get("Name", {}).get("title", [])
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
    user_cat_name = match.group(3).strip() if match.group(3) else "Home"

    selected_cat_id, was_created = get_or_create_category_id(user_cat_name)
    today = datetime.now().strftime("%Y-%m-%d")

    payload = {
        "parent": {"database_id": EXPENSE_DB_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": item_name}}]},
            "Amount": {"number": amount},
            "Date": {"date": {"start": today}},
            "Category": {"relation": [{"id": selected_cat_id}]}
        }
    }

    resp = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=payload)
    
    if resp.status_code == 200:
        notice = " (New category created!)" if was_created else ""
        return f"✅ Logged!\n📝 {item_name}\n💰 {amount}\n📂 {user_cat_name}{notice}"
    else:
        return f"❌ Notion Error: {resp.json().get('message', 'Unknown Error')}"