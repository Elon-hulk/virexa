import discord
from discord.ext import commands
import fastapi
import uvicorn
import asyncio
import os
import sys
import logging
from uvicorn import Config, Server

# Add the root directory to PYTHONPATH so imports work correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import DISCORD_TOKEN
from bot.events import setup_events
from bot.commands import setup_commands
from database.connection import init_db

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("Virexa bot is ready.")

bot = VirexaBot()

# 3. Main async function
async def main():
    if DISCORD_TOKEN == "your-discord-bot-token-here":
        logger.error("Please configure your DISCORD_TOKEN in the .env file.")
        sys.exit(1)
    
    # Use port from environment or default
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting FastAPI on port {port}")
    
    # Start FastAPI server in the same event loop
    config = Config(app, host="0.0.0.0", port=port, loop="none")
    server = Server(config)
    asyncio.create_task(server.serve())
    
    logger.info("Starting Discord bot")
    try:
        await bot.start(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

# 4. Run the main function
if __name__ == "__main__":
    asyncio.run(main())