import asyncio
import logging
from config.settings import BOT_TOKEN, DATABASE_URL, OLLAMA_BASE_URL, OLLAMA_MODEL
from agent.agent_controller import AgentController
import sys
import os
import importlib.util

# Prevent local `telegram/` folder from shadowing the `python-telegram-bot` pip package
original_paths = list(sys.path)
sys.path = [p for p in sys.path if p not in ('', os.getcwd(), os.path.abspath('.'))]
sys.path.append(os.getcwd()) # Add it at the end to allow other imports if needed

import telegram
import telegram.ext

sys.path = original_paths # Restore

spec = importlib.util.spec_from_file_location("local_telegram_bot", "telegram/bot.py")
local_bot_module = importlib.util.module_from_spec(spec)
sys.modules["local_telegram_bot"] = local_bot_module
spec.loader.exec_module(local_bot_module)
TelegramBot = local_bot_module.TelegramBot
from database.db import connect_db, create_tables
from scheduler.scheduler import get_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def main():
    logger.info("Initializing services...")
    
    # Initialize components
    db_client = None
    try:
        # connect_db() implicitly calls create_tables() in its implementation
        db_client = connect_db()
    except Exception as e:
        logger.error(f"Database connection failed: {e}. Running without persistent DB features.")
    
    agent_controller = AgentController(OLLAMA_BASE_URL, OLLAMA_MODEL)
    
    bot = TelegramBot(BOT_TOKEN, agent_controller)
    
    scheduler = None
    try:
        scheduler = get_scheduler()
        scheduler.start()
    except Exception as e:
        logger.error(f"Scheduler failed to start: {e}. Job persistence might be disabled.")

    logger.info("Starting main bot loop...")
    try:
        # Assuming bot.start() might be an async blocking call in an actual implementation
        # For now, just a placeholder run loop
        await bot.start()
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await bot.stop()
        if scheduler:
            scheduler.stop()
        if db_client:
            db_client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
