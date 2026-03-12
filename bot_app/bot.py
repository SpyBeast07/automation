import os
import subprocess
import httpx
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from bot_app.status import get_system_status
from bot_app.fan_control import fan_logic, get_fan_status
from bot_app.system_warnings import check_system_health

# ---------- ENV ----------
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
AUTHORIZED_USERNAME = os.getenv("AUTHORIZED_USERNAME")
BASE_DIR = os.getenv("BASE_DIR", "/storage")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
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

Temperature: {temp} °C
Fan Speed Set: {speed} %
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
async def ask_ai(prompt):

    try:
        response = await http_client.post(
            OLLAMA_URL,
            json={
                "model": "phi3",
                "prompt": prompt,
                "stream": False
            }
        )

        response.raise_for_status()

        data = response.json()

        return data.get("response", "No response")

    except Exception as e:
        return f"AI error: {e}"


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

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


# ---------- MAIN ----------
def run_bot():

    app = create_app()

    print("Bot running...")

    app.run_polling()


if __name__ == "__main__":
    run_bot()