import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "your-discord-bot-token-here")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "123456789")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "super-secret")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:8000/auth/callback")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = os.getenv("DATABASE_URL", "")
# Clean up if user accidentally included the variable name or quotes
if DATABASE_URL.startswith("DATABASE_URL="):
    DATABASE_URL = DATABASE_URL[13:]
DATABASE_URL = DATABASE_URL.strip('"').strip("'").strip()

if not DATABASE_URL:
    DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(BASE_DIR, 'virexa.db')}"
DEFAULT_PREFIX = os.getenv("DEFAULT_PREFIX", "/")
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-dashboard-key")
