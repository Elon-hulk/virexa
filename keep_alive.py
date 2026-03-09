import discord
from discord.ext import commands
import fastapi
import uvicorn
import asyncio
import os
import sys
from threading import Thread

# Add the root directory to PYTHONPATH so imports work correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import DISCORD_TOKEN
from bot.events import setup_events
from bot.commands import setup_commands
from database.connection import init_db

# 1. Setup FastAPI
app = fastapi.FastAPI()

@app.get("/")
async def read_root():
    return {"status": "Bot is Online", "message": "24/7 Uptime Active"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 2. Setup Discord Bot (using your existing VirexaBot class)
class VirexaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.presences = True
        
        super().__init__(command_prefix="/", intents=intents)

    async def setup_hook(self):
        await init_db()
        await setup_events(self)
        await setup_commands(self)
        await self.tree.sync()

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("Virexa bot is ready.")

bot = VirexaBot()

# 3. Function to run FastAPI
def run_fastapi():
    # Use port 8080 or the one provided by your host (e.g., Render sets $PORT)
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

# 4. Main execution
if __name__ == "__main__":
    if DISCORD_TOKEN == "your-discord-bot-token-here":
        print("Please configure your DISCORD_TOKEN in the .env file.")
        sys.exit(1)
    
    # Start FastAPI in a separate thread
    web_thread = Thread(target=run_fastapi, daemon=True)
    web_thread.start()
    
    # Start the Discord Bot
    bot.run(DISCORD_TOKEN)