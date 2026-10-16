import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
from config import config

DB_PATH = config.DATABASE_PATH.replace("sqlite:///", "")

class Invites(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="invites", aliases=["i", "checkinvite"])
    async def prefix_invites(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT earned_credits, spent_credits FROM members WHERE user_id = ?", (target.id,)) as cursor:
                row = await cursor.fetchone()
                earned = row[0] if row else 0
                spent = row[1] if row else 0
                available = earned - spent

        embed = discord.Embed(title=f"📊 Invite & Credit Overview: {target.name}", color=discord.Color.green())
        embed.add_field(name="⭐ Earned Invites", value=str(earned), inline=True)
        embed.add_field(name="💸 Spent Credits", value=str(spent), inline=True)
        embed.add_field(name="✅ Available Credits", value=str(available), inline=True)
        embed.set_footer(text=f"Minimum account age requirement: {config.ACCOUNT_AGE_DAYS} days.")
        await ctx.send(embed=embed)

    @app_commands.command(name="invites", description="Check your invite stats and available credits")
    async def slash_invites(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        async with aiosqlite.connect(DB_PATH) as db:
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

async def setup(bot):
    await bot.add_cog(Invites(bot))
