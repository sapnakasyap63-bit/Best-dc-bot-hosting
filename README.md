# 🤖 VorstyAFK Discord Bot

VorstyAFK is a high-performance Discord Bot built for 24/7 Minecraft / AFK hosting management using Python `discord.py 2.x`, SQLite, and Flask.

## 🌟 Key Features
- **Render Web Service Deployment**: Built-in Flask HTTP server running on `0.0.0.0:$PORT` for uptime health checks.
- **Dynamic Slot System**: Enforces server limits (e.g., `50/50` claimed slots).
- **Instant Activation Alerts**: Sends custom green border embed alerts upon plan claiming.
- **Auto Expiration & MC Whitelist**: Background task automatically revokes in-game access on plan expiry.
- **Full Admin Controls**: Slash commands to manage credits, statuses, and plans.

## 🚀 Quick Deployment Guide on Render.com
1. Push all project files to a **GitHub repository**.
2. Go to **Render Dashboard** -> Click **New** -> Select **Web Service**.
3. Connect your GitHub repository.
4. Set **Environment** to `Python 3`.
5. **Build Command**: `pip install -r requirements.txt`
6. **Start Command**: `python main.py`
7. Add Environment Variables (`DISCORD_TOKEN`, `ALLOWED_GUILD_ID`, `ALERT_CHANNEL_ID`, etc.) under the Environment tab.
8. Deploy!
