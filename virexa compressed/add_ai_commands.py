import sys

with open(r'c:\Code\Virexa\virexa compressed\main.py', 'r', encoding='utf-8') as f:
    text = f.read()

ai_placeholders = '''# --- AI FEATURES ---
@bot.tree.command(name="ai", description="AI response to a prompt.")
async def cmd_ai(interaction: discord.Interaction, prompt: str):
    await interaction.response.send_message("🤖 AI Text Generation requires an OpenAI API key in `.env`. Setup coming in V2!", ephemeral=True)

@bot.tree.command(name="chat", description="Chat with AI.")
async def cmd_chat(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("🗣️ AI Chatting requires an OpenAI API key in `.env`. Setup coming in V2!", ephemeral=True)

@bot.tree.command(name="image", description="Generate image.")
async def cmd_image(interaction: discord.Interaction, prompt: str):
    await interaction.response.send_message("🎨 AI Image Generation requires an API key in `.env`. Setup coming in V2!", ephemeral=True)

@bot.tree.command(name="code", description="AI generates code based on prompt.")
async def cmd_code(interaction: discord.Interaction, prompt: str):
    await interaction.response.send_message("💻 AI Code Generation requires an API key in `.env`. Setup coming in V2!", ephemeral=True)

@bot.tree.command(name="translate", description="Translate text.")
async def cmd_translate(interaction: discord.Interaction, text: str, lang: str):
    await interaction.response.send_message("🌍 Translation feature requires an API key in `.env`. Setup coming in V2!", ephemeral=True)'''

ai_functional = '''# --- AI FEATURES ---
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
    await interaction.followup.send(embed=em)'''

text = text.replace(ai_placeholders, ai_functional)

with open(r'c:\Code\Virexa\virexa compressed\main.py', 'w', encoding='utf-8') as f:
    f.write(text)

with open(r'c:\Code\Virexa\virexa compressed\.env', 'a', encoding='utf-8') as f:
    f.write('\nOPENROUTER_API_KEY="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"\n')

print("Successfully swapped AI commands to functional versions!")
