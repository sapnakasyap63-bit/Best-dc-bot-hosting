import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
from config import config

DB_PATH = config.DATABASE_PATH.replace("sqlite:///", "")

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    admin_group = app_commands.Group(name="admin", description="VorstyAFK A-to-Z Administration Panel")

    @admin_group.command(name="info", description="Check admin panel health & database status")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_info(self, interaction: discord.Interaction):
        await interaction.response.send_message("🛠️ **Admin Panel:** Fully operational and secure.", ephemeral=True)

    @admin_group.command(name="addinvites", description="Add invite credits to a member")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_addinvites(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO members (user_id, earned_credits) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET earned_credits = earned_credits + ?
            """, (member.id, amount, amount))
            await db.commit()
        await interaction.response.send_message(f"✅ Successfully added **{amount}** invite credits to {member.mention}.", ephemeral=True)

    @admin_group.command(name="setinvites", description="Set exact earned invite credits for a member")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_setinvites(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO members (user_id, earned_credits) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET earned_credits = ?
            """, (member.id, amount, amount))
            await db.commit()
        await interaction.response.send_message(f"✅ Set earned credits for {member.mention} to **{amount}**.", ephemeral=True)

    @admin_group.command(name="status", description="Manually set a member's server status")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_status(self, interaction: discord.Interaction, member: discord.Member, status: str):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE user_plans SET status = ? WHERE user_id = ?", (status, member.id))
            await db.commit()
        await interaction.response.send_message(f"✅ Updated status for {member.mention} to `{status}`.", ephemeral=True)

    @admin_group.command(name="clearplan", description="Remove/clear a member's active plan")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_clearplan(self, interaction: discord.Interaction, member: discord.Member):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM user_plans WHERE user_id = ?", (member.id,))
            await db.commit()
        await interaction.response.send_message(f"✅ Cleared active hosting plan for {member.mention}.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))
