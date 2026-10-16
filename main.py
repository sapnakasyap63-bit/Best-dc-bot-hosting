import asyncio
import threading
from flask import Flask
import discord
from discord.ext import commands
from config import config
from database import init_db

config.validate()

app = Flask(__name__)

@app.route("/")
def health_check():
    return {
        "status": "online",
        "bot": "VorstyAFK Operational",
        "guild_id": config.ALLOWED_GUILD_ID
    }, 200

def run_flask():
    app.run(host="0.0.0.0", port=config.PORT)

intents = discord.Intents.default()
intents.members = True
intents.invites = True
intents.message_content = True

bot = commands.Bot(command_prefix=["$", "!"], intents=intents, help_command=None)

@bot.event
async def on_ready():
    await init_db()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    
    guild = discord.Object(id=config.ALLOWED_GUILD_ID)
    try:
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print("Slash commands synced successfully to allowed guild.")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

@bot.event
async def on_guild_join(guild):
    if guild.id != config.ALLOWED_GUILD_ID:
        print(f"Unauthorized guild {guild.name} ({guild.id}). Leaving immediately...")
        await guild.leave()

async def load_cogs():
    await bot.load_extension("cogs.general")
    await bot.load_extension("cogs.invites")
    await bot.load_extension("cogs.plans")
    await bot.load_extension("cogs.admin")

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    async with bot:
        await load_cogs()
        await bot.start(config.DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
