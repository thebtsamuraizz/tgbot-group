import sqlite3
from typing import Any, Dict, List, Optional
from datetime import datetime
from threading import Lock
from config import DB_PATH

_lock = Lock()


def _connect():
    """Create optimized SQLite connection for concurrent access"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    # WAL mode enables concurrent reads without blocking writes
    conn.execute("PRAGMA journal_mode=WAL")
    # Sync mode NORMAL provides good balance between safety and speed
    conn.execute("PRAGMA synchronous=NORMAL")
    # Increase cache size for better performance
    conn.execute("PRAGMA cache_size=10000")
    # Enable query optimization
    conn.execute("PRAGMA optimize")
    return conn


def init_db() -> None:
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        # profiles table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                age INTEGER,
                name TEXT,
                country TEXT,
                city TEXT,
                timezone TEXT,
                tz_offset INTEGER,
                languages TEXT,
                note TEXT,
                added_by TEXT,
                added_by_id INTEGER,
                status TEXT,
                added_at TEXT
            )
            """
        )
        # reports table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id INTEGER,
                reporter_username TEXT,
                category TEXT,
                target_identifier TEXT,
                reason TEXT,
                attachments TEXT,
                created_at TEXT
            )
            """
        )
        # migrations for older DBs: if the new columns are missing, add them
        cur.execute("PRAGMA table_info(profiles)")
        existing = [r[1] for r in cur.fetchall()]
        # PRAGMA rows: cid, name, type, notnull, dflt_value, pk
        if 'added_by_id' not in existing:
            try:
                cur.execute("ALTER TABLE profiles ADD COLUMN added_by_id INTEGER")
            except Exception:
                pass
        if 'status' not in existing:
            try:
                cur.execute("ALTER TABLE profiles ADD COLUMN status TEXT")
                # safe default for existing rows
                cur.execute("UPDATE profiles SET status = 'approved' WHERE status IS NULL OR status = ''")
            except Exception:
                pass
        
        # Create indexes for fast queries
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_profiles_username ON profiles(username)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_profiles_status ON profiles(status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_profiles_added_by_id ON profiles(added_by_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_category ON reports(category)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_reporter_id ON reports(reporter_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at)")
        except Exception:
            pass
        
        conn.commit()
        conn.close()
    # seed initial data
    _seed_profiles()


def _seed_profiles() -> None:
    seed = [
        {"username": "thebitsamuraiizz", "age": 13, "name": None, "country": "Азербайджан", "city": "Баку", "timezone": "UTC+4", "tz_offset": 4, "languages": "Русский, Английский, Азербайджанский", "note": "☆ 𝕋𝕙𝕖 𝔹𝕚𝕥𝕤𝕒𝕞𝕦𝕣𝕒𝕚𝕚𝕫𝕫 ☆ — декоративный стиль"},
        {
            "username": "SkeeYee_j",
            "age": 16,
            "name": None,
            "country": "Россия",
            "city": None,
            "timezone": "+5 к мск",
            "tz_offset": 5,
            "languages": None,
            "note": None,
        },
        {"username": "Cannella_S", "age": None, "name": None, "country": None, "city": None, "timezone": None, "tz_offset": None, "languages": None, "note": None},
        {"username": "nurkotik", "age": 15, "name": None, "country": "Украина", "city": None, "timezone": None, "tz_offset": None, "languages": None, "note": None},
        {"username": "FAFNIR5", "age": 16, "name": "Назар", "country": "Центральная Европа", "city": "Виттен", "timezone": "UTC+1", "tz_offset": 1, "languages": None, "note": None},
        {"username": "doob_rider", "age": 16, "name": "Мирхан", "country": "Казахстан", "city": None, "timezone": "+2 к мск", "tz_offset": 2, "languages": None, "note": None},
        {"username": "Tecno2027", "age": 14, "name": "Тимофей", "country": "Россия", "city": "Екатеринбург", "timezone": "UTC+5", "tz_offset": 5, "languages": None, "note": None},
        {"username": "kixxzzl", "age": 15, "name": "Алёна", "country": "Беларусь", "city": "посёлок Красногорский", "timezone": None, "tz_offset": None, "languages": None, "note": None},
        {"username": "L9g9nda", "age": 11, "name": "создатель", "country": "Украина", "city": "Полтава", "timezone": "+1 к мск", "tz_offset": 1, "languages": None, "note": None},
        {"username": "denji_kuni", "age": 12, "name": None, "country": "Азербайджан", "city": None, "timezone": "+1 к мск", "tz_offset": 1, "languages": None, "note": None},
    ]

    with _lock:
        conn = _connect()
        cur = conn.cursor()
        for p in seed:
            cur.execute("SELECT id FROM profiles WHERE username = ?", (p['username'],))
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO profiles (username, age, name, country, city, timezone, tz_offset, languages, note, added_by, added_by_id, status, added_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        p['username'],
                        p.get('age'),
                        p.get('name'),
                        p.get('country'),
                        p.get('city'),
                        p.get('timezone'),
                        p.get('tz_offset'),
                        p.get('languages'),
                        p.get('note'),
                        'seed',
                        None,
                        'approved',
                        datetime.utcnow().isoformat(),
                    ),
                )
        conn.commit()
        conn.close()


def add_profile(profile: Dict[str, Any]) -> int:
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        # allow caller to specify status (e.g. seed -> approved), otherwise default pending
        status = profile.get('status') or ('pending' if profile.get('added_by') != 'seed' else 'approved')
        added_by_id = profile.get('added_by_id')
        cur.execute(
            "INSERT INTO profiles (username, age, name, country, city, timezone, tz_offset, languages, note, added_by, added_by_id, status, added_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                profile['username'],
                profile.get('age'),
                profile.get('name'),
                profile.get('country'),
                profile.get('city'),
                profile.get('timezone'),
                profile.get('tz_offset'),
                profile.get('languages'),
                profile.get('note'),
                profile.get('added_by', 'user'),
                added_by_id,
                status,
                profile.get('added_at', datetime.utcnow().isoformat()),
            ),
        )
        pid = cur.lastrowid
        conn.commit()
        conn.close()
        return pid


def get_all_profiles(status: Optional[str] = None) -> List[Dict[str, Any]]:
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        if status:
            cur.execute("SELECT * FROM profiles WHERE status = ? ORDER BY username COLLATE NOCASE", (status,))
        else:
            cur.execute("SELECT * FROM profiles ORDER BY username COLLATE NOCASE")
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
        return rows


def get_profile_by_username(username: str) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM profiles WHERE username = ?", (username,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None


def get_profile_by_id(pid: int) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM profiles WHERE id = ?", (pid,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None


def get_profiles_by_status(status: str) -> List[Dict[str, Any]]:
    return get_all_profiles(status=status)


def update_profile_status_by_id(pid: int, status: str) -> bool:
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("UPDATE profiles SET status = ? WHERE id = ?", (status, pid))
        conn.commit()
        affected = cur.rowcount
        conn.close()
        return affected > 0


def update_profile(username: str, changes: Dict[str, Any]) -> bool:
    keys = []
    values = []
    for k, v in changes.items():
        keys.append(f"{k} = ?")
        values.append(v)
    if not keys:
        return False
    values.append(username)
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(f"UPDATE profiles SET {', '.join(keys)} WHERE username = ?", values)
        conn.commit()
        affected = cur.rowcount
        conn.close()
        return affected > 0


def delete_profile(username: str) -> bool:
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM profiles WHERE username = ?", (username,))
        conn.commit()
        affected = cur.rowcount
        conn.close()
        return affected > 0


def add_report(report: Dict[str, Any]) -> int:
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO reports (reporter_id, reporter_username, category, target_identifier, reason, attachments, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                report.get('reporter_id'),
                report.get('reporter_username'),
                report.get('category'),
                report.get('target_identifier'),
                report.get('reason'),
                report.get('attachments'),
                report.get('created_at', datetime.utcnow().isoformat()),
            ),
        )
        rid = cur.lastrowid
        conn.commit()
        conn.close()
        return rid


def get_reports() -> List[Dict[str, Any]]:
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM reports ORDER BY id DESC")
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
        return rows


def clear_reports() -> bool:
    """Delete all reports from database"""
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM reports")
        conn.commit()
        affected = cur.rowcount
        conn.close()
        return affected > 0
