import os
from typing import List
from enum import Enum

try:
    from dotenv import load_dotenv

    # load .env automatically when present
    load_dotenv()
except Exception:
    # dotenv not installed / not available in some environments — ignore
    pass


class Environment(Enum):
    """Application environment types"""
    DEV = "dev"
    PROD = "prod"


# Current environment (default: prod for safety)
BOT_ENV = Environment(os.getenv("BOT_ENV", "prod").lower())

# Logging levels by environment
LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING" if BOT_ENV == Environment.PROD else "DEBUG")


def parse_admin_ids(env: str | None) -> List[int]:
    if not env:
        return []
    parts = [p.strip() for p in env.split(",") if p.strip()]
    ids = []
    for p in parts:
        try:
            ids.append(int(p))
        except ValueError:
            continue
    return ids


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# comma-separated list of admin Telegram user ids
ADMIN_IDS = parse_admin_ids(os.getenv("ADMIN_IDS", "5858124063,1043991178"))

# single super-admin (panel owner) - can be same as ADMIN_IDS or different
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "7009242731"))


# Database configuration
DB_PATH = os.getenv("DB_PATH", "db.sqlite")
CACHE_DIR = os.getenv("CACHE_DIR", "cache")
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")

# Ensure directories exist
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# Rate limiting settings
RATE_LIMIT_PER_SECOND = int(os.getenv("RATE_LIMIT_PER_SECOND", "10"))
RATE_LIMIT_WINDOW = 1  # seconds

# Cache settings
PROFILE_CACHE_TTL = int(os.getenv("PROFILE_CACHE_TTL", "300"))  # 5 minutes
PROFILE_CACHE_FILE = os.path.join(CACHE_DIR, "profiles_cache.json")

# Validation settings
MIN_PROFILE_LENGTH = 10
MAX_PROFILE_LENGTH = 5000
MAX_RETRIES_TELEGRAM = 3
RETRY_BACKOFF_FACTOR = 2
