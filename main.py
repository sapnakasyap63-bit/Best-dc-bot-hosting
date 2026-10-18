import os
import asyncio
import threading
from datetime import datetime, timedelta
from flask import Flask
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import aiosqlite

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ALLOWED_GUILD_ID = int(os.getenv("ALLOWED_GUILD_ID", 0) or 0)
PORT = int(os.getenv("PORT", 10000))
DATABASE_PATH = os.getenv("DATABASE_PATH", "vorstyafk.db").replace("sqlite:///", "")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID", 0) or 0)
MAX_SLOTS = int(os.getenv("MAX_SLOTS", 50))

if not DISCORD_TOKEN or not ALLOWED_GUILD_ID:
    print("❌ CRITICAL ERROR: DISCORD_TOKEN or ALLOWED_GUILD_ID is missing in Environment Variables!")
    exit(1)

app = Flask(__name__)

@app.route("/")
def health_check():
    return {"status": "online", "bot": "VorstyAFK Operational", "guild_id": ALLOWED_GUILD_ID}, 200

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
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
                status TEXT DEFAULT 'Online',
                ip_address TEXT,
                port TEXT,
                assigned_bot TEXT,
                expires_at TEXT
            )
        """)
        await db.commit()

intents = discord.Intents.default()
intents.members = True
intents.invites = True
intents.message_content = True

bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

PLANS_DATA = {
    2: {"days": 3, "name": "3 Days Plan"},
    4: {"days": 7, "name": "7 Days Plan"},
    6: {"days": 15, "name": "15 Days Plan"},
    8: {"days": 22, "name": "22 Days Plan"},
    12: {"days": 30, "name": "30 Days Plan"},
    16: {"days": 60, "name": "60 Days Plan"},
    24: {"days": 90, "name": "90 Days Plan"},
    60: {"days": 9999, "name": "Lifetime Plan"}
}

AFK_BOTS_POOL = [f"Vorsty-AFK-Repo-{i}" for i in range(1, 51)]

@bot.event
async def on_ready():
    await init_db()
    print(f"✅ Central Bot logged in successfully as {bot.user}")
    if not check_expirations.is_running():
        check_expirations.start()

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
            await db.execute("DELETE FROM user_plans WHERE user_id = ?", (user_id,))
            await db.commit()

            endpoint_str = f"{ip}:{port}" if port else ip
            if ALERT_CHANNEL_ID:
                channel = bot.get_channel(ALERT_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(
                        title="🔴 PLAN EXPIRED",
                        description=f"User <@{user_id}> plan has expired.\nAssigned GitHub Repo: `{assigned_bot}`\nEndpoint was: `{endpoint_str}`\nSlot is now free!",
                        color=discord.Color.dark_red()
                    )
                    await channel.send(embed=embed)

@bot.command(name="claim")
async def prefix_claim(ctx, invites: int, ip: str, port: str = None):
    if invites not in PLANS_DATA:
        valid_tiers = ", ".join([str(k) for k in PLANS_DATA.keys()])
        await ctx.send(f"❌ Invalid invite plan tier! Choose from: `{valid_tiers}`.")
        return

    plan_info = PLANS_DATA[invites]
    plan_name = plan_info["name"]
    days = plan_info["days"]

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT expires_at FROM user_plans WHERE user_id = ?", (ctx.author.id,)) as cursor:
            existing_plan = await cursor.fetchone()
        if existing_plan:
            await ctx.send(f"❌ You already have an active plan running until `{existing_plan[0]} UTC`.")
            return

        async with db.execute("SELECT COUNT(*) FROM user_plans") as cursor:
            slot_row = await cursor.fetchone()
            active_slots = slot_row[0] if slot_row else 0

        if active_slots >= MAX_SLOTS:
            await ctx.send(f"❌ **Slots Full ({active_slots}/{MAX_SLOTS})!**")
            return

        async with db.execute("SELECT earned_credits - spent_credits FROM members WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            available = row[0] if row else 0

        if available < invites:
            await ctx.send(f"❌ Insufficient invites! You need **{invites}** invites.")
            return

        async with db.execute("SELECT assigned_bot FROM user_plans") as cursor:
            assigned_rows = await cursor.fetchall()
        taken_bots = {row[0] for row in assigned_rows}

        available_bots = [b for b in AFK_BOTS_POOL if b not in taken_bots]
        if not available_bots:
            await ctx.send("❌ Error: All 50 bot repository slots are currently deployed!")
            return

        assigned_bot = available_bots[0]
        expires_at = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

        await db.execute("UPDATE members SET spent_credits = spent_credits + ? WHERE user_id = ?", (invites, ctx.author.id))
        await db.execute("""
            INSERT INTO user_plans (user_id, plan_name, status, ip_address, port, assigned_bot, expires_at)
            VALUES (?, ?, 'Online', ?, ?, ?, ?)
        """, (ctx.author.id, plan_name, ip, port, assigned_bot, expires_at))
        await db.commit()

    endpoint_display = f"{ip}:{port}" if port else ip
    await ctx.send(f"✅ **Plan Claimed Successfully!**\n📦 **Plan:** {plan_name}\n🤖 **Assigned GitHub Repo:** `{assigned_bot}`\n🌐 **Target IP/Endpoint:** `{endpoint_display}`\n⏳ **Expires At:** `{expires_at} UTC`")

    if ALERT_CHANNEL_ID:
        alert_channel = bot.get_channel(ALERT_CHANNEL_ID)
        if alert_channel:
            embed = discord.Embed(title="🤖 New AFK Bot Deployed & Claimed", color=discord.Color.from_rgb(87, 242, 135))
            embed.add_field(name="Member", value=f"{ctx.author.mention} (`{ctx.author}`)", inline=False)
            embed.add_field(name="Claimed Plan", value=plan_name, inline=True)
            embed.add_field(name="Invites Spent", value=str(invites), inline=True)
            embed.add_field(name="Assigned GitHub Repo", value=f"`{assigned_bot}`", inline=False)
            embed.add_field(name="Server Endpoint", value=f"`{endpoint_display}`", inline=False)
            embed.add_field(name="Expiry Time", value=f"{expires_at} UTC", inline=False)
            await alert_channel.send(embed=embed)

@bot.command(name="remove")
@commands.has_permissions(administrator=True)
async def prefix_remove_plan(ctx, user_input: str):
    target_id = None
    if user_input.startswith("<@") and user_input.endswith(">"):
        cleaned = user_input.replace("<@", "").replace("!", "").replace(">", "")
        if cleaned.isdigit():
            target_id = int(cleaned)
    elif user_input.isdigit():
        target_id = int(user_input)

    if not target_id:
        await ctx.send("❌ Please provide a valid Member Mention or User ID! Example: `$remove @User` or `$remove 123456789`")
        return

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT assigned_bot, ip_address, port FROM user_plans WHERE user_id = ?", (target_id,)) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            await ctx.send(f"❌ User with ID `{target_id}` has no active plan or repo assigned.")
            return

        assigned_bot, ip, port = row
        await db.execute("DELETE FROM user_plans WHERE user_id = ?", (target_id,))
        await db.commit()

    await ctx.send(f"✅ Successfully removed plan and released assigned repo **`{assigned_bot}`** for user ID `{target_id}`.")

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

        async with db.execute("SELECT plan_name, assigned_bot, ip_address, port, expires_at FROM user_plans WHERE user_id = ?", (target.id,)) as cursor:
            plan_row = await cursor.fetchone()

    if plan_row:
        plan_name, assigned_bot, ip, port, expires_at = plan_row
        exp_dt = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
        remaining_days = max(1, (exp_dt - datetime.utcnow()).days)
        expire_display = f"{expires_at} UTC"
        days_display = f"{remaining_days} Days"
        repo_display = f"`{assigned_bot}`"
        endpoint_display = f"`{ip}:{port}`" if port else f"`{ip}`"
    else:
        expire_display = "No Active Plan"
        days_display = "0 Days"
        repo_display = "None"
        endpoint_display = "None"

    embed = discord.Embed(title=f"📊 Invite & Active Plan Status: {target.name}", color=discord.Color.green())
    embed.add_field(name="✅ Current Invites", value=str(current), inline=True)
    embed.add_field(name="💸 Used Invites", value=str(spent), inline=True)
    embed.add_field(name="🚫 Fake Invites", value=str(fake), inline=True)
    embed.add_field(name="🤖 Active GitHub Repo", value=repo_display, inline=False)
    embed.add_field(name="🌐 Target Server", value=endpoint_display, inline=False)
    embed.add_field(name="⏳ Plan Expire Time", value=expire_display, inline=True)
    embed.add_field(name="📅 Remaining Days", value=days_display, inline=True)
    await ctx.send(embed=embed)

@bot.command(name="set")
@commands.has_permissions(administrator=True)
async def prefix_set_invites(ctx, member: discord.Member, amount: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO members (user_id, earned_credits) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET earned_credits = ?
        """, (member.id, amount, amount))
        await db.commit()
    await ctx.send(f"✅ Successfully set earned invites for {member.mention} to **{amount}**.")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(DISCORD_TOKEN)
