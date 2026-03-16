# Telegram AI Automation Bot

A comprehensive, personal Telegram bot built in Python to help manage your Linux system, track expenses via Notion, download media, chat with local LLMs (Ollama + DuckDuckGo search), and intelligently control laptop fans (`nbfc`).

## Features

- **System Monitoring:** Get system status (`/system`), including CPU, memory, and disk usage. The bot also proactively alerts you on high temperatures or low disk space.
- **Fan Control:** Intelligently controls the system fans (`/fans`) using Nodebook Fan Control (`nbfc`), equipped with rolling averages for quiet cooling at low temperatures and immediate reaction when hot.
- **Local AI Chat:** Chat securely with an AI powered by `Ollama` running on your local machine (defaulting to `qwen2.5:3b`). It automatically uses `DuckDuckGo` web search if it needs real-time information.
- **Run Remote Commands:** Execute shell commands directly from your Telegram chat safely using `/run`.
- **Notion Expense Tracker:** Quickly log items to your Notion expense databases (`/ex coffee 54 Food`), and list categories (`/cat`).
- **Media Downloader:** Downloads media directly to your machine using `/dl <link>`.
- **Restricted Access:** Hardcoded username authorization prevents other users from interacting with the bot.

## Prerequisites

Ensure you have the following installed on your host machine:
- `python3` and `venv`
- `nbfc` (Notebook Fan Control, required for fan management)
- `ollama` (For the local AI model)
- A registered Telegram Bot (via `BotFather`)
- A Notion integration token (if utilizing the expense tracker)

## Installation & Setup

1. **Clone or create the project directory:**
   ```bash
   mkdir ~/automation && cd ~/automation
   ```

2. **Set up a Python Virtual Environment:**
   It is recommended to use a virtual environment to manage dependencies.
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install python-telegram-bot httpx python-dotenv duckduckgo-search
   # (Add any additional dependencies your bot_app modules use, e.g., yt-dlp, notion-client, psutil)
   ```

4. **Configuration:**
   Copy the example environment file and fill it out:
   ```bash
   cp .env.example .env
   nano .env
   ```

   **Required `.env` Variables:**
   - `TELEGRAM_TOKEN`: Your bot token from @BotFather.
   - `AUTHORIZED_USERNAME`: Your exact Telegram username (without the `@`) to authorize commands.
   - `OLLAMA_URL`: Local Ollama API (default: `http://localhost:11434/api/generate`).
   - `BASE_DIR`: Base directory for running shell commands.
   - `TELEGRAM_CHAT_ID`: The ID of your chat (for proactive fan/system alerts).
   - Notion Credentials (`NOTION_TOKEN`, `EXPENSE_DB_ID`, `CATEGORY_DB_ID`) for the tracker to work.
   - `DOWNLOAD_DIR`: Where `/dl` should save files.

5. **Running the Bot Manually:**
   ```bash
   python main.py
   ```

## Running as a Systemd Service

To keep the bot running automatically in the background, you can set it up as a systemd service.

1. Create a service file:
   ```bash
   sudo nano /etc/systemd/system/telegram-bot.service
   ```

2. Add the following configuration (adjust usernames/paths as necessary):
   ```ini
   [Unit]
   Description=Telegram AI Bot
   After=network.target

   [Service]
   Type=simple
   User=your_username
   Group=your_username
   WorkingDirectory=/home/your_username/automation
   ExecStart=/home/your_username/automation/venv/bin/python /home/your_username/automation/main.py
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable and Start the Service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable telegram-bot.service
   sudo systemctl start telegram-bot.service
   ```

4. Check the Status:
   ```bash
   sudo systemctl status telegram-bot.service
   ```

## Commands

| Command           | Description |
|-------------------|-------------|
| `/start`          | Check if the bot is online and see commands. |
| `/run <cmd>`      | Execute a bash command and return the output. |
| `/system`         | Check current CPU, RAM, and Disk metrics. |
| `/fans`           | Check current fan speeds and temperatures. |
| `/ex <item> <amt> <cat>`| Add an expense to Notion. |
| `/cat`            | List available categories from Notion database. |
| `/dl <link>`      | Download media to the configured `DOWNLOAD_DIR`. |
| `(Any Text)`      | Chat natively with the Local AI. |
