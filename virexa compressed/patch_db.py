import sys

with open('main.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace missing DB checks with auto-registration!
text = text.replace('''        if not db_user:
            await interaction.followup.send(f"❌ {user.name} is not registered in the database.")
            return''', '''        if not db_user:
            db_user = User(discord_id=str(user.id), username=user.name)
            session.add(db_user)
            await session.commit()''')

text = text.replace('''        if not db_u:
            return await interaction.followup.send(f"❌ {user.name} is not in the database.")''', '''        if not db_u:
            db_u = User(discord_id=str(user.id), username=user.name)
            session.add(db_u)
            await session.commit()''')

text = text.replace('''        if db_u:
            db_u.bio = text[:200]
            await session.commit()
            await interaction.followup.send("✅ Bio updated!")
        else: await interaction.followup.send("❌ Not found in database.")''', '''        if not db_u:
            db_u = User(discord_id=str(interaction.user.id), username=interaction.user.name)
            session.add(db_u)
        db_u.bio = text[:200]
        await session.commit()
        await interaction.followup.send("✅ Bio updated!")''')

text = text.replace('''        if db_u:
            db_u.color = hex_color
            await session.commit()
            await interaction.followup.send(f"✅ Color updated to {hex_color}!")''', '''        if not db_u:
            db_u = User(discord_id=str(interaction.user.id), username=interaction.user.name)
            session.add(db_u)
        db_u.color = hex_color
        await session.commit()
        await interaction.followup.send(f"✅ Color updated to {hex_color}!")''')

text = text.replace('''        if db_u:
            db_u.background = url
            await session.commit()
            await interaction.followup.send("✅ Background updated!")''', '''        if not db_u:
            db_u = User(discord_id=str(interaction.user.id), username=interaction.user.name)
            session.add(db_u)
        db_u.background = url
        await session.commit()
        await interaction.followup.send("✅ Background updated!")''')

text = text.replace('''        db_u = (await session.execute(select(User).where(User.discord_id == str(interaction.user.id)))).scalar_one_or_none()
        bal = db_u.balance if db_u else 0''', '''        db_u = (await session.execute(select(User).where(User.discord_id == str(interaction.user.id)))).scalar_one_or_none()
        if not db_u:
            db_u = User(discord_id=str(interaction.user.id), username=interaction.user.name)
            session.add(db_u)
            await session.commit()
        bal = db_u.balance''')

text = text.replace('''        if db_u:
            db_u.balance = (db_u.balance or 0) + earned
            await session.commit()''', '''        if not db_u:
            db_u = User(discord_id=str(interaction.user.id), username=interaction.user.name)
            session.add(db_u)
        db_u.balance = (db_u.balance or 0) + earned
        await session.commit()''')

text = text.replace('''        if not db_u: return await interaction.followup.send("❌ Not in DB.")''', '''        if not db_u:
            db_u = User(discord_id=str(interaction.user.id), username=interaction.user.name)
            session.add(db_u)
            await session.commit()''')

text = text.replace('''        if not target or target.balance < 100:''', '''        if not target:
            target = User(discord_id=str(user.id), username=user.name)
            session.add(target)
            await session.commit()
        if not thief:
            thief = User(discord_id=str(interaction.user.id), username=interaction.user.name)
            session.add(thief)
            await session.commit()
            
        if target.balance < 100:''')

text = text.replace('''        else:
            await interaction.followup.send("❌ That user is not in the database.")''', '''        else:
            r_user = User(discord_id=str(user.id), username=user.name)
            r_user.rep = 1
            session.add(r_user)
            await session.commit()
            await interaction.followup.send(f"✅ You gave +1 Rep to {user.mention}!")''')

# on_message auto-register
text = text.replace('''        if db_u:
            db_u.xp = (db_u.xp or 0) + random.randint(5, 15)''', '''        if not db_u:
            db_u = User(discord_id=str(message.author.id), username=message.author.name)
            session.add(db_u)
        db_u.xp = (db_u.xp or 0) + random.randint(5, 15)''')

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Patched DB auto-registration!")
