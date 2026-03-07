import discord
from sqlalchemy.future import select
from database.connection import AsyncSessionLocal
from database.models import Server, Event, Log
import datetime

async def log_event_to_db(guild_id: int, event_type: str, user_id: int, description: str):
    async with AsyncSessionLocal() as session:
        # Check if event is enabled
        stmt = select(Event).where(Event.guild_id == str(guild_id), Event.event_name == event_type)
        result = await session.execute(stmt)
        event = result.scalar_one_or_none()

        if event and event.enabled:
            # Create a log entry
            log_entry = Log(
                guild_id=str(guild_id),
                event_type=event_type,
                user_id=str(user_id),
                description=description,
                timestamp=datetime.datetime.utcnow()
            )
            session.add(log_entry)
            await session.commit()
            
            # Optionally send to log channel
            stmt_server = select(Server).where(Server.guild_id == str(guild_id))
            result_server = await session.execute(stmt_server)
            server = result_server.scalar_one_or_none()
            if server and server.log_channel_id:
                return int(server.log_channel_id)
    return None

async def setup_events(bot: discord.ext.commands.Bot):

    @bot.event
    async def on_guild_join(guild):
        async with AsyncSessionLocal() as session:
            stmt = select(Server).where(Server.guild_id == str(guild.id))
            result = await session.execute(stmt)
            server = result.scalar_one_or_none()
            if not server:
                new_server = Server(guild_id=str(guild.id))
                session.add(new_server)
                # default events
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
        if member.bot:
            channel_id = await log_event_to_db(member.guild.id, "bot_add", member.id, f"Bot joined: {member.name}")
        else:
            channel_id = await log_event_to_db(member.guild.id, "member_join", member.id, f"Member joined: {member.name}")
        
        if channel_id:
            channel = member.guild.get_channel(channel_id)
            if channel:
                await channel.send(f"[{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] **Join**: <@{member.id}> ({member.id}) joined the server.")

    @bot.event
    async def on_member_remove(member):
        channel_id = await log_event_to_db(member.guild.id, "member_remove", member.id, f"Member left: {member.name}")
        if channel_id:
            channel = member.guild.get_channel(channel_id)
            if channel:
                await channel.send(f"[{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] **Leave**: {member.name} ({member.id}) left the server.")

    @bot.event
    async def on_member_update(before, after):
        if before.name != after.name:
            channel_id = await log_event_to_db(after.guild.id, "member_update_name", after.id, f"Name changed from {before.name} to {after.name}")
            if channel_id:
                channel = after.guild.get_channel(channel_id)
                if channel:
                    await channel.send(f"[{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] **Name Change**: {before.name} -> {after.name}")
        
        if before.nick != after.nick:
            channel_id = await log_event_to_db(after.guild.id, "member_update_nick", after.id, f"Nickname changed from {before.nick} to {after.nick}")
            if channel_id:
                channel = after.guild.get_channel(channel_id)
                if channel:
                    await channel.send(f"[{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] **Nickname Change**: <@{after.id}> changed nickname to {after.nick}")
        
        # Check roles
        added_roles = [r for r in after.roles if r not in before.roles]
        removed_roles = [r for r in before.roles if r not in after.roles]

        for role in added_roles:
            channel_id = await log_event_to_db(after.guild.id, "role_add", after.id, f"Role added: {role.name}")
            if channel_id:
                channel = after.guild.get_channel(channel_id)
                if channel:
                    await channel.send(f"[{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] **Role Added**: <@{after.id}> was given the {role.name} role.")

        for role in removed_roles:
            channel_id = await log_event_to_db(after.guild.id, "role_remove", after.id, f"Role removed: {role.name}")
            if channel_id:
                channel = after.guild.get_channel(channel_id)
                if channel:
                    await channel.send(f"[{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] **Role Removed**: <@{after.id}> lost the {role.name} role.")

    @bot.event
    async def on_guild_role_create(role):
        channel_id = await log_event_to_db(role.guild.id, "role_create", role.id, f"Role created: {role.name}")
        if channel_id:
            channel = role.guild.get_channel(channel_id)
            if channel:
                await channel.send(f"[{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] **Role Created**: {role.name}")

    @bot.event
    async def on_guild_role_delete(role):
        channel_id = await log_event_to_db(role.guild.id, "role_delete", role.id, f"Role deleted: {role.name}")
        if channel_id:
            channel = role.guild.get_channel(channel_id)
            if channel:
                await channel.send(f"[{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] **Role Deleted**: {role.name}")

    @bot.event
    async def on_guild_channel_create(channel):
        channel_id = await log_event_to_db(channel.guild.id, "channel_create", channel.id, f"Channel created: {channel.name}")
        if channel_id:
            log_chan = channel.guild.get_channel(channel_id)
            if log_chan:
                await log_chan.send(f"[{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] **Channel Created**: #{channel.name}")

    @bot.event
    async def on_guild_channel_delete(channel):
        channel_id = await log_event_to_db(channel.guild.id, "channel_delete", channel.id, f"Channel deleted: {channel.name}")
        if channel_id:
            log_chan = channel.guild.get_channel(channel_id)
            if log_chan:
                await log_chan.send(f"[{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] **Channel Deleted**: #{channel.name}")
