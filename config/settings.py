import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8764406228:AAHzk2iNSLDKoI5mmN0zWwEJF7f2mYHrCQ4")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/agent_db")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3")
