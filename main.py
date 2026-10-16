import os
import asyncio
import threading
from datetime import datetime, timedelta
from flask import Flask
import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
import aiosqlite

load_dotenv()

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ALLOWED_GUILD_ID = int(os.getenv("ALLOWED_GUILD_ID", 0) or 0)
PORT = int(os.getenv("PORT", 10000))
DATABASE_PATH = os.getenv("DATABASE_PATH", "vorstyafk.db").replace("sqlite:///", "")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID", 0) or 0)
MAX_SLOTS = int(os.getenv("MAX_SLOTS", 50))

if not DISCORD_TOKEN or not ALLOWED_GUILD_ID:
    print("❌ CRITICAL ERROR: DISCORD_TOKEN or ALLOWED_GUILD_ID is missing in Environment Variables!")
    exit(1)

# --- FLASK HEALTH CHECK FOR RENDER ---
app = Flask(__name__)

@app.route("/")
def health_check():
    return {"status": "online", "bot": "VorstyAFK Operational", "guild_id": ALLOWED_GUILD_ID}, 200

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# --- DATABASE SETUP ---
async def init_db():
    asyncign = aiosqlite.connect(DATABASE_PATH)
    async with asyncign as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS members (
                user_id INTEGER PRIMARY KEY,
                earned_credits INTEGER DEFAULT 0,
                spent_credits INTEGER DEFAULT 0,
                fake_invites INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_plans (
                user_id INTEGER PRIMARY KEY,
                plan_name TEXT,
                status TEXT DEFAULT 'Offline',
                ip_address TEXT,
                port INTEGER,
                assigned_bot TEXT,
                expires_at TEXT
            )
        """)
        await db.commit()

# --- DISCORD BOT SETUP ---
intents = discord.Intents.default()
intents.members = True
intents.invites = True
intents.message_content = True

bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

# --- PLANS & AFK BOTS POOL DATA ---
PLANS_DATA = {
    2: {"days": 3, name: "3 Days Plan"},
    4: {"days": 7, name: "7 Days Plan"},
    6: {"days": 15, name: "15 Days Plan"},
    8: {"days": 22, name: "22 Days Plan"},
    12: {"days": 30, name: "30 Days Plan"},
    16: {"days": 60, name: "60 Days Plan"},
    24: {"days": 90, name: "90 Days Plan"},
    60: {"days": 9999, name: "Lifetime Plan"}
}

# 50 AFK Bots mapped with their GitHub Repository names
AFK_BOTS_POOL = [
    f"Vorsty-AFK-Bot-Repo-{i}" for i in range(1, 51)
]

@bot.event
async def on_ready():
    await init_db()
    print(f"✅ Logged in successfully as {bot.user} (ID: {bot.user.id})[span_7](start_span)[span_7](end_span)")
    
    guild = discord.Object(id=ALLOWED_GUILD_ID)
    try:
        bot.tree.clear_commands(guild=guild)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print("✅ Slash commands synced successfully to allowed guild[span_8](start_span)[span_8](end_span).")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")
    
    if not check_expirations.is_running():
        check_expirations.start()

@bot.event
async def on_guild_join(guild):
    if guild.id != ALLOWED_GUILD_ID:
        print(f"⚠️ Unauthorized guild {guild.name} ({guild.id}). Leaving immediately...[span_9](start_span)[span_9](end_span)")
        await guild.leave()

# --- BACKGROUND EXPIRY TASK ---
@tasks.loop(minutes=1)
async def check_expirations():
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT user_id, plan_name, assigned_bot, ip_address, port FROM user_plans WHERE expires_at <= ?", 
            (now_str,)
        ) as cursor:
            expired_plans = await cursor.fetchall()

        for user_id, plan_name, assigned_bot, ip, port in expired_plans:
            # Delete expired plan so slot is freed and user can claim again
            await db.execute("DELETE FROM user_plans WHERE user_id = ?", (user_id,))
            await db.commit()

            user = bot.get_user(user_id)
            if user:
                try:
                    embed = discord.Embed(
                        title="⚠️ Hosting Plan Expired",
                        description=f"Your **{plan_name}** for server `{ip}:{port}` has expired. Your assigned bot `{assigned_bot}` is now released.",
                        color=discord.Color.red()
                    )
                    await user.send(embed=embed)
                except Exception:
                    pass

            if ALERT_CHANNEL_ID:
                channel = bot.get_channel(ALERT_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(
                        title="🔴 Plan Expiration & Bot Release",
                        description=f"User <@{user_id}>'s plan expired.\nReleased Bot: `{assigned_bot}`\nSlot freed up!",
                        color=discord.Color.dark_red()
                    )
                    await channel.send(embed=embed)

# --- COMMANDS ---

@bot.command(name="help")
async def prefix_help(ctx):
    embed = discord.Embed(title="🛡️ VorstyAFK Help Center", color=discord.Color.blurple())
    embed.description = "Available Prefix Commands (`$`):"
    embed.add_field(name="💎 Claim Plan", value="`$claim <invites> <ip> <port>`\n*(Example: `$claim 4 Hypixel.net 25565`)*", inline=False)
    embed.add_field(name="📊 Check Invites", value="`$i` (or `$i @member`)", inline=False)
    embed.add_field(name="👑 Admin Commands", value="`$set @member <invites>`", inline=False)
    embed.set_footer(text="VorstyAFK System • Secure 24/7 Hosting[span_10](start_span)[span_10](end_span)")
    await ctx.send(embed=embed)

@bot.tree.command(name="help", description="Show help menu for VorstyAFK")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(title="🛡️ VorstyAFK Slash Help Menu", color=discord.Color.blurple())
    embed.add_field(name="Commands Info", value="Use prefix `$` for all hosting and claim commands in chat.", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command(name="i")
async def prefix_invites(ctx, member: discord.Member = None):
    target = member or ctx.author
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT earned_credits, spent_credits, fake_invites FROM members WHERE user_id = ?", (target.id,)) as cursor:
            row = await cursor.fetchone()
            earned = row[0] if row else 0
            spent = row[1] if row else 0
            fake = row[2] if row else 0
            current = earned - spent

        async with db.execute("SELECT plan_name, expires_at FROM user_plans WHERE user_id = ?", (target.id,)) as cursor:
            plan_row = await cursor.fetchone()

    if plan_row:
        plan_name, expires_at = plan_row
        # Calculate remaining days
        exp_dt = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
        remaining_days = max(1, (exp_dt - datetime.utcnow()).days)
        expire_display = f"{expires_at} UTC"
        days_display = f"{remaining_days} Days"
    else:
        expire_display = "No Active Plan"
        days_display = "0 Days"

    embed = discord.Embed(title=f"📊 Invite & Plan Status: {target.name}", color=discord.Color.green())
    embed.add_field(name="✅ Current Invites", value=str(current), inline=True)
    embed.add_field(name="💸 Used Invites", value=str(spent), inline=True)
    embed.add_field(name="🚫 Fake Invites", value=str(fake), inline=True)
    embed.add_field(name="⏳ Plan Expire Time", value=expire_display, inline=False)
    embed.add_field(name="📅 Remaining Days", value=days_display, inline=False)
    await ctx.send(embed=embed)

@bot.command(name="claim")
async def prefix_claim(ctx, invites: int, ip: str, port: int):
    # Check if invites count matches a valid plan tier
    if invites not in PLANS_DATA:
        valid_tiers = ", ".join([str(k) for k in PLANS_DATA.keys()])
        await ctx.send(f"❌ Invalid invite requirement! Valid invite amounts for plans are: `{valid_tiers}`. Check `$help`.")
        return

    plan_info = PLANS_DATA[invites]
    plan_name = plan_info["name"]
    days = plan_info["days"]

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # 1. Check if user already has an active plan
        async with db.execute("SELECT expires_at FROM user_plans WHERE user_id = ?", (ctx.author.id,)) as cursor:
            existing_plan = await cursor.fetchone()
        if existing_plan:
            await ctx.send(f"❌ You already have an active plan running until `{existing_plan[0]} UTC`. You cannot claim another until it expires.")
            return

        # 2. Check total active slots (Max 50)
        async with db.execute("SELECT COUNT(*) FROM user_plans") as cursor:
            slot_row = await cursor.fetchone()
            active_slots = slot_row[0] if slot_row else 0

        if active_slots >= MAX_SLOTS:
            await ctx.send(f"❌ **Slots Full ({active_slots}/{MAX_SLOTS})!** All 50 AFK bot hosting slots are currently occupied.")
            return

        # 3. Check user available invites
        async with db.execute("SELECT earned_credits - spent_credits FROM members WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            available = row[0] if row else 0

        if available < invites:
            await ctx.send(f"❌ Insufficient invites! You need **{invites}** invites for the **{plan_name}**, but you only have **{available}** available.")
            return

        # 4. Find an unassigned bot from the 50 bots pool
        async with db.execute("SELECT assigned_bot FROM user_plans") as cursor:
            assigned_rows = await cursor.fetchall()
        taken_bots = {row[0] for row in assigned_rows}

        available_bots = [b for b in AFK_BOTS_POOL if b not in taken_bots]
        if not available_bots:
            await ctx.send("❌ Error: All server bot instances are currently deployed!")
            return

        assigned_bot = available_bots[0] # Pick the first free bot

        # 5. Calculate expiry
        expires_at = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

        # 6. Update database (Deduct invites, save active plan)
        await db.execute("UPDATE members SET spent_credits = spent_credits + ? WHERE user_id = ?", (invites, ctx.author.id))
        await db.execute("""
            INSERT INTO user_plans (user_id, plan_name, status, ip_address, port, assigned_bot, expires_at)
            VALUES (?, ?, 'Online', ?, ?, ?, ?)
        """, (ctx.author.id, plan_name, ip, port, assigned_bot, expires_at))
        await db.commit()

    # Success reply to user
    await ctx.send(f"✅ **Plan Successfully Claimed!**\n📦 **Plan:** {plan_name}\n🤖 **Assigned Bot:** `{assigned_bot}`\n🌐 **Target IP/Port:** `{ip}:{port}`\n⏳ **Expires At:** `{expires_at} UTC`")

    # Alert Channel Embed Notification
    if ALERT_CHANNEL_ID:
        alert_channel = bot.get_channel(ALERT_CHANNEL_ID)
        if alert_channel:
            embed = discord.Embed(title="🤖 New AFK Bot Deployed & Claimed", color=discord.Color.from_rgb(87, 242, 135))
            embed.add_field(name="Member", value=f"{ctx.author.mention} (`{ctx.author}`)", inline=False)
            embed.add_field(name="Claimed Plan", value=plan_name, inline=True)
            embed.add_field(name="Invites Spent", value=str(invites), inline=True)
            embed.add_field(name="Assigned GitHub Bot", value=f"`{assigned_bot}`", inline=False)
            embed.add_field(name="Server Endpoint", value=f"`{ip}:{port}`", inline=False)
            embed.add_field(name="Expiry Time", value=f"{expires_at} UTC", inline=False)
            await alert_channel.send(embed=embed)

# --- ADMIN COMMANDS ---
@bot.command(name="set")
@commands.has_permissions(administrator=True)
async def prefix_set_invites(ctx, member: discord.Member, amount: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO members (user_id, earned_credits) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET earned_credits = ?
        """, (member.id, amount, amount))
        await db.commit()
    await ctx.send(f"✅ Successfully set earned invites for {member.mention} to **{amount}**[span_11](start_span)[span_11](end_span).")

@prefix_set_invites.error
async def set_invites_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You do not have permission to use admin commands.")
    else:
        await ctx.send("❌ Incorrect format! Use: `$set @member <amount>`")

# --- MAIN RUNNER ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(DISCORD_TOKEN)
