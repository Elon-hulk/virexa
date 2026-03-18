import discord
from discord import app_commands
from discord.ext import commands
import os
import datetime
import asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.future import select

# ─────────────────────────────────────────────
# CONFIG — loads from .env file
# ─────────────────────────────────────────────
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "your-discord-bot-token-here")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Cleanup DATABASE_URL if accidentally duplicated
if DATABASE_URL.startswith("DATABASE_URL="):
    DATABASE_URL = DATABASE_URL[13:]
DATABASE_URL = DATABASE_URL.strip('"').strip("'").strip()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if not DATABASE_URL:
    DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(BASE_DIR, 'virexa.db')}"

# ─────────────────────────────────────────────
# DATABASE MODELS
# ─────────────────────────────────────────────
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    discord_id = Column(String, unique=True, index=True)
    username = Column(String)
    avatar = Column(String, nullable=True)
    access_token = Column(String)
    refresh_token = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    discord_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Server(Base):
    __tablename__ = "servers"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(String, unique=True, index=True)
    log_channel_id = Column(String, nullable=True)
    prefix = Column(String, default="/")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    events = relationship("Event", back_populates="server")
    logs = relationship("Log", back_populates="server")

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(String, ForeignKey("servers.guild_id"))
    event_name = Column(String)
    enabled = Column(Boolean, default=False)
    server = relationship("Server", back_populates="events")

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(String, ForeignKey("servers.guild_id"))
    event_type = Column(String)
    user_id = Column(String)
    description = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    server = relationship("Server", back_populates="logs")

# ─────────────────────────────────────────────
# DATABASE CONNECTION
# ─────────────────────────────────────────────
def _build_engine(url: str):
    """Build async engine, stripping unsupported params from asyncpg URLs."""
    import re
    connect_args = {}
    url_lc = (url or "").lower()

    if "pooler.supabase.com" in url_lc or ":6543" in url_lc:
        connect_args["statement_cache_size"] = 0

    # asyncpg does not accept sslmode in the URL — move it to connect_args
    if "postgresql" in url_lc or "postgres" in url_lc:
        ssl_match = re.search(r"[?&]sslmode=([^&]+)", url)
        if ssl_match:
            ssl_val = ssl_match.group(1).lower()
            # Remove sslmode from URL
            url = re.sub(r"[?&]sslmode=[^&]*", "", url).rstrip("?&")
            if ssl_val in ("require", "verify-ca", "verify-full"):
                connect_args["ssl"] = True
            elif ssl_val == "disable":
                connect_args["ssl"] = False

    return create_async_engine(url, echo=False, pool_pre_ping=True, connect_args=connect_args)

try:
    engine = _build_engine(DATABASE_URL)
except Exception as e:
    print(f"Failed to create engine: {e}")
    engine = create_async_engine("sqlite+aiosqlite:///./virexa.db")

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Database initialized.")
    except Exception as e:
        print(f"Database initialization failed: {e}")

# ─────────────────────────────────────────────
# EVENT LOGGING HELPER
# ─────────────────────────────────────────────
async def log_event_to_db(guild_id, event_type, user_id, description):
    async with AsyncSessionLocal() as session:
        stmt = select(Event).where(Event.guild_id == str(guild_id), Event.event_name == event_type)
        result = await session.execute(stmt)
        event = result.scalar_one_or_none()
        if event and event.enabled:
            log_entry = Log(
                guild_id=str(guild_id),
                event_type=event_type,
                user_id=str(user_id),
                description=description,
                timestamp=datetime.datetime.utcnow()
            )
            session.add(log_entry)
            await session.commit()
            stmt_server = select(Server).where(Server.guild_id == str(guild_id))
            result_server = await session.execute(stmt_server)
            server = result_server.scalar_one_or_none()
            if server and server.log_channel_id:
                return int(server.log_channel_id)
    return None

# ─────────────────────────────────────────────
# BOT SETUP
# ─────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

class VirexaBot(commands.Bot):
    async def setup_hook(self):
        await init_db()
        await self.tree.sync()
        print("Slash commands synced.")

bot = VirexaBot(command_prefix="/", intents=intents)

# ─────────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Virexa bot is ready.")

@bot.event
async def on_guild_join(guild):
    async with AsyncSessionLocal() as session:
        stmt = select(Server).where(Server.guild_id == str(guild.id))
        result = await session.execute(stmt)
        server = result.scalar_one_or_none()
        if not server:
            session.add(Server(guild_id=str(guild.id)))
            default_events = [
                "member_join", "member_remove", "bot_add",
                "member_update_name", "member_update_nick",
                "role_add", "role_remove", "role_create", "role_delete",
                "channel_create", "channel_delete"
            ]
            for ev in default_events:
                session.add(Event(guild_id=str(guild.id), event_name=ev, enabled=False))
            await session.commit()

@bot.event
async def on_member_join(member):
    ts = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    if member.bot:
        channel_id = await log_event_to_db(member.guild.id, "bot_add", member.id, f"Bot joined: {member.name}")
    else:
        channel_id = await log_event_to_db(member.guild.id, "member_join", member.id, f"Member joined: {member.name}")
    if channel_id:
        ch = member.guild.get_channel(channel_id)
        if ch:
            await ch.send(f"[{ts}] **Join**: <@{member.id}> ({member.id}) joined the server.")

@bot.event
async def on_member_remove(member):
    ts = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    channel_id = await log_event_to_db(member.guild.id, "member_remove", member.id, f"Member left: {member.name}")
    if channel_id:
        ch = member.guild.get_channel(channel_id)
        if ch:
            await ch.send(f"[{ts}] **Leave**: {member.name} ({member.id}) left the server.")

@bot.event
async def on_member_update(before, after):
    ts = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    if before.name != after.name:
        channel_id = await log_event_to_db(after.guild.id, "member_update_name", after.id, f"Name changed from {before.name} to {after.name}")
        if channel_id:
            ch = after.guild.get_channel(channel_id)
            if ch:
                await ch.send(f"[{ts}] **Name Change**: {before.name} -> {after.name}")
    if before.nick != after.nick:
        channel_id = await log_event_to_db(after.guild.id, "member_update_nick", after.id, f"Nick changed from {before.nick} to {after.nick}")
        if channel_id:
            ch = after.guild.get_channel(channel_id)
            if ch:
                await ch.send(f"[{ts}] **Nickname Change**: <@{after.id}> changed nickname to {after.nick}")
    for role in [r for r in after.roles if r not in before.roles]:
        channel_id = await log_event_to_db(after.guild.id, "role_add", after.id, f"Role added: {role.name}")
        if channel_id:
            ch = after.guild.get_channel(channel_id)
            if ch:
                await ch.send(f"[{ts}] **Role Added**: <@{after.id}> was given the {role.name} role.")
    for role in [r for r in before.roles if r not in after.roles]:
        channel_id = await log_event_to_db(after.guild.id, "role_remove", after.id, f"Role removed: {role.name}")
        if channel_id:
            ch = after.guild.get_channel(channel_id)
            if ch:
                await ch.send(f"[{ts}] **Role Removed**: <@{after.id}> lost the {role.name} role.")

@bot.event
async def on_guild_role_create(role):
    ts = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    channel_id = await log_event_to_db(role.guild.id, "role_create", role.id, f"Role created: {role.name}")
    if channel_id:
        ch = role.guild.get_channel(channel_id)
        if ch:
            await ch.send(f"[{ts}] **Role Created**: {role.name}")

@bot.event
async def on_guild_role_delete(role):
    ts = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    channel_id = await log_event_to_db(role.guild.id, "role_delete", role.id, f"Role deleted: {role.name}")
    if channel_id:
        ch = role.guild.get_channel(channel_id)
        if ch:
            await ch.send(f"[{ts}] **Role Deleted**: {role.name}")

@bot.event
async def on_guild_channel_create(channel):
    ts = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    channel_id = await log_event_to_db(channel.guild.id, "channel_create", channel.id, f"Channel created: {channel.name}")
    if channel_id:
        log_chan = channel.guild.get_channel(channel_id)
        if log_chan:
            await log_chan.send(f"[{ts}] **Channel Created**: #{channel.name}")

@bot.event
async def on_guild_channel_delete(channel):
    ts = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    channel_id = await log_event_to_db(channel.guild.id, "channel_delete", channel.id, f"Channel deleted: {channel.name}")
    if channel_id:
        log_chan = channel.guild.get_channel(channel_id)
        if log_chan:
            await log_chan.send(f"[{ts}] **Channel Deleted**: #{channel.name}")

# ─────────────────────────────────────────────
# SLASH COMMANDS
# ─────────────────────────────────────────────
@bot.tree.command(name="setup", description="Initial configuration wizard for Virexa")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setup(interaction: discord.Interaction):
    await interaction.response.send_message("Setup starting! Configure using /setlog, /setprefix, /enableevent.", ephemeral=True)
    async with AsyncSessionLocal() as session:
        stmt = select(Server).where(Server.guild_id == str(interaction.guild_id))
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            session.add(Server(guild_id=str(interaction.guild_id)))
            await session.commit()

@bot.tree.command(name="setlog", description="Set the server log channel")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setlog(interaction: discord.Interaction, channel: discord.TextChannel):
    async with AsyncSessionLocal() as session:
        stmt = select(Server).where(Server.guild_id == str(interaction.guild_id))
        result = await session.execute(stmt)
        server = result.scalar_one_or_none()
        if server:
            server.log_channel_id = str(channel.id)
            await session.commit()
            await interaction.response.send_message(f"Log channel set to {channel.mention}", ephemeral=True)
        else:
            await interaction.response.send_message("Server not initialized. Run /setup first.", ephemeral=True)

@bot.tree.command(name="setprefix", description="Change command prefix")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setprefix(interaction: discord.Interaction, prefix: str):
    async with AsyncSessionLocal() as session:
        stmt = select(Server).where(Server.guild_id == str(interaction.guild_id))
        result = await session.execute(stmt)
        server = result.scalar_one_or_none()
        if server:
            server.prefix = prefix
            await session.commit()
            await interaction.response.send_message(f"Prefix set to `{prefix}`", ephemeral=True)
        else:
            await interaction.response.send_message("Server not initialized. Run /setup first.", ephemeral=True)

@bot.tree.command(name="enableevent", description="Enable a logging event")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_enableevent(interaction: discord.Interaction, event_name: str):
    valid_events = ["member_join", "member_remove", "bot_add", "member_update_name",
                    "member_update_nick", "role_add", "role_remove", "role_create",
                    "role_delete", "channel_create", "channel_delete"]
    if event_name not in valid_events:
        await interaction.response.send_message(f"Invalid event. Valid: {', '.join(valid_events)}", ephemeral=True)
        return
    async with AsyncSessionLocal() as session:
        stmt = select(Event).where(Event.guild_id == str(interaction.guild_id), Event.event_name == event_name)
        result = await session.execute(stmt)
        event = result.scalar_one_or_none()
        if event:
            event.enabled = True
        else:
            session.add(Event(guild_id=str(interaction.guild_id), event_name=event_name, enabled=True))
        await session.commit()
        await interaction.response.send_message(f"Event `{event_name}` enabled.", ephemeral=True)

@bot.tree.command(name="disableevent", description="Disable a logging event")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_disableevent(interaction: discord.Interaction, event_name: str):
    async with AsyncSessionLocal() as session:
        stmt = select(Event).where(Event.guild_id == str(interaction.guild_id), Event.event_name == event_name)
        result = await session.execute(stmt)
        event = result.scalar_one_or_none()
        if event:
            event.enabled = False
            await session.commit()
            await interaction.response.send_message(f"Event `{event_name}` disabled.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Event `{event_name}` not found.", ephemeral=True)

@bot.tree.command(name="status", description="Show bot configuration and status")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_status(interaction: discord.Interaction):
    async with AsyncSessionLocal() as session:
        stmt = select(Server).where(Server.guild_id == str(interaction.guild_id))
        result = await session.execute(stmt)
        server = result.scalar_one_or_none()
        if server:
            log_ch = f"<#{server.log_channel_id}>" if server.log_channel_id else "Not Set"
            stmt_ev = select(Event).where(Event.guild_id == str(interaction.guild_id), Event.enabled == True)
            result_ev = await session.execute(stmt_ev)
            events = result_ev.scalars().all()
            enabled_evs = ", ".join([e.event_name for e in events]) or "None"
            embed = discord.Embed(title="Virexa Status", color=0x00aaff)
            embed.add_field(name="Ping", value=f"{round(bot.latency * 1000)}ms", inline=False)
            embed.add_field(name="Log Channel", value=log_ch, inline=False)
            embed.add_field(name="Prefix", value=server.prefix, inline=False)
            embed.add_field(name="Enabled Events", value=enabled_evs, inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Server not initialized. Run /setup first.", ephemeral=True)

# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────
async def main():
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    if not DISCORD_TOKEN or DISCORD_TOKEN == "your-discord-bot-token-here":
        print("ERROR: Please set DISCORD_TOKEN in your .env file.")
    else:
        asyncio.run(main())
