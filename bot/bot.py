import os
import subprocess
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = "8764406228:AAHzk2iNSLDKoI5mmN0zWwEJF7f2mYHrCQ4"

AUTHORIZED_USERNAME = "SpyBeast07"

BASE_DIR = "/storage"
OLLAMA_URL = "http://localhost:11434/api/generate"


# ---------- SECURITY CHECK ----------
def is_authorized(update: Update):
    user = update.message.from_user
    return user.username == AUTHORIZED_USERNAME


# ---------- AI ----------
def ask_ai(prompt):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": "phi3",
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        data = response.json()
        return data.get("response", "No response")

    except Exception as e:
        return f"AI error: {e}"


# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_authorized(update):
        return

    await update.message.reply_text(
        "Server Bot Ready.\nSend any message to talk with AI.\n\nCommands:\n/start\n/run"
    )


# ---------- AI CHAT ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_authorized(update):
        return

    user_message = update.message.text

    await update.message.reply_text("Thinking...")

    result = ask_ai(user_message)

    await update.message.reply_text(result[:4000])


# ---------- RUN COMMAND ----------
async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_authorized(update):
        return

    cmd = " ".join(context.args)

    try:
        output = subprocess.check_output(
            cmd,
            shell=True,
            cwd=BASE_DIR,
            stderr=subprocess.STDOUT
        )

        await update.message.reply_text(output.decode()[:4000])

    except Exception as e:
        await update.message.reply_text(str(e))


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("run", run))

# AI message handler
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Bot running...")

app.run_polling()