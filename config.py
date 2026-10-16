import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    ALLOWED_GUILD_ID = int(os.getenv("ALLOWED_GUILD_ID", 0))
    PORT = int(os.getenv("PORT", 10000))
    DATABASE_PATH = os.getenv("DATABASE_PATH", "sqlite:///vorstyafk.db")
    ACCOUNT_AGE_DAYS = int(os.getenv("ACCOUNT_AGE_DAYS", 7))
    
    # Alert Channel & Slots Configuration
    ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID", 0))
    MAX_SLOTS = int(os.getenv("MAX_SLOTS", 50))
    
    # Admin Role IDs
    ADMIN_ROLE_IDS = [
        int(r.strip()) for r in os.getenv("ADMIN_ROLE_IDS", "").split(",") if r.strip().isdigit()
    ]
    
    # Minecraft Config
    MC_RCON_HOST = os.getenv("MC_RCON_HOST", "")
    MC_RCON_PORT = int(os.getenv("MC_RCON_PORT", 25575))
    MC_RCON_PASSWORD = os.getenv("MC_RCON_PASSWORD", "")

    @classmethod
    def validate(cls):
        if not cls.DISCORD_TOKEN:
            raise ValueError("❌ CRITICAL ERROR: DISCORD_TOKEN is missing in environment variables!")
        if not cls.ALLOWED_GUILD_ID:
            raise ValueError("❌ CRITICAL ERROR: ALLOWED_GUILD_ID is missing in environment variables!")
        print("✅ Environment variables loaded and validated successfully.")

config = Config()
