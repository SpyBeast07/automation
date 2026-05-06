import os
import httpx
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from bot_app.status import get_system_status
from bot_app.fan_control import fan_logic, get_fan_status
from bot_app.system_warnings import check_system_health
from bot_app.expense_tracker import list_categories, add_to_notion
from bot_app.downloader import handle_download
from ddgs import DDGS

# ---------- ENV ----------
load_dotenv()

# Prepend venv/bin to PATH to use local dependencies like yt-dlp
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
_venv_bin = os.path.join(_project_root, "venv", "bin")

if os.path.isdir(_venv_bin):
    os.environ["PATH"] = _venv_bin + os.pathsep + os.environ.get("PATH", "")

TOKEN = os.getenv("TELEGRAM_TOKEN")
AUTHORIZED_USERNAME = os.getenv("AUTHORIZED_USERNAME")
BASE_DIR = os.getenv("BASE_DIR", "/storage")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Global HTTP client
http_client = httpx.AsyncClient(timeout=120.0)

# ---------- SECURITY ----------
def get_user(update):
    if update.message:
        return update.message.from_user
    if update.callback_query:
        return update.callback_query.from_user
    return None


def is_authorized(update):
    user = get_user(update)
    if not user:
        return False

    return user.username == AUTHORIZED_USERNAME


# ---------- STATUS ----------
async def status(update, context):
    if not is_authorized(update):
        return

    result = get_system_status()

    for i in range(0, len(result), 4000):
        await update.message.reply_text(result[i:i+4000])


# ---------- FANS ----------
async def fans(update, context):
    if not is_authorized(update):
        return

    result = get_fan_status()

    for i in range(0, len(result), 4000):
        await update.message.reply_text(result[i:i+4000])


# ---------- FAN MONITOR ----------
async def fan_monitor(app):

    await asyncio.sleep(10)

    while True:

        try:
            temp, speed, changed = fan_logic()

            if changed and CHAT_ID:

                text = f"""
Fan control triggered:

{temp}
{speed}
"""

                await app.bot.send_message(
                    chat_id=CHAT_ID,
                    text=text
                )

        except Exception as e:
            print("Fan monitor error:", e)

        await asyncio.sleep(30)


# ---------- SYSTEM MONITOR ----------
async def system_monitor(app):

    await asyncio.sleep(15)

    while True:

        try:
            warning_msg = check_system_health()

            if warning_msg and CHAT_ID:
                await app.bot.send_message(
                    chat_id=CHAT_ID,
                    text=warning_msg,
                    parse_mode="Markdown"
                )

        except Exception as e:
            print("System monitor error:", e)

        await asyncio.sleep(60)


# ---------- AI ----------
def web_search(query):
    try:
        results = DDGS().text(query, max_results=3)
        if not results:
            return "No results found."
        
        formatted_results = []
        for r in results:
            formatted_results.append(f"Source: {r.get('href')}\nContent: {r.get('body')}")
        
        return "\n\n".join(formatted_results)
    except Exception as e:
        return f"Search error: {str(e)}"

async def ask_ai(prompt):

    chat_url = OLLAMA_URL.replace("generate", "chat")
    
    tools = [{
        'type': 'function',
        'function': {
            'name': 'web_search',
            'description': 'Use this tool to get up-to-date information, news, or prices from the internet.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {'type': 'string', 'description': 'The search keywords'},
                },
                'required': ['query'],
            },
        },
    }]

    messages = [
        {
            'role': 'system', 
            'content': 'You are a helpful assistant with web access. If you are asked about current events, prices, or anything you do not know for sure, use the web_search tool.'
        },
        {'role': 'user', 'content': prompt}
    ]

    try:
        response = await http_client.post(
            chat_url,
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "tools": tools,
                "stream": False
            }
        )

        response.raise_for_status()
        data = response.json()
        message = data.get("message", {})

        # Fallback for models that output tool choice as raw JSON text
        content = message.get("content", "").strip()
        if not message.get("tool_calls") and content.startswith("{") and content.endswith("}"):
            import json
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict) and "name" in parsed and "arguments" in parsed:
                    message["tool_calls"] = [{"function": parsed}]
            except Exception:
                pass

        # Check for tool calls
        if message.get("tool_calls"):
            for tool in message["tool_calls"]:
                if tool["function"]["name"] == 'web_search':
                    query = tool["function"]["arguments"]["query"]
                    
                    loop = asyncio.get_event_loop()
                    search_data = await loop.run_in_executor(None, web_search, query)
                    
                    messages.append(message)
                    messages.append({'role': 'tool', 'content': search_data})
                    
                    final_response = await http_client.post(
                        chat_url,
                        json={
                            "model": OLLAMA_MODEL,
                            "messages": messages,
                            "stream": False
                        }
                    )
                    final_response.raise_for_status()
                    final_data = final_response.json()
                    return final_data.get("message", {}).get("content", "No response")
        
        return message.get("content", "No response")

    except Exception as e:
        return f"AI error: {str(e)}"


# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_authorized(update):
        return

    await update.message.reply_text(
        """
Commands:
/start

/run -- Run commands

/system -- Get system status
/fans -- Get fan status

/ex -- Add new expense
/cat -- List expense categories

/dl <link> -- Download media from a link
"""
    )


# ---------- AI CHAT ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_authorized(update):
        return

    user_message = update.message.text

    await update.message.reply_text("Thinking...")

    result = await ask_ai(user_message)

    for i in range(0, len(result), 4000):
        await update.message.reply_text(result[i:i+4000])


# ---------- RUN COMMAND ----------
async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_authorized(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /run <command>")
        return

    cmd = " ".join(context.args)

    try:

        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=BASE_DIR
        )

        stdout, _ = await process.communicate()

        output = stdout.decode().strip()

        if not output:
            output = "Command executed successfully."

        for i in range(0, len(output), 4000):
            await update.message.reply_text(output[i:i+4000])

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


# ---------- EXPENSES ----------
async def ex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /ex [Item Name] [Amount] [Category]\nExample: /ex coffee 54 Food")
        return

    text = " ".join(context.args)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, add_to_notion, text)
    await update.message.reply_text(result)

async def cat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, list_categories)
    await update.message.reply_text(result, parse_mode="Markdown")


# ---------- DOWNLOADER ----------
async def dl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /dl <link>")
        return

    url = context.args[0]
    
    if not url.startswith("http"):
        await update.message.reply_text("Send a valid URL.")
        return

    await update.message.reply_text("Downloading...")

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, handle_download, url)
        await update.message.reply_text(f"Download complete: {result}")
    except Exception as e:
        await update.message.reply_text(f"Download failed:\n{e}")


# ---------- APP ----------
async def on_startup(app):
    asyncio.create_task(fan_monitor(app))
    asyncio.create_task(system_monitor(app))


def create_app():

    if not TOKEN:
        raise ValueError("TELEGRAM_TOKEN not found")

    app = ApplicationBuilder().token(TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("run", run))
    app.add_handler(CommandHandler("system", status))
    app.add_handler(CommandHandler("fans", fans))
    app.add_handler(CommandHandler("ex", ex_command))
    app.add_handler(CommandHandler("cat", cat_command))
    app.add_handler(CommandHandler("dl", dl_command))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


# ---------- MAIN ----------
def run_bot():

    app = create_app()

    print("Bot running...")

    app.run_polling()


if __name__ == "__main__":
    run_bot()