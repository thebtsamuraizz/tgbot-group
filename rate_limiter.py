"""
Rate limiting and Telegram API retry logic.
Protects against spam and handles API errors gracefully.
"""
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable, Any
from functools import wraps
from telegram.error import TelegramError, RetryAfter
import config

logger = logging.getLogger(__name__)


class UserRateLimiter:
    """
    Per-user rate limiter to prevent spam.
    """
    
    def __init__(self, max_rate: int = None, time_period: int = 1):
        """
        Args:
            max_rate: Max requests per time_period (default from config)
            time_period: Time window in seconds
        """
        self.max_rate = max_rate or config.RATE_LIMIT_PER_SECOND
        self.time_period = time_period
        self.requests = defaultdict(list)
    
    def is_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to make request"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.time_period)
        
        # Remove old requests outside the window
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id]
            if req_time > cutoff
        ]
        
        # Check if limit exceeded
        if len(self.requests[user_id]) >= self.max_rate:
            return False
        
        # Record this request
        self.requests[user_id].append(now)
        return True
    
    def get_reset_time(self, user_id: int) -> int:
        """Get seconds until user can make next request"""
        if not self.requests[user_id]:
            return 0
        
        oldest = self.requests[user_id][0]
        reset = oldest + timedelta(seconds=self.time_period)
        now = datetime.now()
        
        if reset > now:
            return int((reset - now).total_seconds()) + 1
        return 0


# Global rate limiter
rate_limiter = UserRateLimiter()


async def retry_telegram_request(
    func: Callable,
    *args,
    max_retries: int = None,
    backoff_factor: int = None,
    **kwargs
) -> Any:
    """
    Retry Telegram API request with exponential backoff.
    
    Args:
        func: Async function to call
        max_retries: Max retry attempts (default from config)
        backoff_factor: Exponential backoff multiplier (default from config)
        *args, **kwargs: Arguments to pass to func
    
    Returns:
        Result from func
    """
    max_retries = max_retries or config.MAX_RETRIES_TELEGRAM
    backoff_factor = backoff_factor or config.RETRY_BACKOFF_FACTOR
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        
        except RetryAfter as e:
            # Telegram throttling - wait and retry
            wait_time = e.retry_after + 1
            logger.warning(
                f'Rate limited by Telegram, waiting {wait_time}s '
                f'(attempt {attempt + 1}/{max_retries})'
            )
            await asyncio.sleep(wait_time)
        
        except TelegramError as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                logger.warning(
                    f'Telegram error: {e} '
                    f'(attempt {attempt + 1}/{max_retries}, waiting {wait_time}s)'
                )
                await asyncio.sleep(wait_time)
        
        except Exception as e:
            last_error = e
            logger.error(f'Unexpected error in retry_telegram_request: {e}')
            if attempt < max_retries - 1:
                wait_time = backoff_factor ** attempt
                await asyncio.sleep(wait_time)
    
    raise last_error or TelegramError('Max retries exceeded')


async def send_message_with_retry(context, chat_id: int, text: str, **kwargs) -> bool:
    """
    Send message with automatic retry on error.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        await retry_telegram_request(
            context.bot.send_message,
            chat_id=chat_id,
            text=text,
            **kwargs
        )
        return True
    except Exception as e:
        logger.error(f'Failed to send message to {chat_id}: {e}')
        return False


async def edit_message_with_retry(context, **kwargs) -> bool:
    """
    Edit message with automatic retry on error.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        await retry_telegram_request(
            context.bot.edit_message_text,
            **kwargs
        )
        return True
    except Exception as e:
        logger.error(f'Failed to edit message: {e}')
        return False


def check_rate_limit(func):
    """
    Decorator to enforce rate limiting on handlers.
    
    Usage:
        @check_rate_limit
        async def my_handler(update, context):
            ...
    """
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id if update.effective_user else None
        
        if not user_id:
            return await func(update, context, *args, **kwargs)
        
        if not rate_limiter.is_allowed(user_id):
            reset_time = rate_limiter.get_reset_time(user_id)
            message = f'⏳ Слишком много запросов. Попробуйте через {reset_time} сек.'
            
            try:
                if update.message:
                    await update.message.reply_text(message)
                elif update.callback_query:
                    await update.callback_query.answer(message, show_alert=True)
            except Exception as e:
                logger.error(f'Failed to send rate limit message: {e}')
            
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper
