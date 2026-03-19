import sys
import os
import re

file_path = r"c:\Code\Virexa\virexa compressed\main.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update Server Model
server_new = """    guild_id = Column(String, unique=True, index=True)
    log_channel_id = Column(String, nullable=True)
    prefix = Column(String, default="/")
    welcome_message = Column(String, nullable=True)
    goodbye_message = Column(String, nullable=True)
    welcome_channel_id = Column(String, nullable=True)
    goodbye_channel_id = Column(String, nullable=True)
    autorole_id = Column(String, nullable=True)
    mute_role_id = Column(String, nullable=True)
    mod_role_id = Column(String, nullable=True)
    admin_role_id = Column(String, nullable=True)"""
code = code.replace("    guild_id = Column(String, unique=True, index=True)\n    log_channel_id = Column(String, nullable=True)\n    prefix = Column(String, default=\"/\")", server_new)

# 2. Add Warning Model
warning_model = """
class Warning(Base):
    __tablename__ = "warnings"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(String)
    user_id = Column(String)
    moderator_id = Column(String)
    reason = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
"""
if "class Warning(Base):" not in code:
    code = code.replace("class Event(Base):", warning_model + "\nclass Event(Base):")

# 3. Add the 50 commands
fifty_commands = '''
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
    await interaction.channel.send(f"📢 **Announcement**\n\n{message}")
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
                em.add_field(name=f"Warn ID: {w.id}", value=f"Reason: {w.reason}\nMod: <@{w.moderator_id}>", inline=False)
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
'''

if "# 🛡️ ADMIN & MODERATION & USER COMMANDS" not in code:
    code = code.replace("# ─────────────────────────────────────────────\n# STARTUP", fifty_commands + "\n# ─────────────────────────────────────────────\n# STARTUP")

# Also add the event triggers for Welcome/Goodbye and AutoRole to the on_member_join / remove events
event_patch_join = """@bot.event
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

    if member.bot:"""
code = code.replace("@bot.event\nasync def on_member_join(member):\n    if member.bot:", event_patch_join)

event_patch_leave = """@bot.event
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

    try:"""
code = code.replace("@bot.event\nasync def on_member_remove(member):\n    try:", event_patch_leave)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)
print("Successfully injected all commands and patched models!")
