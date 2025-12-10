"""
Validation and sanitization utilities for user input.
Ensures data integrity and security.
"""
import re
import logging
from typing import Tuple
import config

logger = logging.getLogger(__name__)

# Forbidden words/patterns
FORBIDDEN_PATTERNS = [
    r'spam', r'phishing', r'scam', r'bot', r'hack',
    r'xxx', r'porn', r'18\+', r'nudes',
]

# URL pattern for detection and replacement
URL_PATTERN = re.compile(
    r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
)


def validate_profile_text(text: str) -> Tuple[bool, str | None]:
    """
    Validate profile submission text.
    
    Returns:
        (is_valid, error_message)
    """
    if not text:
        return False, "Текст не может быть пустым"
    
    text = text.strip()
    
    if len(text) < config.MIN_PROFILE_LENGTH:
        return False, f"Минимум {config.MIN_PROFILE_LENGTH} символов"
    
    if len(text) > config.MAX_PROFILE_LENGTH:
        return False, f"Максимум {config.MAX_PROFILE_LENGTH} символов"
    
    # Check for forbidden content
    text_lower = text.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, text_lower):
            return False, "Найден запрещенный контент"
    
    return True, None


def sanitize_text(text: str, remove_urls: bool = False) -> str:
    """
    Sanitize user input text.
    
    Args:
        text: Input text to sanitize
        remove_urls: If True, replace URLs with [ссылка]
    
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    text = text.strip()
    
    if remove_urls:
        text = URL_PATTERN.sub('[ссылка]', text)
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text


def validate_username(username: str) -> Tuple[bool, str | None]:
    """
    Validate Telegram username format.
    
    Returns:
        (is_valid, error_message)
    """
    if not username:
        return False, "Username не может быть пустым"
    
    # Remove @ if present
    username = username.lstrip('@')
    
    # Username rules: 5-32 characters, alphanumeric and underscore
    if len(username) < 5 or len(username) > 32:
        return False, "Username должен быть от 5 до 32 символов"
    
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Username может содержать только буквы, цифры и подчеркивание"
    
    return True, None


def validate_age(age: int | str) -> Tuple[bool, str | None]:
    """
    Validate user age.
    
    Returns:
        (is_valid, error_message)
    """
    try:
        if isinstance(age, str):
            age = int(age.strip())
        
        if age < 10:
            return False, "Возраст должен быть не менее 10 лет"
        
        if age > 120:
            return False, "Возраст должен быть не более 120 лет"
        
        return True, None
    except (ValueError, TypeError):
        return False, "Возраст должен быть числом"


def sanitize_profile_data(data: dict) -> dict:
    """
    Sanitize all profile fields.
    
    Args:
        data: Profile dictionary
    
    Returns:
        Sanitized profile dictionary
    """
    sanitized = {}
    
    for key, value in data.items():
        if value is None:
            sanitized[key] = None
        elif isinstance(value, str):
            # IMPORTANT: Do NOT sanitize 'note' field - it needs to preserve line breaks
            if key == 'note':
                sanitized[key] = value.strip()  # Only strip, don't remove newlines
            else:
                sanitized[key] = sanitize_text(value)
        else:
            sanitized[key] = value
    
    return sanitized


def is_spam(text: str, threshold: float = 0.5) -> bool:
    """
    Simple spam detection based on caps and special chars ratio.
    
    Args:
        text: Text to check
        threshold: Ratio threshold (0-1)
    
    Returns:
        True if likely spam
    """
    if not text or len(text) < 5:
        return False
    
    caps_count = sum(1 for c in text if c.isupper())
    special_count = sum(1 for c in text if not c.isalnum() and c != ' ')
    
    ratio = (caps_count + special_count) / len(text)
    
    return ratio > threshold
