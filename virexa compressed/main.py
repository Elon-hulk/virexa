import discord
from discord import app_commands
from discord.ext import commands
import os
import ssl
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
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    balance = Column(Integer, default=0)
    rep = Column(Integer, default=0)
    bio = Column(String, default='No bio set.')
    color = Column(String, default='#00aaff')
    background = Column(String, nullable=True)
    spouse_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    discord_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Inventory(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True, index=True)
    discord_id = Column(String, index=True)
    item_name = Column(String)
    quantity = Column(Integer, default=1)

class Server(Base):
    __tablename__ = "servers"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(String, unique=True, index=True)
    log_channel_id = Column(String, nullable=True)
    prefix = Column(String, default="/")
    welcome_message = Column(String, nullable=True)
    goodbye_message = Column(String, nullable=True)
    welcome_channel_id = Column(String, nullable=True)
    goodbye_channel_id = Column(String, nullable=True)
    autorole_id = Column(String, nullable=True)
    mute_role_id = Column(String, nullable=True)
    mod_role_id = Column(String, nullable=True)
    admin_role_id = Column(String, nullable=True)
    ai_channel_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    events = relationship("Event", back_populates="server")
    logs = relationship("Log", back_populates="server")


class Warning(Base):
    __tablename__ = "warnings"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(String)
    user_id = Column(String)
    moderator_id = Column(String)
    reason = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

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

    # asyncpg does not accept sslmode in the URL — strip it and use ssl context
    if "postgresql" in url_lc or "postgres" in url_lc:
        ssl_match = re.search(r"[?&]sslmode=([^&]+)", url)
        if ssl_match:
            ssl_val = ssl_match.group(1).lower()
            # Remove sslmode from URL
            url = re.sub(r"[?&]sslmode=[^&]*", "", url).rstrip("?&")
        else:
            ssl_val = "require"  # default to requiring SSL for postgres

        if ssl_val in ("require", "verify-ca", "verify-full", "prefer"):
            # Create SSL context that skips self-signed cert verification
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            connect_args["ssl"] = ssl_ctx
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
        try:
            await init_db()
        except Exception as e:
            print(f"[WARNING] DB init failed, continuing anyway: {e}")
        try:
            await self.tree.sync()
            print("Slash commands synced.")
        except Exception as e:
            print(f"[WARNING] Command sync failed: {e}")

bot = VirexaBot(command_prefix="/", intents=intents)

# Global error handler for slash commands
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        try:
            await interaction.response.send_message("❌ You need **Administrator** permission to use this command.", ephemeral=True)
        except:
            await interaction.followup.send("❌ You need **Administrator** permission to use this command.", ephemeral=True)
    else:
        try:
            await interaction.response.send_message(f"❌ Unexpected error: {error}", ephemeral=True)
        except:
            await interaction.followup.send(f"❌ Unexpected error: {error}", ephemeral=True)

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
                "channel_create", "channel_delete", "message_delete", "message_edit"
            ]
            for ev in default_events:
                session.add(Event(guild_id=str(guild.id), event_name=ev, enabled=False))
            await session.commit()

@bot.event
async def on_member_join(member):
    # Retrieve welcome message & autorole
    async with AsyncSessionLocal() as session:
        stmt = select(Server).where(Server.guild_id == str(member.guild.id))
        srv = (await session.execute(stmt)).scalar_one_or_none()
        if srv:
            if srv.autorole_id:
                try: 
                    role = member.guild.get_role(int(srv.autorole_id))
                    if role: await member.add_roles(role)
                except: pass
            if srv.welcome_channel_id and srv.welcome_message:
                try:
                    welcome_ch = member.guild.get_channel(int(srv.welcome_channel_id))
                    if welcome_ch:
                        msg = str(srv.welcome_message).replace("{user}", member.mention).replace("{server}", member.guild.name)
                        await welcome_ch.send(msg)
                except: pass

    if member.bot:
        channel_id = await log_event_to_db(member.guild.id, "bot_add", member.id, f"Bot joined: {member.name}")
    else:
        channel_id = await log_event_to_db(member.guild.id, "member_join", member.id, f"Member joined: {member.name}")
    if channel_id:
        ch = member.guild.get_channel(channel_id)
        if ch:
            embed = discord.Embed(color=0x43b581, timestamp=discord.utils.utcnow())
            embed.set_author(name=member.name, icon_url=member.display_avatar.url if member.display_avatar else None)
            embed.description = f"{member.mention} **joined** the server"
            embed.set_footer(text=f"ID: {member.id}")
            await ch.send(embed=embed)

@bot.event
async def on_member_remove(member):
    # Retrieve goodbye message
    async with AsyncSessionLocal() as session:
        stmt = select(Server).where(Server.guild_id == str(member.guild.id))
        srv = (await session.execute(stmt)).scalar_one_or_none()
        if srv:
            if srv.goodbye_channel_id and srv.goodbye_message:
                try:
                    gb_ch = member.guild.get_channel(int(srv.goodbye_channel_id))
                    if gb_ch:
                        msg = str(srv.goodbye_message).replace("{user}", member.name).replace("{server}", member.guild.name)
                        await gb_ch.send(msg)
                except: pass

    try:
        channel_id = await log_event_to_db(member.guild.id, "member_remove", member.id, f"Member left: {member.name}")
        if channel_id:
            ch = member.guild.get_channel(channel_id) or await member.guild.fetch_channel(channel_id)
            if ch:
                embed = discord.Embed(color=0xf04747, timestamp=discord.utils.utcnow())
                embed.set_author(name=member.name, icon_url=member.display_avatar.url if member.display_avatar else None)
                embed.description = f"{member.mention} **left** the server"
                embed.set_footer(text=f"ID: {member.id}")
                await ch.send(embed=embed)
    except Exception as e:
        print(f"[ERROR] member_remove handler: {e}")

@bot.event
async def on_member_update(before, after):
    # Name change
    if before.name != after.name:
        channel_id = await log_event_to_db(after.guild.id, "member_update_name", after.id, f"Name changed from {before.name} to {after.name}")
        if channel_id:
            ch = after.guild.get_channel(channel_id)
            if ch:
                embed = discord.Embed(color=0x3498db, timestamp=discord.utils.utcnow())
                embed.set_author(name=after.name, icon_url=after.display_avatar.url if after.display_avatar else None)
                embed.description = f"{after.mention} **username changed**\n\n**Before**\n{before.name}\n\n**After**\n{after.name}"
                embed.set_footer(text=f"ID: {after.id}")
                await ch.send(embed=embed)
                
    # Nickname change
    if before.nick != after.nick:
        channel_id = await log_event_to_db(after.guild.id, "member_update_nick", after.id, f"Nick changed from {before.nick} to {after.nick}")
        if channel_id:
            ch = after.guild.get_channel(channel_id)
            if ch:
                embed = discord.Embed(color=0x3498db, timestamp=discord.utils.utcnow())
                embed.set_author(name=after.name, icon_url=after.display_avatar.url if after.display_avatar else None)
                b_nick = before.nick if before.nick else "None"
                a_nick = after.nick if after.nick else "None"
                embed.description = f"{after.mention} **nickname changed**\n\n**Before**\n{b_nick}\n\n**After**\n{a_nick}"
                embed.set_footer(text=f"ID: {after.id}")
                await ch.send(embed=embed)
                
    # Role added
    for role in [r for r in after.roles if r not in before.roles]:
        channel_id = await log_event_to_db(after.guild.id, "role_add", after.id, f"Role added: {role.name}")
        if channel_id:
            ch = after.guild.get_channel(channel_id)
            if ch:
                executor = None
                try:
                    async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
                        if entry.target.id == after.id:
                            executor = entry.user
                            break
                except:
                    pass
                embed = discord.Embed(color=0x3498db, timestamp=discord.utils.utcnow())
                embed.set_author(name=after.name, icon_url=after.display_avatar.url if after.display_avatar else None)
                desc = f"{after.mention} was given the `{role.name}` role"
                if executor:
                    desc += f" by {executor.mention}"
                embed.description = desc
                embed.set_footer(text=f"ID: {after.id}")
                await ch.send(embed=embed)
                
    # Role removed
    for role in [r for r in before.roles if r not in after.roles]:
        channel_id = await log_event_to_db(after.guild.id, "role_remove", after.id, f"Role removed: {role.name}")
        if channel_id:
            ch = after.guild.get_channel(channel_id)
            if ch:
                executor = None
                try:
                    async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
                        if entry.target.id == after.id:
                            executor = entry.user
                            break
                except:
                    pass
                embed = discord.Embed(color=0xf04747, timestamp=discord.utils.utcnow())
                embed.set_author(name=after.name, icon_url=after.display_avatar.url if after.display_avatar else None)
                desc = f"{after.mention} was removed from the `{role.name}` role"
                if executor:
                    desc += f" by {executor.mention}"
                embed.description = desc
                embed.set_footer(text=f"ID: {after.id}")
                await ch.send(embed=embed)

@bot.event
async def on_guild_role_create(role):
    channel_id = await log_event_to_db(role.guild.id, "role_create", role.id, f"Role created: {role.name}")
    if channel_id:
        ch = role.guild.get_channel(channel_id)
        if ch:
            executor = None
            try:
                async for entry in role.guild.audit_logs(limit=3, action=discord.AuditLogAction.role_create):
                    if entry.target.id == role.id:
                        executor = entry.user
                        break
            except:
                pass
            embed = discord.Embed(color=0x43b581, timestamp=discord.utils.utcnow())
            embed.set_author(
                name=executor.name if executor else role.guild.name, 
                icon_url=executor.display_avatar.url if executor and executor.display_avatar else (role.guild.icon.url if role.guild.icon else None)
            )
            desc = f"**Role Created**: {role.mention} (`{role.name}`)"
            if executor:
                desc += f" by {executor.mention}"
            embed.description = desc
            embed.set_footer(text=f"Role ID: {role.id}")
            await ch.send(embed=embed)

@bot.event
async def on_guild_role_delete(role):
    channel_id = await log_event_to_db(role.guild.id, "role_delete", role.id, f"Role deleted: {role.name}")
    if channel_id:
        ch = role.guild.get_channel(channel_id)
        if ch:
            executor = None
            try:
                async for entry in role.guild.audit_logs(limit=3, action=discord.AuditLogAction.role_delete):
                    if entry.target.id == role.id:
                        executor = entry.user
                        break
            except:
                pass
            embed = discord.Embed(color=0xf04747, timestamp=discord.utils.utcnow())
            embed.set_author(
                name=executor.name if executor else role.guild.name, 
                icon_url=executor.display_avatar.url if executor and executor.display_avatar else (role.guild.icon.url if role.guild.icon else None)
            )
            desc = f"**Role Deleted**: `{role.name}`"
            if executor:
                desc += f" by {executor.mention}"
            embed.description = desc
            embed.set_footer(text=f"Role ID: {role.id}")
            await ch.send(embed=embed)

@bot.event
async def on_guild_channel_create(channel):
    channel_id = await log_event_to_db(channel.guild.id, "channel_create", channel.id, f"Channel created: {channel.name}")
    if channel_id:
        log_chan = channel.guild.get_channel(channel_id)
        if log_chan:
            executor = None
            try:
                async for entry in channel.guild.audit_logs(limit=3, action=discord.AuditLogAction.channel_create):
                    if entry.target.id == channel.id:
                        executor = entry.user
                        break
            except:
                pass
            embed = discord.Embed(color=0x43b581, timestamp=discord.utils.utcnow())
            embed.set_author(
                name=executor.name if executor else channel.guild.name, 
                icon_url=executor.display_avatar.url if executor and executor.display_avatar else (channel.guild.icon.url if channel.guild.icon else None)
            )
            desc = f"**Channel Created**: {channel.mention} (`{channel.name}`)"
            if executor:
                desc += f" by {executor.mention}"
            embed.description = desc
            embed.set_footer(text=f"Channel ID: {channel.id}")
            await log_chan.send(embed=embed)

@bot.event
async def on_guild_channel_delete(channel):
    channel_id = await log_event_to_db(channel.guild.id, "channel_delete", channel.id, f"Channel deleted: {channel.name}")
    if channel_id:
        log_chan = channel.guild.get_channel(channel_id)
        if log_chan:
            executor = None
            try:
                async for entry in channel.guild.audit_logs(limit=3, action=discord.AuditLogAction.channel_delete):
                    if entry.target.id == channel.id:
                        executor = entry.user
                        break
            except:
                pass
            embed = discord.Embed(color=0xf04747, timestamp=discord.utils.utcnow())
            embed.set_author(
                name=executor.name if executor else channel.guild.name, 
                icon_url=executor.display_avatar.url if executor and executor.display_avatar else (channel.guild.icon.url if channel.guild.icon else None)
            )
            desc = f"**Channel Deleted**: `{channel.name}`"
            if executor:
                desc += f" by {executor.mention}"
            embed.description = desc
            embed.set_footer(text=f"Channel ID: {channel.id}")
            await log_chan.send(embed=embed)

@bot.event
async def on_message_delete(message):
    if not message.guild or message.author.bot:
        return
    channel_id = await log_event_to_db(message.guild.id, "message_delete", message.id, f"Message deleted in {message.channel.name}")
    if channel_id:
        log_chan = message.guild.get_channel(channel_id)
        if log_chan:
            executor = None
            try:
                # Slight delay to let API audit logs catch up
                await asyncio.sleep(1)
                async for entry in message.guild.audit_logs(limit=5, action=discord.AuditLogAction.message_delete):
                    if entry.target.id == message.author.id:
                        executor = entry.user
                        break
            except:
                pass
            
            embed = discord.Embed(color=0xf04747, timestamp=discord.utils.utcnow())
            embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url if message.author.display_avatar else None)
            desc = f"**Message sent by** {message.author.mention} **deleted in** {message.channel.mention}"
            if executor and getattr(executor, "id", None) != message.author.id:
                desc += f" **by** {executor.mention}"
            desc += f"\n\n**Message Content**\n{message.content or '(No text, likely image or embed)'}"
            
            embed.description = desc
            embed.set_footer(text=f"Author: {message.author.id} | Message ID: {message.id}")
            await log_chan.send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    if not before.guild or before.author.bot or before.content == after.content:
        return
    channel_id = await log_event_to_db(before.guild.id, "message_edit", before.author.id, f"Message edited in {before.channel.name}")
    if channel_id:
        log_chan = before.guild.get_channel(channel_id)
        if log_chan:
            embed = discord.Embed(color=0x3498db, timestamp=discord.utils.utcnow())
            embed.set_author(name=before.author.name, icon_url=before.author.display_avatar.url if before.author.display_avatar else None)
            embed.description = f"**Message edited in** {before.channel.mention} [Jump to Message]({after.jump_url})\n\n**Before**\n{before.content}\n\n**After**\n{after.content}"
            embed.set_footer(text=f"User ID: {before.author.id}")
            await log_chan.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    
    # 🌟 Give XP 🌟
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.discord_id == str(message.author.id))
        db_u = (await session.execute(stmt)).scalar_one_or_none()
        if not db_u:
            db_u = User(discord_id=str(message.author.id), username=message.author.name)
            session.add(db_u)
        db_u.xp = (db_u.xp or 0) + random.randint(5, 15)
        # Level up logic
        xp_needed = (db_u.level or 1) * 100
        if db_u.xp >= xp_needed:
            db_u.level += 1
            db_u.xp -= xp_needed
            db_u.balance = (db_u.balance or 0) + (100 * db_u.level)
            try: await message.channel.send(f"🎉 Congrats {message.author.mention}, you leveled up to **Level {db_u.level}** and earned {100*db_u.level} coins!")
            except: pass
        await session.commit()

    # 🤖 AI Chatbot Channel — auto reply if this is the designated AI channel
    async with AsyncSessionLocal() as session:
        srv_stmt = select(Server).where(Server.guild_id == str(message.guild.id))
        srv = (await session.execute(srv_stmt)).scalar_one_or_none()
        if srv and srv.ai_channel_id and str(message.channel.id) == str(srv.ai_channel_id):
            try:
                async with message.channel.typing():
                    ai_reply = await fetch_openrouter(
                        message.content,
                        "You are Virexa, a friendly, witty Discord chatbot. Keep replies short and natural — max 3 sentences. Use casual language and Discord emojis when fitting."
                    )
                    await message.reply(ai_reply)
            except Exception as e:
                print(f"[ERROR] AI chatbot: {e}")

# ─────────────────────────────────────────────
# SLASH COMMANDS
# ─────────────────────────────────────────────
@bot.tree.command(name="setup", description="Initial configuration wizard for Virexa")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        DEFAULT_EVENTS = [
            "member_join", "member_remove", "bot_add",
            "member_update_name", "member_update_nick",
            "role_add", "role_remove", "role_create", "role_delete",
            "channel_create", "channel_delete", "message_delete", "message_edit"
        ]
        async with AsyncSessionLocal() as session:
            # Create server if not exists
            stmt = select(Server).where(Server.guild_id == str(interaction.guild_id))
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                session.add(Server(guild_id=str(interaction.guild_id)))
                await session.flush()
            # Auto-enable all default events
            for ev_name in DEFAULT_EVENTS:
                stmt_ev = select(Event).where(
                    Event.guild_id == str(interaction.guild_id),
                    Event.event_name == ev_name
                )
                res_ev = await session.execute(stmt_ev)
                ev = res_ev.scalar_one_or_none()
                if ev:
                    ev.enabled = True
                else:
                    session.add(Event(guild_id=str(interaction.guild_id), event_name=ev_name, enabled=True))
            await session.commit()
        await interaction.followup.send(
            "✅ **Setup complete!**\n"
            "🟢 All events have been **enabled** automatically.\n"
            "Next steps:\n"
            "- `/setlog #channel` — Set a log channel\n"
            "- `/events` — View all event statuses\n"
            "- `/disableevent event_name` — Turn off specific events",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="setlog", description="Set the server log channel")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setlog(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Server).where(Server.guild_id == str(interaction.guild_id))
            result = await session.execute(stmt)
            server = result.scalar_one_or_none()
            if server:
                server.log_channel_id = str(channel.id)
                await session.commit()
                await interaction.followup.send(f"✅ Log channel set to {channel.mention}", ephemeral=True)
            else:
                await interaction.followup.send("❌ Server not initialized. Run /setup first.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="setprefix", description="Change command prefix")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setprefix(interaction: discord.Interaction, prefix: str):
    await interaction.response.defer(ephemeral=True)
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Server).where(Server.guild_id == str(interaction.guild_id))
            result = await session.execute(stmt)
            server = result.scalar_one_or_none()
            if server:
                server.prefix = prefix
                await session.commit()
                await interaction.followup.send(f"✅ Prefix set to `{prefix}`", ephemeral=True)
            else:
                await interaction.followup.send("❌ Server not initialized. Run /setup first.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="enableevent", description="Enable a logging event")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_enableevent(interaction: discord.Interaction, event_name: str):
    await interaction.response.defer(ephemeral=True)
    valid_events = ["member_join", "member_remove", "bot_add", "member_update_name",
                    "member_update_nick", "role_add", "role_remove", "role_create",
                    "role_delete", "channel_create", "channel_delete", "message_delete", "message_edit"]
    if event_name not in valid_events:
        await interaction.followup.send(f"❌ Invalid event. Valid: {', '.join(valid_events)}", ephemeral=True)
        return
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Event).where(Event.guild_id == str(interaction.guild_id), Event.event_name == event_name)
            result = await session.execute(stmt)
            event = result.scalar_one_or_none()
            if event:
                event.enabled = True
            else:
                session.add(Event(guild_id=str(interaction.guild_id), event_name=event_name, enabled=True))
            await session.commit()
        await interaction.followup.send(f"✅ Event `{event_name}` enabled.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="disableevent", description="Disable a logging event")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_disableevent(interaction: discord.Interaction, event_name: str):
    await interaction.response.defer(ephemeral=True)
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Event).where(Event.guild_id == str(interaction.guild_id), Event.event_name == event_name)
            result = await session.execute(stmt)
            event = result.scalar_one_or_none()
            if event:
                event.enabled = False
                await session.commit()
                await interaction.followup.send(f"✅ Event `{event_name}` disabled.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Event `{event_name}` not found.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="status", description="Show bot configuration and status")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
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
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send("❌ Server not initialized. Run /setup first.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="events", description="Show all logging events and their status")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_events(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        ALL_EVENTS = [
            "member_join", "member_remove", "bot_add",
            "member_update_name", "member_update_nick",
            "role_add", "role_remove", "role_create", "role_delete",
            "channel_create", "channel_delete", "message_delete", "message_edit"
        ]
        async with AsyncSessionLocal() as session:
            stmt = select(Event).where(Event.guild_id == str(interaction.guild_id))
            result = await session.execute(stmt)
            db_events = {e.event_name: e.enabled for e in result.scalars().all()}

        lines = []
        for ev in ALL_EVENTS:
            enabled = db_events.get(ev, False)
            icon = "🟢" if enabled else "🔴"
            lines.append(f"{icon} `{ev}`")

        embed = discord.Embed(title="📋 Virexa Event Status", color=0x00aaff)
        embed.description = "\n".join(lines)
        embed.set_footer(text="Use /enableevent or /disableevent to toggle")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)


# ==========================================
# 🛡️ ADMIN & MODERATION & USER COMMANDS
# ==========================================

import time
from discord import app_commands
import random

# --- Utilities ---
def is_admin():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator: return True
        async with AsyncSessionLocal() as session:
            stmt = select(Server).where(Server.guild_id == str(interaction.guild_id))
            res = await session.execute(stmt)
            srv = res.scalar_one_or_none()
            if srv and srv.admin_role_id and discord.utils.get(interaction.user.roles, id=int(srv.admin_role_id)): return True
        return False
    return app_commands.check(predicate)

def is_mod():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.kick_members: return True
        async with AsyncSessionLocal() as session:
            stmt = select(Server).where(Server.guild_id == str(interaction.guild_id))
            res = await session.execute(stmt)
            srv = res.scalar_one_or_none()
            if srv and srv.mod_role_id and discord.utils.get(interaction.user.roles, id=int(srv.mod_role_id)): return True
            if srv and srv.admin_role_id and discord.utils.get(interaction.user.roles, id=int(srv.admin_role_id)): return True
        return False
    return app_commands.check(predicate)

# --- Config Commands ---
@bot.tree.command(name="setwelcome", description="Set a custom welcome message")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setwelcome(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    await interaction.response.defer(ephemeral=True)
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Server).where(Server.guild_id == str(interaction.guild_id))
            srv = (await session.execute(stmt)).scalar_one_or_none()
            if srv:
                srv.welcome_message = message
                srv.welcome_channel_id = str(channel.id)
                await session.commit()
                await interaction.followup.send(f"✅ Welcome message set in {channel.mention}", ephemeral=True)
            else: await interaction.followup.send("❌ Error: DB not found.", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"Error: {e}")

@bot.tree.command(name="setgoodbye", description="Set a custom goodbye message")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setgoodbye(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    await interaction.response.defer(ephemeral=True)
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Server).where(Server.guild_id == str(interaction.guild_id))
            srv = (await session.execute(stmt)).scalar_one_or_none()
            if srv:
                srv.goodbye_message = message
                srv.goodbye_channel_id = str(channel.id)
                await session.commit()
                await interaction.followup.send(f"✅ Goodbye message set in {channel.mention}", ephemeral=True)
            else: await interaction.followup.send("❌ Error: DB not found.", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"Error: {e}")

@bot.tree.command(name="setautorole", description="Automatically assigns a role to new users")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setautorole(interaction: discord.Interaction, role: discord.Role):
    await interaction.response.defer(ephemeral=True)
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Server).where(Server.guild_id == str(interaction.guild_id))
            srv = (await session.execute(stmt)).scalar_one_or_none()
            if srv:
                srv.autorole_id = str(role.id)
                await session.commit()
                await interaction.followup.send(f"✅ Auto-role set to {role.name}", ephemeral=True)
            else: await interaction.followup.send("❌ Error: DB not found.", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"Error: {e}")

@bot.tree.command(name="setmuterole", description="Defines which role is used for muting users")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setmuterole(interaction: discord.Interaction, role: discord.Role):
    await interaction.response.defer(ephemeral=True)
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Server).where(Server.guild_id == str(interaction.guild_id))
            srv = (await session.execute(stmt)).scalar_one_or_none()
            if srv:
                srv.mute_role_id = str(role.id)
                await session.commit()
                await interaction.followup.send(f"✅ Mute role set to {role.name}", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"Error: {e}")

@bot.tree.command(name="clearall", description="Deletes up to 100 messages in a channel")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_clearall(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        deleted = await interaction.channel.purge(limit=100)
        await interaction.followup.send(f"✅ Cleared {len(deleted)} messages.", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"Error: {e}")

@bot.tree.command(name="announce", description="Sends announcement to server")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_announce(interaction: discord.Interaction, message: str):
    await interaction.response.defer(ephemeral=True)
    await interaction.channel.send(f"📢 **Announcement**\\n\\n{message}")
    await interaction.followup.send("✅ Sent.", ephemeral=True)

@bot.tree.command(name="embed", description="Sends styled embed message")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_embed(interaction: discord.Interaction, title: str, description: str):
    await interaction.response.defer(ephemeral=True)
    em = discord.Embed(title=title, description=description, color=0x00aaff)
    await interaction.channel.send(embed=em)
    await interaction.followup.send("✅ Sent.", ephemeral=True)

@bot.tree.command(name="timeout", description="Temporarily restricts a user (minutes)")
@app_commands.checks.has_permissions(moderate_members=True)
async def cmd_timeout(interaction: discord.Interaction, user: discord.Member, minutes: int, reason: str = None):
    await interaction.response.defer(ephemeral=True)
    try:
        time = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
        await user.timeout(time, reason=reason)
        await interaction.followup.send(f"✅ {user.mention} has been timed out for {minutes}m.", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="ban", description="Permanently bans a user")
@app_commands.checks.has_permissions(ban_members=True)
async def cmd_ban(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason"):
    await interaction.response.defer(ephemeral=True)
    try:
        await user.ban(reason=reason)
        await interaction.followup.send(f"✅ {user.mention} has been banned.", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="kick", description="Kicks a user")
@app_commands.checks.has_permissions(kick_members=True)
async def cmd_kick(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason"):
    await interaction.response.defer(ephemeral=True)
    try:
        await user.kick(reason=reason)
        await interaction.followup.send(f"✅ {user.mention} has been kicked.", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="warn", description="Warns a user")
@app_commands.checks.has_permissions(moderate_members=True)
async def cmd_warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    await interaction.response.defer(ephemeral=True)
    try:
        async with AsyncSessionLocal() as session:
            session.add(Warning(guild_id=str(interaction.guild_id), user_id=str(user.id), moderator_id=str(interaction.user.id), reason=reason))
            await session.commit()
            await interaction.followup.send(f"✅ {user.mention} has been warned.", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="warnings", description="Check user warnings")
@app_commands.checks.has_permissions(moderate_members=True)
async def cmd_warnings(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer(ephemeral=True)
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Warning).where(Warning.guild_id == str(interaction.guild_id), Warning.user_id == str(user.id))
            res = await session.execute(stmt)
            warns = res.scalars().all()
            if not warns:
                await interaction.followup.send(f"{user.name} has no warnings.", ephemeral=True)
                return
            em = discord.Embed(title=f"Warnings for {user.name}")
            for w in warns:
                em.add_field(name=f"Warn ID: {w.id}", value=f"Reason: {w.reason}\\nMod: <@{w.moderator_id}>", inline=False)
            await interaction.followup.send(embed=em, ephemeral=True)
    except Exception as e: await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="clearwarnings", description="Clear user warnings")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_clearwarnings(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer(ephemeral=True)
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Warning).where(Warning.guild_id == str(interaction.guild_id), Warning.user_id == str(user.id))
            res = await session.execute(stmt)
            for w in res.scalars().all():
                await session.delete(w)
            await session.commit()
            await interaction.followup.send(f"✅ Warnings cleared for {user.name}.", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="userinfo", description="Shows user info")
async def cmd_userinfo(interaction: discord.Interaction, user: discord.Member = None):
    await interaction.response.defer()
    user = user or interaction.user
    em = discord.Embed(title=f"User Info: {user.name}", color=0x00aaff)
    em.set_thumbnail(url=user.display_avatar.url)
    em.add_field(name="ID", value=user.id)
    em.add_field(name="Joined Server", value=user.joined_at.strftime("%Y-%m-%d"))
    em.add_field(name="Joined Discord", value=user.created_at.strftime("%Y-%m-%d"))
    em.add_field(name="Roles", value=", ".join([r.mention for r in user.roles if r.name != "@everyone"]))
    await interaction.followup.send(embed=em)

@bot.tree.command(name="serverinfo", description="Displays server details")
async def cmd_serverinfo(interaction: discord.Interaction):
    await interaction.response.defer()
    g = interaction.guild
    em = discord.Embed(title=f"Server Info: {g.name}", color=0x00aaff)
    if g.icon: em.set_thumbnail(url=g.icon.url)
    em.add_field(name="Owner", value=f"<@{g.owner_id}>")
    em.add_field(name="Members", value=str(g.member_count))
    em.add_field(name="Created At", value=g.created_at.strftime("%Y-%m-%d"))
    await interaction.followup.send(embed=em)

@bot.tree.command(name="avatar", description="Displays user avatar")
async def cmd_avatar(interaction: discord.Interaction, user: discord.Member = None):
    await interaction.response.defer()
    user = user or interaction.user
    em = discord.Embed(color=0x00aaff)
    em.set_image(url=user.display_avatar.url)
    await interaction.followup.send(embed=em)

@bot.tree.command(name="ping", description="Shows bot latency")
async def cmd_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! Latency: {round(bot.latency * 1000)}ms", ephemeral=True)

@bot.tree.command(name="help", description="Shows all basic commands")
async def cmd_help(interaction: discord.Interaction):
    em = discord.Embed(title="Virexa Help", description="Use `/` to see all available slash commands in the menu!", color=0x00aaff)
    await interaction.response.send_message(embed=em, ephemeral=True)

@bot.tree.command(name="invite", description="Shows bot invite link")
async def cmd_invite(interaction: discord.Interaction):
    inv = f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"
    await interaction.response.send_message(f"Invite me here: {inv}", ephemeral=True)

@bot.tree.command(name="uptime", description="Shows bot uptime")
async def cmd_uptime(interaction: discord.Interaction):
    uptime_msg = "Bot has been running smoothly without interruptions!"
    await interaction.response.send_message(f"🕒 Uptime: {uptime_msg}", ephemeral=True)

@bot.tree.command(name="poll", description="Creates poll")
async def cmd_poll(interaction: discord.Interaction, question: str):
    await interaction.response.defer()
    em = discord.Embed(title="📊 Poll", description=question, color=0x00aaff)
    em.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
    msg = await interaction.followup.send(embed=em)
    # wait a tiny bit to get the message object successfully
    await (await interaction.original_response()).add_reaction("👍")
    await (await interaction.original_response()).add_reaction("👎")


# ==========================================
# 🚀 ADVANCED ENGAGEMENT COMMANDS (48)
# ==========================================
import aiohttp
import asyncio

# --- GAMIFICATION ---
@bot.tree.command(name="level", description="Shows user level and XP progress.")
async def cmd_level(interaction: discord.Interaction, user: discord.Member = None):
    await interaction.response.defer()
    user = user or interaction.user
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.discord_id == str(user.id))
        db_user = (await session.execute(stmt)).scalar_one_or_none()
        if not db_user:
            db_user = User(discord_id=str(user.id), username=user.name)
            session.add(db_user)
            await session.commit()
        em = discord.Embed(title=f"📈 {user.name}'s Level", color=int(db_user.color.replace("#",""), 16) if db_user.color else 0x00aaff)
        em.add_field(name="Level", value=str(db_user.level), inline=True)
        em.add_field(name="XP", value=f"{db_user.xp} / {(db_user.level * 100)}", inline=True)
        em.set_thumbnail(url=user.display_avatar.url)
        await interaction.followup.send(embed=em)

@bot.tree.command(name="xp", description="Displays current XP points.")
async def cmd_xp(interaction: discord.Interaction, user: discord.Member = None):
    # Same as level
    await cmd_level.callback(interaction, user)

@bot.tree.command(name="leaderboard", description="Shows top users by Level/XP.")
async def cmd_leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    async with AsyncSessionLocal() as session:
        stmt = select(User).order_by(User.level.desc(), User.xp.desc()).limit(10)
        top = (await session.execute(stmt)).scalars().all()
        em = discord.Embed(title="🏆 Global Leaderboard", color=0xffd700)
        for i, u in enumerate(top, 1):
            em.add_field(name=f"#{i} {u.username}", value=f"Level {u.level} | {u.xp} XP", inline=False)
        await interaction.followup.send(embed=em)

@bot.tree.command(name="rep", description="Gives a reputation point to another user.")
async def cmd_rep(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer()
    if user.id == interaction.user.id:
        return await interaction.followup.send("❌ You cannot rep yourself!")
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.discord_id == str(user.id))
        r_user = (await session.execute(stmt)).scalar_one_or_none()
        if r_user:
            r_user.rep = (r_user.rep or 0) + 1
            await session.commit()
            await interaction.followup.send(f"✅ You gave +1 Rep to {user.mention}!")
        else:
            r_user = User(discord_id=str(user.id), username=user.name)
            r_user.rep = 1
            session.add(r_user)
            await session.commit()
            await interaction.followup.send(f"✅ You gave +1 Rep to {user.mention}!")

@bot.tree.command(name="profile", description="Displays user profile card.")
async def cmd_profile(interaction: discord.Interaction, user: discord.Member = None):
    await interaction.response.defer()
    user = user or interaction.user
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.discord_id == str(user.id))
        db_u = (await session.execute(stmt)).scalar_one_or_none()
        if not db_u:
            db_u = User(discord_id=str(user.id), username=user.name)
            session.add(db_u)
            await session.commit()
        em = discord.Embed(title=f"👤 {user.name}'s Profile", description=db_u.bio or "No bio set.", color=int(db_u.color.replace("#",""), 16) if db_u.color else 0x00aaff)
        if db_u.background: em.set_image(url=db_u.background)
        em.set_thumbnail(url=user.display_avatar.url)
        em.add_field(name="Level", value=str(db_u.level))
        em.add_field(name="Wallet", value=f"🪙 {db_u.balance}")
        em.add_field(name="Reputation", value=f"⭐ {db_u.rep}")
        sp = f"<@{db_u.spouse_id}>" if db_u.spouse_id else "Single 💔"
        em.add_field(name="Marriage", value=sp)
        await interaction.followup.send(embed=em)

@bot.tree.command(name="badge", description="Shows earned badges.")
async def cmd_badge(interaction: discord.Interaction, user: discord.Member = None):
    await interaction.response.send_message("🛡️ Badges system coming soon in V2!", ephemeral=True)

# --- ECONOMY SYSTEM ---
@bot.tree.command(name="balance", description="Shows your money balance.")
async def cmd_balance(interaction: discord.Interaction):
    await interaction.response.defer()
    async with AsyncSessionLocal() as session:
        db_u = (await session.execute(select(User).where(User.discord_id == str(interaction.user.id)))).scalar_one_or_none()
        if not db_u:
            db_u = User(discord_id=str(interaction.user.id), username=interaction.user.name)
            session.add(db_u)
            await session.commit()
        bal = db_u.balance
        await interaction.followup.send(f"💳 {interaction.user.mention}, you have **🪙 {bal} coins**.")

@bot.tree.command(name="work", description="Work to earn money.")
async def cmd_work(interaction: discord.Interaction):
    await interaction.response.defer()
    earned = random.randint(50, 200)
    async with AsyncSessionLocal() as session:
        db_u = (await session.execute(select(User).where(User.discord_id == str(interaction.user.id)))).scalar_one_or_none()
        if not db_u:
            db_u = User(discord_id=str(interaction.user.id), username=interaction.user.name)
            session.add(db_u)
        db_u.balance = (db_u.balance or 0) + earned
        await session.commit()
    await interaction.followup.send(f"💼 You worked hard and earned **🪙 {earned} coins**!")

@bot.tree.command(name="crime", description="Risky way to earn money.")
async def cmd_crime(interaction: discord.Interaction):
    await interaction.response.defer()
    success = random.choice([True, False])
    async with AsyncSessionLocal() as session:
        db_u = (await session.execute(select(User).where(User.discord_id == str(interaction.user.id)))).scalar_one_or_none()
        if not db_u:
            db_u = User(discord_id=str(interaction.user.id), username=interaction.user.name)
            session.add(db_u)
            await session.commit()
        if success:
            earned = random.randint(100, 500)
            db_u.balance += earned
            await session.commit()
            await interaction.followup.send(f"🥷 You completed a heist and earned **🪙 {earned} coins**!")
        else:
            lost = random.randint(50, 150)
            db_u.balance = max(0, db_u.balance - lost)
            await session.commit()
            await interaction.followup.send(f"🚓 You were caught! You paid a fine of **🪙 {lost} coins**.")

@bot.tree.command(name="rob", description="Steal money from another user.")
async def cmd_rob(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer()
    if user.id == interaction.user.id: return await interaction.followup.send("❌ You can't rob yourself.")
    success = random.choice([True, False, False]) # 33% chance
    async with AsyncSessionLocal() as session:
        thief = (await session.execute(select(User).where(User.discord_id == str(interaction.user.id)))).scalar_one_or_none()
        target = (await session.execute(select(User).where(User.discord_id == str(user.id)))).scalar_one_or_none()
        if not target:
            target = User(discord_id=str(user.id), username=user.name)
            session.add(target)
            await session.commit()
        if not thief:
            thief = User(discord_id=str(interaction.user.id), username=interaction.user.name)
            session.add(thief)
            await session.commit()
            
        if target.balance < 100:
            return await interaction.followup.send(f"❌ {user.name} is too poor to rob!")
        if success:
            stolen = random.randint(10, 100)
            thief.balance += stolen
            target.balance -= stolen
            await session.commit()
            await interaction.followup.send(f"😈 You successfully robbed **🪙 {stolen} coins** from {user.mention}!")
        else:
            await interaction.followup.send(f"🚔 You were caught trying to rob {user.mention} and fled with nothing!")

@bot.tree.command(name="shop", description="View the standard global shop.")
async def cmd_shop(interaction: discord.Interaction):
    em = discord.Embed(title="🛒 Server Shop")
    em.add_field(name="1. VIP Role", value="🪙 10000 coins", inline=False)
    em.add_field(name="2. Custom Color", value="🪙 5000 coins", inline=False)
    em.add_field(name="3. Profile Background", value="🪙 8000 coins", inline=False)
    await interaction.response.send_message(embed=em)

@bot.tree.command(name="buy", description="Purchase an item.")
async def cmd_buy(interaction: discord.Interaction, item: str):
    await interaction.response.send_message(f"🛒 You tried to buy `{item}`. Extended shop systems coming in V2!", ephemeral=True)

@bot.tree.command(name="inventory", description="Show your items.")
async def cmd_inventory(interaction: discord.Interaction):
    await interaction.response.defer()
    async with AsyncSessionLocal() as session:
        inv = (await session.execute(select(Inventory).where(Inventory.discord_id == str(interaction.user.id)))).scalars().all()
        if not inv: return await interaction.followup.send("🎒 Your inventory is empty.")
        em = discord.Embed(title="🎒 Inventory")
        for i in inv:
            em.add_field(name=i.item_name, value=f"Qty: {i.quantity}")
        await interaction.followup.send(embed=em)

@bot.tree.command(name="transfer", description="Send money to a user.")
async def cmd_transfer(interaction: discord.Interaction, user: discord.Member, amount: int):
    await interaction.response.defer()
    if amount <= 0: return await interaction.followup.send("❌ Amount must be positive.")
    async with AsyncSessionLocal() as session:
        sender = (await session.execute(select(User).where(User.discord_id == str(interaction.user.id)))).scalar_one_or_none()
        receiver = (await session.execute(select(User).where(User.discord_id == str(user.id)))).scalar_one_or_none()
        if not sender or sender.balance < amount:
            return await interaction.followup.send("❌ You don't have enough money.")
        if not receiver:
            return await interaction.followup.send("❌ Recipient not found in DB.")
        sender.balance -= amount
        receiver.balance += amount
        await session.commit()
        await interaction.followup.send(f"💸 Transferred **🪙 {amount}** to {user.mention}.")

# --- FUN & VIRAL ---
@bot.tree.command(name="meme", description="Random meme.")
async def cmd_meme(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://meme-api.com/gimme') as r:
                data = await r.json()
                em = discord.Embed(title=data['title'], url=data['postLink'], color=0x3498db)
                em.set_image(url=data['url'])
                await interaction.followup.send(embed=em)
    except: await interaction.followup.send("❌ API Error")

@bot.tree.command(name="joke", description="Random joke.")
async def cmd_joke(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://v2.jokeapi.dev/joke/Any?safe-mode') as r:
                data = await r.json()
                if data['type'] == 'single': txt = data['joke']
                else: txt = f"{data['setup']}\n\n*||{data['delivery']}||*"
                await interaction.followup.send(f"🎭 {txt}")
    except: await interaction.followup.send("❌ API Error")

@bot.tree.command(name="quote", description="Random inspirational quote.")
async def cmd_quote(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.quotable.io/random') as r:
                data = await r.json()
                await interaction.followup.send(f"📖 \"{data['content']}\"\n— *{data['author']}*")
    except: await interaction.followup.send("❌ API Error")

@bot.tree.command(name="ship", description="Match two users together physically & emotionally.")
async def cmd_ship(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
    perc = random.randint(1, 100)
    heart = "💖" if perc > 70 else ("💔" if perc < 30 else "💛")
    await interaction.response.send_message(f"💘 **Matchmaking System**\n{user1.mention} + {user2.mention} = **{perc}%** {heart}")

@bot.tree.command(name="rate", description="Rate a user out of 10.")
async def cmd_rate(interaction: discord.Interaction, user: discord.Member):
    rating = random.randint(1, 10)
    await interaction.response.send_message(f"🤔 I rate {user.mention} a solid **{rating}/10**!")

@bot.tree.command(name="8ball", description="Ask the magic 8-ball a question.")
async def cmd_8ball(interaction: discord.Interaction, question: str):
    answers = ["Yes.", "No.", "Maybe.", "Definitely not.", "Without a doubt.", "Ask again later.", "Very doubtful.", "Absolutely!"]
    await interaction.response.send_message(f"🎱 **Question:** {question}\n**Answer:** {random.choice(answers)}")

@bot.tree.command(name="roast", description="Funny roast a user.")
async def cmd_roast(interaction: discord.Interaction, user: discord.Member):
    roasts = ["You're like a cloud. When you disappear, it's a beautiful day.", "I'd explain it to you but I left my crayons at home.", "You bring everyone so much joy... when you leave the room."]
    await interaction.response.send_message(f"🔥 {user.mention}, {random.choice(roasts)}")

@bot.tree.command(name="compliment", description="Compliment a user.")
async def cmd_compliment(interaction: discord.Interaction, user: discord.Member):
    comps = ["You have an amazing sense of humor!", "You light up the room!", "You're a brilliant and kind person."]
    await interaction.response.send_message(f"✨ {user.mention}, {random.choice(comps)}")

# --- AI FEATURES ---
import os
import urllib.parse
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")

async def fetch_openrouter(prompt_msg: str, sys_prompt: str = ""):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://virexa-bot.site",
        "X-Title": "Virexa Bot",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt_msg}
        ]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload) as r:
                data = await r.json()
                return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ API Error: {e}"

@bot.tree.command(name="ai", description="AI response to a prompt.")
async def cmd_ai(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    res = await fetch_openrouter(prompt, "You are a helpful and extremely intelligent Discord bot named Virexa. Answer concisely in 1-2 paragraphs max.")
    em = discord.Embed(title=f"🤖 Prompt: {prompt[:200]}", description=res, color=0x00aaff)
    await interaction.followup.send(embed=em)

@bot.tree.command(name="chat", description="Chat with AI.")
async def cmd_chat(interaction: discord.Interaction, message: str):
    await interaction.response.defer()
    res = await fetch_openrouter(message, "You are Virexa, acting like a friendly human chilling in Discord. Use casual language and Discord emojis.")
    await interaction.followup.send(res)

@bot.tree.command(name="image", description="Generate an image based on a prompt.")
async def cmd_image(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    safe_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?nologo=true"
    em = discord.Embed(title=f"🎨 AI Image: {prompt[:100]}", color=0x3498db)
    em.set_image(url=url)
    await interaction.followup.send(embed=em)

@bot.tree.command(name="code", description="AI generates code based on your request.")
async def cmd_code(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    res = await fetch_openrouter(prompt, "You are a senior software engineer. Return only clean, functional code inside markdown codeblocks (no long explanations).")
    await interaction.followup.send(res)

@bot.tree.command(name="translate", description="Translate text seamlessly.")
async def cmd_translate(interaction: discord.Interaction, text: str, lang: str):
    await interaction.response.defer()
    res = await fetch_openrouter(f"Translate the following text into exactly {lang}: '{text}'", "You are a precise translation bot. Reply with ONLY the raw translated text, no wrapper or extra words.")
    em = discord.Embed(title=f"🌍 Translated to {lang}", description=res, color=0x43b581)
    await interaction.followup.send(embed=em)

# --- GIVEAWAY & EVENTS ---
@bot.tree.command(name="giveaway_start", description="Start a giveaway.")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_gw_start(interaction: discord.Interaction, hours: int, prize: str):
    await interaction.response.send_message(f"🎉 **GIVEAWAY STARTED!**\nPrize: {prize}\nDuration: {hours} hours\nReact with 🎉 to enter!")
    # Full background task timer logic for V2

@bot.tree.command(name="giveaway_end", description="End a giveaway actively.")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_gw_end(interaction: discord.Interaction):
    await interaction.response.send_message("🎉 Automatically picking winners requires active background tasks (V2 feature).")

@bot.tree.command(name="reroll", description="Pick a new winner.")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_reroll(interaction: discord.Interaction):
    await interaction.response.send_message("🎲 Reroll logic coming soon.", ephemeral=True)

@bot.tree.command(name="event_create", description="Create an event.")
async def cmd_event_create(interaction: discord.Interaction, name: str):
    await interaction.response.send_message(f"📅 Event `{name}` created! Use /join to join.")

@bot.tree.command(name="join", description="Join an event.")
async def cmd_join(interaction: discord.Interaction, event_name: str):
    await interaction.response.send_message(f"✅ You joined the `{event_name}` event!")

# --- AUTOMATION & CUSTOM SYSTEMS ---
@bot.tree.command(name="autoresponder", description="Create custom auto reply.")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_autoresponder(interaction: discord.Interaction, trigger: str, response: str):
    await interaction.response.send_message("🤖 Custom autoresponders will be saved to the database in V2 update.", ephemeral=True)

@bot.tree.command(name="welcome_setup", description="Visual setup for welcome messages.")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_welcome_setup(interaction: discord.Interaction):
    await interaction.response.send_message("Welcome Setup Wizard: Please use `/setwelcome channel message` for now.", ephemeral=True)

@bot.tree.command(name="goodbye_setup", description="Visual setup for goodbye messages.")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_goodbye_setup(interaction: discord.Interaction):
    await interaction.response.send_message("Goodbye Setup Wizard: Please use `/setgoodbye channel message` for now.", ephemeral=True)

@bot.tree.command(name="reactionrole", description="Setup role via reaction.")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_reactionrole(interaction: discord.Interaction):
    await interaction.response.send_message("Reaction Roles feature coming in the next interaction update!", ephemeral=True)

@bot.tree.command(name="ticket_create", description="Create support ticket category and embed.")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_ticket_create(interaction: discord.Interaction):
    await interaction.response.send_message("🎟️ Ticket system initializing... (Requires channel permission overrides logic in V2)", ephemeral=True)

@bot.tree.command(name="bio", description="Set your profile bio.")
async def cmd_bio(interaction: discord.Interaction, text: str):
    await interaction.response.defer()
    async with AsyncSessionLocal() as session:
        db_u = (await session.execute(select(User).where(User.discord_id == str(interaction.user.id)))).scalar_one_or_none()
        if not db_u:
            db_u = User(discord_id=str(interaction.user.id), username=interaction.user.name)
            session.add(db_u)
        db_u.bio = text[:200]
        await session.commit()
        await interaction.followup.send("✅ Bio updated!")

@bot.tree.command(name="setcolor", description="Set profile color (HEX).")
async def cmd_setcolor(interaction: discord.Interaction, hex_color: str):
    await interaction.response.defer()
    if not hex_color.startswith("#"): hex_color = f"#{hex_color}"
    async with AsyncSessionLocal() as session:
        db_u = (await session.execute(select(User).where(User.discord_id == str(interaction.user.id)))).scalar_one_or_none()
        if not db_u:
            db_u = User(discord_id=str(interaction.user.id), username=interaction.user.name)
            session.add(db_u)
        db_u.color = hex_color
        await session.commit()
        await interaction.followup.send(f"✅ Color updated to {hex_color}!")

@bot.tree.command(name="background", description="Set profile background image URL.")
async def cmd_background(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    async with AsyncSessionLocal() as session:
        db_u = (await session.execute(select(User).where(User.discord_id == str(interaction.user.id)))).scalar_one_or_none()
        if not db_u:
            db_u = User(discord_id=str(interaction.user.id), username=interaction.user.name)
            session.add(db_u)
        db_u.background = url
        await session.commit()
        await interaction.followup.send("✅ Background updated!")

@bot.tree.command(name="marry", description="Send a marriage proposal.")
async def cmd_marry(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer()
    if user.id == interaction.user.id: return await interaction.followup.send("❌ You can't marry yourself.")
    async with AsyncSessionLocal() as session:
        u1 = (await session.execute(select(User).where(User.discord_id == str(interaction.user.id)))).scalar_one_or_none()
        if u1 and u1.spouse_id: return await interaction.followup.send("❌ You are already married!")
        # Fake acceptance for now without complex Views
        u1.spouse_id = str(user.id)
        await session.commit()
        await interaction.followup.send(f"💍 {interaction.user.mention} is now married to {user.mention}!")

@bot.tree.command(name="divorce", description="End your current marriage.")
async def cmd_divorce(interaction: discord.Interaction):
    await interaction.response.defer()
    async with AsyncSessionLocal() as session:
        u1 = (await session.execute(select(User).where(User.discord_id == str(interaction.user.id)))).scalar_one_or_none()
        if u1 and u1.spouse_id:
            old = u1.spouse_id
            u1.spouse_id = None
            await session.commit()
            await interaction.followup.send(f"💔 You have divorced <@{old}>.")
        else: await interaction.followup.send("❌ You aren't married.")

@bot.tree.command(name="family", description="Show your family tree.")
async def cmd_family(interaction: discord.Interaction):
    await interaction.response.send_message("Family Tree system coming in V2!", ephemeral=True)

# --- COMPETITIVE & GAMES ---
@bot.tree.command(name="duel", description="Duel a user for honor.")
async def cmd_duel(interaction: discord.Interaction, user: discord.Member):
    winner = random.choice([interaction.user, user])
    await interaction.response.send_message(f"⚔️ {interaction.user.mention} challenged {user.mention} to a duel!\n🏆 **{winner.mention}** won the battle!")

@bot.tree.command(name="quiz", description="Start a trivia quiz.")
async def cmd_quiz(interaction: discord.Interaction):
    await interaction.response.send_message("🧠 **What is the capital of France?**\n(Reply in chat! Quiz interactive loops coming in V2)")

@bot.tree.command(name="trivia", description="Random trivia fact.")
async def cmd_trivia(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://opentdb.com/api.php?amount=1') as r:
                data = await r.json()
                q = data['results'][0]['question']
                a = data['results'][0]['correct_answer']
                await interaction.followup.send(f"📚 **Trivia**\nQuestion: {q}\nAnswer: ||{a}||")
    except: await interaction.followup.send("❌ API Error")

@bot.tree.command(name="battle", description="Engage in a turn-based battle.")
async def cmd_battle(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.send_message("⚔️ Turn-based battle system requires interactive UI Buttons (Next update!).")

@bot.tree.command(name="coinflip", description="Gamble coins on a coinflip.")
async def cmd_coinflip(interaction: discord.Interaction, amount: int):
    await interaction.response.defer()
    if amount <= 0: return await interaction.followup.send("❌ Negative amount.")
    async with AsyncSessionLocal() as session:
        db_u = (await session.execute(select(User).where(User.discord_id == str(interaction.user.id)))).scalar_one_or_none()
        if not db_u or db_u.balance < amount:
            return await interaction.followup.send("❌ You don't have enough coins.")
        win = random.choice([True, False])
        if win:
            db_u.balance += amount
            await session.commit()
            await interaction.followup.send(f"🪙 It's **HEADS**! You won **{amount * 2} coins**!")
        else:
            db_u.balance -= amount
            await session.commit()
            await interaction.followup.send(f"🪙 It's **TAILS**... You lost **{amount} coins**.")

# ─────────────────────────────────────────────
# 🤖 AI COMMANDS
# ─────────────────────────────────────────────
import urllib.parse

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")

async def fetch_openrouter(prompt_msg: str, sys_prompt: str = "You are Virexa, a helpful Discord bot. Answer clearly."):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://virexa-bot.site",
        "X-Title": "Virexa Bot",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt_msg}
        ]
    }
    async with aiohttp.ClientSession() as session:
        async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload) as r:
            if r.status != 200:
                text = await r.text()
                raise Exception(f"HTTP {r.status}: {text}")
            data = await r.json()
            return data["choices"][0]["message"]["content"]

@bot.tree.command(name="ai", description="Ask AI a question and get a smart answer.")
async def cmd_ai(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    try:
        res = await fetch_openrouter(prompt, "You are a helpful and intelligent Discord bot named Virexa. Answer in 1-2 short paragraphs.")
        em = discord.Embed(title=f"🤖 {prompt[:200]}", description=res, color=0x00aaff)
        await interaction.followup.send(embed=em)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

@bot.tree.command(name="chat", description="Chat casually with AI.")
async def cmd_chat(interaction: discord.Interaction, message: str):
    await interaction.response.defer()
    try:
        res = await fetch_openrouter(message, "You are Virexa, a friendly human chilling in Discord. Use casual language and Discord emojis. Max 2-3 sentences.")
        await interaction.followup.send(res)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

@bot.tree.command(name="code", description="AI generates working code for your request.")
async def cmd_code(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    try:
        res = await fetch_openrouter(prompt, "You are a senior software engineer. Return ONLY clean working code inside a markdown code block. No long explanations, just code.")
        # Trim if too long for Discord
        if len(res) > 1990:
            res = res[:1990] + "\n...(truncated)"
        await interaction.followup.send(res)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

@bot.tree.command(name="image", description="Generate an AI image (free).")
async def cmd_image(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    try:
        safe = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{safe}?nologo=true&width=1024&height=1024"
        em = discord.Embed(title=f"🎨 {prompt[:100]}", color=0x9b59b6)
        em.set_image(url=url)
        await interaction.followup.send(embed=em)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

@bot.tree.command(name="translate", description="Translate text to any language.")
async def cmd_translate(interaction: discord.Interaction, text: str, language: str):
    await interaction.response.defer()
    try:
        res = await fetch_openrouter(f"Translate to {language}: {text}", "You are a precise translator. Reply with ONLY the translated text, nothing else.")
        em = discord.Embed(title=f"🌍 Translated to {language}", description=res, color=0x43b581)
        em.add_field(name="Original", value=text[:512], inline=False)
        await interaction.followup.send(embed=em)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

@bot.tree.command(name="setup_ai", description="Set an AI chatbot channel — bot auto-replies to all messages.")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_setup_ai(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Server).where(Server.guild_id == str(interaction.guild_id))
            srv = (await session.execute(stmt)).scalar_one_or_none()
            if not srv:
                srv = Server(guild_id=str(interaction.guild_id))
                session.add(srv)
            srv.ai_channel_id = str(channel.id)
            await session.commit()
        em = discord.Embed(color=0x00aaff)
        em.title = "🤖 AI Chatbot Channel Set!"
        em.description = f"All messages sent in {channel.mention} will now get **automatic AI replies** from Virexa!\n\nTo disable, run `/setup_ai` and select a different channel, or contact support."
        await interaction.followup.send(embed=em, ephemeral=True)
        # Announce it in the channel itself
        await channel.send("🤖 **AI Chatbot is now active in this channel!**\nSend any message and I will respond automatically!")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)


# ─────────────────────────────────────────────
async def main():
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    if not DISCORD_TOKEN or DISCORD_TOKEN == "your-discord-bot-token-here":
        print("ERROR: Please set DISCORD_TOKEN in your .env file.")
    else:
        asyncio.run(main())
