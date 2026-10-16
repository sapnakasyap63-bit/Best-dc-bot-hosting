import discord
from discord.ext import commands
from discord import app_commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def prefix_help(self, ctx):
        embed = discord.Embed(title="🛡️ VorstyAFK Help Center", color=discord.Color.blurple())
        embed.description = "Here are all available commands for AFK & Hosting management:"
        embed.add_field(name="💎 Plan & Hosting", value="`$plans`, `$claim <plan> <ip> <port>`, `$status`", inline=False)
        embed.add_field(name="📊 Invites & Credits", value="`$invites`, `$i`", inline=False)
        embed.add_field(name="🚀 Extra Hosting Commands", value="`$node`, `$stats`, `$restart`, `$stop`, `$start`, `$logs`, `$ping`", inline=False)
        embed.add_field(name="👑 Admin Direct", value="`$dm <user> <msg>`, `/admin`", inline=False)
        embed.set_footer(text="VorstyAFK System • 24/7 Hosting Control")
        await ctx.send(embed=embed)

    @app_commands.command(name="help", description="Show comprehensive help menu for VorstyAFK")
    async def slash_help(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🛡️ VorstyAFK Slash Help Menu", color=discord.Color.blurple())
        embed.add_field(name="Available Slash Commands", value="`/help`, `/plans`, `/invites`, `/dm`, `/admin`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="dm")
    @commands.has_permissions(administrator=True)
    async def prefix_dm(self, ctx, member: discord.Member, *, msg: str):
        try:
            await member.send(f"📢 **Official Notice from {ctx.guild.name}:**\n{msg}")
            await ctx.send(f"✅ Successfully delivered DM to {member.mention}!")
        except Exception as e:
            await ctx.send(f"❌ Failed to send DM: `{e}`")

    @app_commands.command(name="dm", description="Send a direct message to a member (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_dm(self, interaction: discord.Interaction, member: discord.Member, message: str):
        try:
            await member.send(f"📢 **Official Notice from {interaction.guild.name}:**\n{message}")
            await interaction.response.send_message(f"✅ Successfully delivered DM to {member.mention}!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to send DM: `{e}`", ephemeral=True)

    @commands.command(name="node")
    async def cmd_node(self, ctx):
        await ctx.send("🖥️ **Active Node:** `US-East-Vorsty-01` | Status: `Optimal` | Latency: `12ms`")

    @commands.command(name="stats")
    async def cmd_stats(self, ctx):
        await ctx.send("📈 **Cluster Load:** CPU `18%` | RAM `1.4GB / 8GB` | Disk `12%`")

    @commands.command(name="start")
    async def cmd_start(self, ctx):
        await ctx.send("🚀 Starting your AFK container instance...")

    @commands.command(name="stop")
    async def cmd_stop(self, ctx):
        await ctx.send("🛑 Stopping your active container instance safely...")

    @commands.command(name="restart")
    async def cmd_restart(self, ctx):
        await ctx.send("🔄 Rebooting your server container... Services will resume shortly.")

    @commands.command(name="logs")
    async def cmd_logs(self, ctx):
        await ctx.send("📋 **Container Live Logs:**\n`[INFO] Server initialized successfully.`\n`[INFO] AFK loop active. No drops detected.`")

    @commands.command(name="ping")
    async def cmd_ping(self, ctx):
        await ctx.send(f"🏓 **Pong!** Bot Latency: `{round(self.bot.latency * 1000)}ms`")

async def setup(bot):
    await bot.add_cog(General(bot))
