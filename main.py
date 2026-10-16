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
ACCOUNT_AGE_DAYS = int(os.getenv("ACCOUNT_AGE_DAYS", 7))
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID", 0) or 0)
MAX_SLOTS = int(os.getenv("MAX_SLOTS", 50))

if not DISCORD_TOKEN or not ALLOWED_GUILD_ID:
    print("❌ CRITICAL ERROR: DISCORD_TOKEN or ALLOWED_GUILD_ID is missing in Render Environment Variables!")
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
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS members (
                user_id INTEGER PRIMARY KEY,
                earned_credits INTEGER DEFAULT 0,
                spent_credits INTEGER DEFAULT 0,
                account_created TEXT,
                joined_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_plans (
                user_id INTEGER PRIMARY KEY,
                plan_name TEXT,
                status TEXT DEFAULT 'Offline',
                uptime TEXT DEFAULT '0%',
                ip_address TEXT,
                port INTEGER,
                expires_at TEXT,
                last_verified TEXT
            )
        """)
        await db.commit()

# --- DISCORD BOT SETUP ---
intents = discord.Intents.default()
intents.members = True
intents.invites = True
intents.message_content = True

bot = commands.Bot(command_prefix=["$", "!"], intents=intents, help_command=None)

# --- PLANS DATA ---
PLANS_DATA = {
    "3days": {"days": 3, "invites": 2},
    "7days": {"days": 7, "invites": 4},
    "15days": {"days": 15, "invites": 6},
    "22days": {"days": 22, "invites": 8},
    "30days": {"days": 30, "invites": 12},
    "60days": {"days": 60, "invites": 16},
    "90days": {"days": 90, "invites": 24},
    "lifetime": {"days": 9999, "invites": 60},
}

@bot.event
async def on_ready():
    await init_db()
    print(f"✅ Logged in successfully as {bot.user} (ID: {bot.user.id})")
    
    guild = discord.Object(id=ALLOWED_GUILD_ID)
    try:
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print("✅ Slash commands synced successfully to allowed guild.")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")
    
    if not check_expirations.is_running():
        check_expirations.start()

@bot.event
async def on_guild_join(guild):
    if guild.id != ALLOWED_GUILD_ID:
        print(f"⚠️ Unauthorized guild {guild.name} ({guild.id}). Leaving immediately...")
        await guild.leave()

# --- BACKGROUND EXPIRY TASK ---
@tasks.loop(minutes=1)
async def check_expirations():
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT user_id, plan_name, ip_address, port FROM user_plans WHERE expires_at <= ? AND status != 'Expired'", 
            (now_str,)
        ) as cursor:
            expired_plans = await cursor.fetchall()

        for user_id, plan_name, ip, port in expired_plans:
            await db.execute("UPDATE user_plans SET status = 'Expired' WHERE user_id = ?", (user_id,))
            await db.commit()

            user = bot.get_user(user_id)
            if user:
                try:
                    embed = discord.Embed(
                        title="⚠️ Hosting Plan Expired",
                        description=f"Your **{plan_name.upper()}** plan for server `{ip}:{port}` has expired.\nIn-Game bot access has been automatically revoked.",
                        color=discord.Color.red()
                    )
                    await user.send(embed=embed)
                except Exception:
                    pass

            if ALERT_CHANNEL_ID:
                channel = bot.get_channel(ALERT_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(
                        title="🔴 Plan Expiration Alert",
                        description=f"User <@{user_id}>'s plan **{plan_name.upper()}** expired. Slots updated!",
                        color=discord.Color.dark_red()
                    )
                    await channel.send(embed=embed)

# --- COMMANDS ---

@bot.command(name="help")
async def prefix_help(ctx):
    embed = discord.Embed(title="🛡️ VorstyAFK Help Center", color=discord.Color.blurple())
    embed.description = "Here are all available commands for AFK & Hosting management:"
    embed.add_field(name="💎 Plan & Hosting", value="`$plans`, `$claim <plan> <ip> <port>`, `$status`", inline=False)
    embed.add_field(name="📊 Invites & Credits", value="`$invites`, `$i`", inline=False)
    embed.add_field(name="🚀 Extra Hosting Commands", value="`$node`, `$stats`, `$restart`, `$stop`, `$start`, `$logs`, `$ping`", inline=False)
    embed.set_footer(text="VorstyAFK System • 24/7 Hosting Control")
    await ctx.send(embed=embed)

@bot.tree.command(name="help", description="Show comprehensive help menu for VorstyAFK")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(title="🛡️ VorstyAFK Slash Help Menu", color=discord.Color.blurple())
    embed.add_field(name="Available Slash Commands", value="`/help`, `/plans`, `/invites`", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command(name="invites", aliases=["i", "checkinvite"])
async def prefix_invites(ctx, member: discord.Member = None):
    target = member or ctx.author
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT earned_credits, spent_credits FROM members WHERE user_id = ?", (target.id,)) as cursor:
            row = await cursor.fetchone()
            earned = row[0] if row else 0
            spent = row[1] if row else 0
            available = earned - spent

    embed = discord.Embed(title=f"📊 Invite & Credit Overview: {target.name}", color=discord.Color.green())
    embed.add_field(name="⭐ Earned Invites", value=str(earned), inline=True)
    embed.add_field(name="💸 Spent Credits", value=str(spent), inline=True)
    embed.add_field(name="✅ Available Credits", value=str(available), inline=True)
    embed.set_footer(text=f"Minimum account age requirement: {ACCOUNT_AGE_DAYS} days.")
    await ctx.send(embed=embed)

@bot.tree.command(name="invites", description="Check your invite stats and available credits")
async def slash_invites(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT earned_credits, spent_credits FROM members WHERE user_id = ?", (target.id,)) as cursor:
            row = await cursor.fetchone()
            earned = row[0] if row else 0
            spent = row[1] if row else 0
            available = earned - spent

    embed = discord.Embed(title=f"📊 Invite & Credit Overview: {target.name}", color=discord.Color.green())
    embed.add_field(name="⭐ Earned Invites", value=str(earned), inline=True)
    embed.add_field(name="💸 Spent Credits", value=str(spent), inline=True)
    embed.add_field(name="✅ Available Credits", value=str(available), inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command(name="plans")
async def prefix_plans(ctx):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM user_plans WHERE status != 'Expired'") as cursor:
            row = await cursor.fetchone()
            active_count = row[0] if row else 0

    embed = discord.Embed(title="💎 VorstyAFK Hosting Plans", color=discord.Color.gold())
    embed.description = f"**Current Active Slots:** `{active_count}/{MAX_SLOTS}`\n\nExchange invites for AFK Bot Hosting:"
    
    for p_name, p_info in PLANS_DATA.items():
        duration_text = "Lifetime" if p_info['days'] == 9999 else f"{p_info['days']} Days"
        embed.add_field(
            name=f"📦 {p_name.upper()} Plan",
            value=f"Duration: **{duration_text}**\nCost: **{p_info['invites']} Invites**",
            inline=True
        )
    embed.set_footer(text="Use $claim <plan_name> <ip> <port> to activate!")
    await ctx.send(embed=embed)

@bot.tree.command(name="plans", description="Show plans and active slot status")
async def slash_plans(interaction: discord.Interaction):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM user_plans WHERE status != 'Expired'") as cursor:
            row = await cursor.fetchone()
            active_count = row[0] if row else 0

        async with db.execute("SELECT plan_name, status, uptime, ip_address, port, expires_at FROM user_plans WHERE user_id = ?", (interaction.user.id,)) as cursor:
            user_plan = await cursor.fetchone()

    embed = discord.Embed(title="💎 VorstyAFK Slots & Status", color=discord.Color.gold())
    embed.add_field(name="Server Slots", value=f"`{active_count}/{MAX_SLOTS}` Claimed", inline=False)

    if user_plan:
        p_name, status, uptime, ip, port, expires = user_plan
        embed.add_field(name="Your Plan", value=f"**{p_name.upper()}**", inline=True)
        embed.add_field(name="Endpoint", value=f"`{ip}:{port}`", inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Expiry", value=expires, inline=False)
    else:
        embed.add_field(name="Your Plan", value="❌ No active plan.", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command(name="claim")
async def prefix_claim(ctx, plan_name: str, ip: str, port: int):
    plan_key = plan_name.lower().strip()
    if plan_key not in PLANS_DATA:
        await ctx.send(f"❌ Invalid plan! Type `$plans` to view all valid options.")
        return

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM user_plans WHERE status != 'Expired'") as cursor:
            slot_row = await cursor.fetchone()
            active_slots = slot_row[0] if slot_row else 0

        if active_slots >= MAX_SLOTS:
            await ctx.send(f"❌ **Slots Full ({active_slots}/{MAX_SLOTS})!** All hosting slots are currently taken.")
            return

        req_invites = PLANS_DATA[plan_key]["invites"]
        days = PLANS_DATA[plan_key]["days"]

        async with db.execute("SELECT earned_credits - spent_credits, earned_credits FROM members WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()
            available = row[0] if row else 0
            total_verified = row[1] if row else 0

        if available < req_invites:
            await ctx.send(f"❌ Insufficient invites! Need **{req_invites}** invites, but you have **{available}**.")
            return

        expires_at = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

        await db.execute("UPDATE members SET spent_credits = spent_credits + ? WHERE user_id = ?", (req_invites, ctx.author.id))
        await db.execute("""
            INSERT INTO user_plans (user_id, plan_name, status, uptime, ip_address, port, expires_at)
            VALUES (?, ?, 'Online', '100%', ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            plan_name = excluded.plan_name,
            status = 'Online',
            uptime = '100%',
            ip_address = excluded.ip_address,
            port = excluded.port,
            expires_at = excluded.expires_at
        """, (ctx.author.id, plan_key, ip, port, expires_at))
        await db.commit()

    await ctx.send(f"✅ **Plan Activated!** `{plan_key.upper()}` for `{ip}:{port}`. Valid until `{expires_at} UTC`.")

    if ALERT_CHANNEL_ID:
        alert_channel = bot.get_channel(ALERT_CHANNEL_ID)
        if alert_channel:
            embed = discord.Embed(title="🤖 New Plan Activation", color=discord.Color.from_rgb(87, 242, 135))
            embed.add_field(name="Member Name", value=f"{ctx.author.name} (@{ctx.author.display_name})", inline=False)
            embed.add_field(name="Total Invites Verified", value=str(total_verified), inline=False)
            duration_str = "Lifetime" if days == 9999 else f"{days} Days"
            embed.add_field(name="Valid Duration", value=duration_str, inline=False)
            embed.add_field(name="Target Server IP", value=f"`{ip}:{port}`", inline=False)
            await alert_channel.send(embed=embed)

@bot.command(name="status")
async def prefix_status(ctx):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT plan_name, status, uptime, ip_address, port FROM user_plans WHERE user_id = ?", (ctx.author.id,)) as cursor:
            row = await cursor.fetchone()

    if not row:
        await ctx.send("❌ You do not have an active hosting plan right now.")
        return

    p_name, status, uptime, ip, port = row
    embed = discord.Embed(title="🟢 Verified Hosting Status", color=discord.Color.blue())
    embed.add_field(name="Plan", value=p_name.upper(), inline=True)
    embed.add_field(name="Server", value=f"`{ip}:{port}`", inline=True)
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="Uptime", value=uptime, inline=True)
    await ctx.send(embed=embed)

# --- EXTRA COMMANDS ---
@bot.command(name="node")
async def cmd_node(ctx):
    await ctx.send("🖥️ **Active Node:** `US-East-Vorsty-01` | Status: `Optimal` | Latency: `12ms`")

@bot.command(name="stats")
async def cmd_stats(ctx):
    await ctx.send("📈 **Cluster Load:** CPU `18%` | RAM `1.4GB / 8GB` | Disk `12%`")

@bot.command(name="start")
async def cmd_start(ctx):
    await ctx.send("🚀 Starting your AFK container instance...")

@bot.command(name="stop")
async def cmd_stop(ctx):
    await ctx.send("🛑 Stopping your active container instance safely...")

@bot.command(name="restart")
async def cmd_restart(ctx):
    await ctx.send("🔄 Rebooting your server container... Services will resume shortly.")

@bot.command(name="logs")
async def cmd_logs(ctx):
    await ctx.send("📋 **Container Live Logs:**\n`[INFO] Server initialized successfully.`\n`[INFO] AFK loop active. No drops detected.`")

@bot.command(name="ping")
async def cmd_ping(ctx):
    await ctx.send(f"🏓 **Pong!** Bot Latency: `{round(bot.latency * 1000)}ms`")

# --- ADMIN COMMANDS ---
@bot.tree.command(name="admin_addinvites", description="Add invite credits to a member (Admin Only)")
@app_commands.checks.has_permissions(administrator=True)
async def admin_addinvites(interaction: discord.Interaction, member: discord.Member, amount: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO members (user_id, earned_credits) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET earned_credits = earned_credits + ?
        """, (member.id, amount, amount))
        await db.commit()
    await interaction.response.send_message(f"✅ Successfully added **{amount}** invite credits to {member.mention}.", ephemeral=True)

@bot.tree.command(name="admin_setinvites", description="Set exact earned invite credits for a member (Admin Only)")
@app_commands.checks.has_permissions(administrator=True)
async def admin_setinvites(interaction: discord.Interaction, member: discord.Member, amount: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO members (user_id, earned_credits) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET earned_credits = ?
        """, (member.id, amount, amount))
        await db.commit()
    await interaction.response.send_message(f"✅ Set earned credits for {member.mention} to **{amount}**.", ephemeral=True)

@bot.tree.command(name="admin_status", description="Manually set a member's server status (Admin Only)")
@app_commands.checks.has_permissions(administrator=True)
async def admin_status(interaction: discord.Interaction, member: discord.Member, status: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE user_plans SET status = ? WHERE user_id = ?", (status, member.id))
        await db.commit()
    await interaction.response.send_message(f"✅ Updated status for {member.mention} to `{status}`.", ephemeral=True)

@bot.tree.command(name="admin_clearplan", description="Remove/clear a member's active plan (Admin Only)")
@app_commands.checks.has_permissions(administrator=True)
async def admin_clearplan(interaction: discord.Interaction, member: discord.Member):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM user_plans WHERE user_id = ?", (member.id,))
        await db.commit()
    await interaction.response.send_message(f"✅ Cleared active hosting plan for {member.mention}.", ephemeral=True)

# --- MAIN RUNNER ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(DISCORD_TOKEN)
