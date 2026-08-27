import os
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.request import HTTPXRequest

from bot_app.status import get_system_status
from bot_app.fan_control import fan_logic, get_fan_status
from bot_app.system_warnings import check_system_health
from bot_app.expense_tracker import list_categories, add_to_notion, add_income_to_notion
from bot_app.nutrition_tracker import log_food, consume_food_selection, get_nutrition_stats, refresh_food_cache

# ---------- ENV ----------
load_dotenv()

# Prepend venv/bin to PATH to use local dependencies
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
_venv_bin = os.path.join(_project_root, "venv", "bin")

if os.path.isdir(_venv_bin):
    os.environ["PATH"] = _venv_bin + os.pathsep + os.environ.get("PATH", "")

TOKEN = os.getenv("TELEGRAM_TOKEN")
AUTHORIZED_USERNAME = os.getenv("AUTHORIZED_USERNAME")
BASE_DIR = os.getenv("BASE_DIR", "/storage")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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


# ---------- START ----------
HELP_TEXT = """
Commands:
/start

/run -- Run commands

/system -- Get system status
/fans -- Get fan status

/in -- Add new income
/ex -- Add new expense
/cat -- List expense categories

/eat <food> <qty> [meal] -- Log food
/stats -- Today's nutrition analytics
/refreshfoods -- Refresh food database cache
"""


async def send_help(update):
    await update.message.reply_text(HELP_TEXT)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_authorized(update):
        return

    await send_help(update)


# ---------- UNKNOWN MESSAGE ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_authorized(update):
        return

    await send_help(update)


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

async def in_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /in [Item Name] [Amount] [Source]\nExample: /in TCS 14500 Salary")
        return

    text = " ".join(context.args)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, add_income_to_notion, text)
    await update.message.reply_text(result)

async def cat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, list_categories)
    await update.message.reply_text(result, parse_mode="Markdown")


# ---------- NUTRITION ----------
async def eat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /eat [Food Name] [Quantity] [Optional Meal]\nExample: /eat Paneer 150 Snacks")
        return

    text = " ".join(context.args)
    loop = asyncio.get_event_loop()
    result, selection, analytics = await loop.run_in_executor(None, log_food, text)

    if analytics:
        await update.message.reply_text(result)
        await update.message.reply_text(analytics)
        return

    if not selection:
        await update.message.reply_text(result)
        return

    keyboard = [
        [InlineKeyboardButton(opt["name"], callback_data=f"eat:{selection['key']}:{i}")]
        for i, opt in enumerate(selection["options"])
    ]
    await update.message.reply_text(result, reply_markup=InlineKeyboardMarkup(keyboard))


async def on_eat_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    if not is_authorized(update):
        await query.answer("Not authorized.")
        return

    _, key, index = query.data.split(":")
    loop = asyncio.get_event_loop()
    result, analytics = await loop.run_in_executor(None, consume_food_selection, key, int(index))

    if result is None:
        await query.answer("Selection expired. Please use /eat again.")
        return

    await query.answer()
    await query.edit_message_text(result)

    if analytics:
        await query.message.reply_text(analytics)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, get_nutrition_stats)
    await update.message.reply_text(result)


async def refreshfoods_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, refresh_food_cache)
    await update.message.reply_text("✅ Food cache refreshed. Next /eat will fetch fresh data from Notion.")


# ---------- APP ----------
async def on_startup(app):
    asyncio.create_task(fan_monitor(app))
    asyncio.create_task(system_monitor(app))


def create_app():

    if not TOKEN:
        raise ValueError("TELEGRAM_TOKEN not found")

    # Use custom HTTPXRequest with increased timeouts to prevent NetworkError/ReadError
    request_config = HTTPXRequest(
        connect_timeout=20.0,
        read_timeout=20.0,
        write_timeout=20.0,
        pool_timeout=5.0
    )

    app = ApplicationBuilder().token(TOKEN).request(request_config).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("run", run))
    app.add_handler(CommandHandler("system", status))
    app.add_handler(CommandHandler("fans", fans))
    app.add_handler(CommandHandler("ex", ex_command))
    app.add_handler(CommandHandler("in", in_command))
    app.add_handler(CommandHandler("cat", cat_command))
    app.add_handler(CommandHandler("eat", eat_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("refreshfoods", refreshfoods_command))
    app.add_handler(CallbackQueryHandler(on_eat_selection, pattern="^eat:"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


# ---------- MAIN ----------
def run_bot():

    app = create_app()

    print("Bot running...")

    app.run_polling()


if __name__ == "__main__":
    run_bot()