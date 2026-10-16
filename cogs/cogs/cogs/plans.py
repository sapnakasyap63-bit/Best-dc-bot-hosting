import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
from datetime import datetime, timedelta
from config import config

DB_PATH = config.DATABASE_PATH.replace("sqlite:///", "")

class Plans(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_expirations.start()

    def cog_unload(self):
        self.check_expirations.cancel()

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

    async def update_mc_in_game_access(self, ip: str, port: int, action: str):
        try:
            if action == "ALLOW":
                print(f"🎮 [MC Integration] Granted In-Game Access to {ip}:{port}")
            elif action == "REVOKE":
                print(f"🛑 [MC Integration] Revoked In-Game Access for {ip}:{port}")
        except Exception as e:
            print(f"❌ MC Integration Error: {e}")

    @tasks.loop(minutes=1)
    async def check_expirations(self):
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT user_id, plan_name, ip_address, port FROM user_plans WHERE expires_at <= ? AND status != 'Expired'", 
                (now_str,)
            ) as cursor:
                expired_plans = await cursor.fetchall()

            for user_id, plan_name, ip, port in expired_plans:
                await db.execute("UPDATE user_plans SET status = 'Expired' WHERE user_id = ?", (user_id,))
                await db.commit()

                if ip and port:
                    await self.update_mc_in_game_access(ip, port, "REVOKE")

                user = self.bot.get_user(user_id)
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

                if config.ALERT_CHANNEL_ID:
                    channel = self.bot.get_channel(config.ALERT_CHANNEL_ID)
                    if channel:
                        embed = discord.Embed(
                            title="🔴 Plan Expiration Alert",
                            description=f"User <@{user_id}>'s plan **{plan_name.upper()}** expired. Slots updated!",
                            color=discord.Color.dark_red()
                        )
                        await channel.send(embed=embed)

    @commands.command(name="plans")
    async def prefix_plans(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM user_plans WHERE status != 'Expired'") as cursor:
                row = await cursor.fetchone()
                active_count = row[0] if row else 0

        embed = discord.Embed(title="💎 VorstyAFK Hosting Plans", color=discord.Color.gold())
        embed.description = f"**Current Active Slots:** `{active_count}/{config.MAX_SLOTS}`\n\nExchange invites for AFK Bot Hosting:"
        
        for p_name, p_info in self.PLANS_DATA.items():
            duration_text = "Lifetime" if p_info['days'] == 9999 else f"{p_info['days']} Days"
            embed.add_field(
                name=f"📦 {p_name.upper()} Plan",
                value=f"Duration: **{duration_text}**\nCost: **{p_info['invites']} Invites**",
                inline=True
            )
        embed.set_footer(text="Use $claim <plan_name> <ip> <port> to activate!")
        await ctx.send(embed=embed)

    @app_commands.command(name="plans", description="Show plans and active slot status")
    async def slash_plans(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM user_plans WHERE status != 'Expired'") as cursor:
                row = await cursor.fetchone()
                active_count = row[0] if row else 0

            async with db.execute("SELECT plan_name, status, uptime, ip_address, port, expires_at FROM user_plans WHERE user_id = ?", (interaction.user.id,)) as cursor:
                user_plan = await cursor.fetchone()

        embed = discord.Embed(title="💎 VorstyAFK Slots & Status", color=discord.Color.gold())
        embed.add_field(name="Server Slots", value=f"`{active_count}/{config.MAX_SLOTS}` Claimed", inline=False)

        if user_plan:
            p_name, status, uptime, ip, port, expires = user_plan
            embed.add_field(name="Your Plan", value=f"**{p_name.upper()}**", inline=True)
            embed.add_field(name="Endpoint", value=f"`{ip}:{port}`", inline=True)
            embed.add_field(name="Status", value=status, inline=True)
            embed.add_field(name="Expiry", value=expires, inline=False)
        else:
            embed.add_field(name="Your Plan", value="❌ No active plan.", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="claim")
    async def prefix_claim(self, ctx, plan_name: str, ip: str, port: int):
        plan_key = plan_name.lower().strip()
        if plan_key not in self.PLANS_DATA:
            await ctx.send(f"❌ Invalid plan! Type `$plans` to view all valid options.")
            return

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM user_plans WHERE status != 'Expired'") as cursor:
                slot_row = await cursor.fetchone()
                active_slots = slot_row[0] if slot_row else 0

            if active_slots >= config.MAX_SLOTS:
                await ctx.send(f"❌ **Slots Full ({active_slots}/{config.MAX_SLOTS})!** All hosting slots are currently taken.")
                return

            req_invites = self.PLANS_DATA[plan_key]["invites"]
            days = self.PLANS_DATA[plan_key]["days"]

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

        await self.update_mc_in_game_access(ip, port, "ALLOW")

        await ctx.send(f"✅ **Plan Activated!** `{plan_key.upper()}` for `{ip}:{port}`. Valid until `{expires_at} UTC`.")

        if config.ALERT_CHANNEL_ID:
            alert_channel = self.bot.get_channel(config.ALERT_CHANNEL_ID)
            if alert_channel:
                embed = discord.Embed(
                    title="🤖 New Plan Activation",
                    color=discord.Color.from_rgb(87, 242, 135)
                )
                embed.add_field(
                    name="Member Name",
                    value=f"{ctx.author.name} (@{ctx.author.display_name})",
                    inline=False
                )
                embed.add_field(
                    name="Total Invites Verified",
                    value=str(total_verified),
                    inline=False
                )
                duration_str = "Lifetime" if days == 9999 else f"{days} Days"
                embed.add_field(
                    name="Valid Duration",
                    value=duration_str,
                    inline=False
                )
                embed.add_field(
                    name="Target Server IP",
                    value=f"`{ip}:{port}`",
                    inline=False
                )
                await alert_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Plans(bot))
