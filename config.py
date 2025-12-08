import os
from typing import List
try:
    from dotenv import load_dotenv

    # load .env automatically when present
    load_dotenv()
except Exception:
    # dotenv not installed / not available in some environments — ignore
    pass


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


DB_PATH = os.getenv("DB_PATH", "db.sqlite")
