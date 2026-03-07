import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "your-discord-bot-token-here")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "123456789")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "super-secret")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:8000/auth/callback")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./virexa.db")
DEFAULT_PREFIX = os.getenv("DEFAULT_PREFIX", "/")
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-dashboard-key")
