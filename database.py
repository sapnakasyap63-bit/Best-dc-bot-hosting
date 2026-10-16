import aiosqlite
from config import config

DB_PATH = config.DATABASE_PATH.replace("sqlite:///", "")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS invites (
                invite_code TEXT PRIMARY KEY,
                inviter_id INTEGER,
                uses INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id INTEGER,
                target_id INTEGER,
                action TEXT,
                old_value TEXT,
                new_value TEXT,
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
