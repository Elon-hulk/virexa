import discord
from discord import app_commands
from sqlalchemy.future import select
from database.connection import AsyncSessionLocal
from database.models import Server, Event

async def setup_commands(bot: discord.ext.commands.Bot):
    
    @bot.tree.command(name="setup", description="Initial configuration wizard for Virexa")
    @app_commands.checks.has_permissions(administrator=True)
    async def cmd_setup(interaction: discord.Interaction):
        await interaction.response.send_message("Setup starting! Please configure using the web dashboard or other slash commands like /setlog, /setprefix.", ephemeral=True)
        # Verify server exists in DB
        async with AsyncSessionLocal() as session:
            stmt = select(Server).where(Server.guild_id == str(interaction.guild_id))
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                new_server = Server(guild_id=str(interaction.guild_id))
                session.add(new_server)
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

    @bot.tree.command(name="setprefix", description="Change command prefix (for standard commands if used)")
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

    @bot.tree.command(name="enableevent", description="Enable logging event")
    @app_commands.checks.has_permissions(administrator=True)
    async def cmd_enableevent(interaction: discord.Interaction, event_name: str):
        valid_events = ["member_join", "member_remove", "bot_add", "member_update_name", 
                        "member_update_nick", "role_add", "role_remove", "role_create", 
                        "role_delete", "channel_create", "channel_delete"]
        if event_name not in valid_events:
            await interaction.response.send_message(f"Invalid event. Valid events: {', '.join(valid_events)}", ephemeral=True)
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

    @bot.tree.command(name="disableevent", description="Disable logging event")
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
                await interaction.response.send_message(f"Event `{event_name}` not found or already disabled.", ephemeral=True)

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

                embed = discord.Embed(title="Virexa Status", color=0x00ff00)
                embed.add_field(name="Ping", value=f"{round(bot.latency * 1000)}ms", inline=False)
                embed.add_field(name="Log Channel", value=log_ch, inline=False)
                embed.add_field(name="Prefix", value=server.prefix, inline=False)
                embed.add_field(name="Enabled Events", value=enabled_evs, inline=False)
                
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("Server not initialized. Run /setup first.", ephemeral=True)
