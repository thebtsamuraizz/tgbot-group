import logging
from datetime import datetime
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


AGE_RE = re.compile(r"\b([8-9][0-9]|[1-7]?\d)\b")
TZ_RE = re.compile(r"(UTC)?\s*([+-]?\d{1,2})")


def parse_profile_text(text: str) -> Dict[str, Any]:
    """Try to parse age, timezone, name, country, city, languages, note.

    Returns dict with recognized fields and list of missing fields to ask.
    """
    data: Dict[str, Any] = {}

    # age
    m = AGE_RE.search(text)
    if m:
        age = int(m.group(1))
        if 8 <= age <= 99:
            data['age'] = age

    # timezone
    m = TZ_RE.search(text)
    if m:
        try:
            offset = int(m.group(2))
            data['tz_offset'] = offset
            text_tz = f"UTC{offset:+d}" if m.group(1) else (f"{offset:+d} к мск" if offset != 0 else "UTC+0")
            data['timezone'] = text_tz
        except Exception:
            pass

    # languages - comma separated list of words (simple heuristic)
    if ',' in text:
        parts = [p.strip() for p in text.split(',') if len(p.strip()) > 0]
        if len(parts) >= 2:
            data['languages'] = ', '.join(parts[:5])

    # username-like tokens: @username
    m = re.search(r"@([A-Za-z0-9_]{1,32})", text)
    if m:
        data['username'] = m.group(1)

    # name (simple heuristic: Words with capitalized first letter - pick first)
    m = re.search(r"\b([А-ЯЁA-Z][а-яёa-z]+)\b", text)
    if m:
        data['name'] = m.group(1)

    # country / city simple heuristics (keywords)
    countries = ["Россия", "Украина", "Казахстан", "Беларусь", "Азербайджан"]
    for c in countries:
        if c.lower() in text.lower():
            data['country'] = c
            break

    # city guess: word after comma or after country
    city_m = re.search(r"[,:]\s*([А-Яа-яЁёA-Za-z\- ]{3,40})", text)
    if city_m:
        candidate = city_m.group(1).strip()
        if len(candidate) < 40 and len(candidate) > 2 and not candidate.isdigit():
            data['city'] = candidate.split('\n')[0].strip()

    # note: remainder length limited
    if len(text) > 200:
        data['note'] = text[:400]
    else:
        data['note'] = text

    # choose required fields to ask: age and username are critical
    need = []
    if 'age' not in data:
        need.append('age')
    if 'username' not in data:
        need.append('username')

    return {'data': data, 'need': need}


def iso_now() -> str:
    return datetime.utcnow().isoformat()


def short_profile_card(profile: Dict[str, Any]) -> str:
    """Format profile card with proper line breaks and emojis.

    Escape user-provided fields for safe HTML output.
    """
    import html as _html
    lines = []

    # Helper to escape or return empty
    def esc(val):
        if val is None:
            return ''
        return _html.escape(str(val))

    # Username
    if profile.get('username'):
        lines.append(f"👤 <b>@{esc(profile.get('username'))}</b>")
    else:
        lines.append("👤 (без ника)")

    # Name
    if profile.get('name'):
        lines.append(f"📝 <b>Имя:</b> {esc(profile.get('name'))}")

    # Age
    if profile.get('age') is not None:
        lines.append(f"🎂 <b>Возраст:</b> {esc(profile.get('age'))}")

    # Country
    if profile.get('country'):
        lines.append(f"🌍 <b>Страна:</b> {esc(profile.get('country'))}")

    # City
    if profile.get('city'):
        lines.append(f"🏙️ <b>Город:</b> {esc(profile.get('city'))}")

    # Timezone
    if profile.get('timezone'):
        lines.append(f"🕐 <b>Часовой пояс:</b> {esc(profile.get('timezone'))}")

    # Languages
    if profile.get('languages'):
        lines.append(f"💬 <b>Языки:</b> {esc(profile.get('languages'))}")

    # Note (preserve all line breaks)
    if profile.get('note'):
        note = esc(profile.get('note', '')).strip()
        if note:
            lines.append(f"📋 <b>Заметка:</b>")
            # preserve original newlines (escaped already)
            lines.extend(note.split('\n'))

    return '\n'.join(lines)
