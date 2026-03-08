import logging
import subprocess
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

logger = logging.getLogger(__name__)

AUTHORIZED_USERNAME = "SpyBeast07"
BASE_DIR = "/storage"
OLLAMA_URL = "http://localhost:11434/api/generate"

# Global reference for background tasks
_bot_instance = None

class TelegramBot:
    def __init__(self, token: str, agent_controller):
        global _bot_instance
        self.token = token
        self.agent_controller = agent_controller
        self.app = ApplicationBuilder().token(self.token).build()
        _bot_instance = self.app.bot
        
        self.app.add_handler(CommandHandler("start", self.start_cmd))
        self.app.add_handler(CommandHandler("run", self.run_cmd))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    def is_authorized(self, update: Update):
        user = update.message.from_user
        return user.username == AUTHORIZED_USERNAME

    def ask_ai(self, prompt):
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

    async def start_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update):
            return
        await update.message.reply_text(
            "Server Bot Ready.\nSend any message to talk with AI.\n\nCommands:\n/start\n/run"
        )

    async def run_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update):
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

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update):
            return
        user_message = update.message.text
        user_id = str(update.message.from_user.id)
        
        await update.message.reply_text("Thinking...")
        
        # Use LangChain agent to process the message asynchronously
        result = await self.agent_controller.process_message(user_message, chat_id=update.effective_chat.id)
        
        await update.message.reply_text(result)
        
        # Save to database if available
        try:
            from database.db import save_chat
            save_chat(user_id, user_message, result)
        except Exception as e:
            logger.warning(f"Failed to save chat to DB: {e}")

    async def start(self):
        logger.info("Starting Telegram bot...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        
    async def stop(self):
        logger.info("Stopping Telegram bot...")
        if self.app.updater and self.app.updater.running:
            await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
