import os
import subprocess
import httpx
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Load environment variables
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
AUTHORIZED_USERNAME = os.getenv("AUTHORIZED_USERNAME")
BASE_DIR = os.getenv("BASE_DIR", "/storage")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")


# ---------- SECURITY CHECK ----------
def is_authorized(update: Update):
    user = update.message.from_user
    return user.username == AUTHORIZED_USERNAME


# ---------- AI ----------
async def ask_ai(prompt):
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
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
        "Server Bot Ready (Async).\nSend any message to talk with AI.\n\nCommands:\n/start\n/run"
    )


# ---------- AI CHAT ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    user_message = update.message.text
    await update.message.reply_text("Thinking...")

    result = await ask_ai(user_message)
    
    # Telegram message limit is 4096
    if len(result) > 4000:
        for i in range(0, len(result), 4000):
            await update.message.reply_text(result[i:i+4000])
    else:
        await update.message.reply_text(result)


# ---------- RUN COMMAND ----------
async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    if not context.args:
        await update.message.reply_text("Please provide a command to run.")
        return

    cmd = " ".join(context.args)

    try:
        # Using asyncio.create_subprocess_shell for non-blocking execution
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=BASE_DIR
        )
        stdout, _ = await process.communicate()
        output = stdout.decode()

        if not output:
            output = "Command executed with no output."

        if len(output) > 4000:
            for i in range(0, len(output), 4000):
                await update.message.reply_text(output[i:i+4000])
        else:
            await update.message.reply_text(output)

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


if __name__ == "__main__":
    if not TOKEN:
        print("Error: TELEGRAM_TOKEN not found in .env file.")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("run", run))

    # AI message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot running (Async)...")
    app.run_polling()