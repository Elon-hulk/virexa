import discord
from discord.ext import commands
import os
import sys

# Add the root directory to PYTHONPATH so imports work correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import DISCORD_TOKEN
from bot.events import setup_events
from bot.commands import setup_commands
from database.connection import init_db

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

if __name__ == "__main__":
    if DISCORD_TOKEN == "your-discord-bot-token-here":
        print("Please configure your DISCORD_TOKEN in the .env file.")
    else:
        bot.run(DISCORD_TOKEN)
