# 📊 Logging Guide

## Overview

The bot now has comprehensive logging with multiple output formats and destinations.

## Logging Levels

### Development Mode (`BOT_ENV=dev`)
- **Level**: DEBUG
- **Console**: All messages (DEBUG and above)
- **File**: All messages (DEBUG and above)
- **Use**: Development, debugging, testing

```bash
export BOT_ENV=dev
export LOG_LEVEL=DEBUG
python3 main.py
```

### Production Mode (`BOT_ENV=prod`)
- **Level**: WARNING
- **Console**: WARNING and ERROR only
- **File**: All messages
- **Use**: Live deployment

```bash
export BOT_ENV=prod
export LOG_LEVEL=WARNING
python3 main.py
```

## Log Outputs

### 1. Console Output

When you run the bot, you'll see:

```
======================================================================
🤖 TELEGRAM BOT STARTING UP
======================================================================
2025-12-09 11:36:42,186 [INFO] __main__: 🚀 Starting bot in dev environment
2025-12-09 11:36:42,186 [INFO] __main__: 📊 Log level: INFO
2025-12-09 11:36:42,186 [INFO] __main__: 📦 Loading cached profiles from disk...
2025-12-09 11:36:42,426 [INFO] __main__: ✅ Database initialized
2025-12-09 11:36:42,426 [INFO] __main__: 💾 Cached profiles loaded: 10 profiles
2025-12-09 11:36:42,427 [INFO] __main__: 👥 Admin IDs: [123456789, 987654321]
2025-12-09 11:36:42,427 [INFO] __main__: 👑 Super admin ID: 123456789

======================================================================
✅ BOT CONNECTED AND RUNNING
======================================================================
📢 Press Ctrl+C to stop the bot
📊 Logs saved to: bot.log
======================================================================
```

### 2. File Output (`bot.log`)

All logs are saved to `bot.log` including:
- All levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Full tracebacks for errors
- API call details

## Log Format

```
YYYY-MM-DD HH:MM:SS,mmm [LEVEL] logger_name: message
```

Example:
```
2025-12-09 11:36:42,186 [INFO] __main__: ✅ Database initialized
2025-12-09 11:36:42,426 [ERROR] handlers: Failed to save profile: Database locked
```

## Monitoring Logs in Real-time

### Live log monitoring

```bash
tail -f bot.log
```

### Filter by log level

```bash
# Only errors
grep "\[ERROR\]" bot.log

# Warnings and errors
grep "\[WARNING\]\|\[ERROR\]" bot.log

# Info level
grep "\[INFO\]" bot.log

# Debug level
grep "\[DEBUG\]" bot.log
```

### Filter by specific actions

```bash
# Admin review actions
grep "admin_review_cb" bot.log

# New profile submissions
grep "new_profile_confirm_cb" bot.log

# Cache operations
grep "cache_manager" bot.log

# Rate limiting
grep "rate_limit" bot.log

# Database operations
grep "database" bot.log
```

### Search for errors with context

```bash
# Show 10 lines before and after error
grep -B 10 -A 10 "\[ERROR\]" bot.log

# Count errors
grep "\[ERROR\]" bot.log | wc -l

# Show unique errors
grep "\[ERROR\]" bot.log | sort | uniq -c
```

## Logging Locations

### Console
- Startup information
- User-friendly error messages
- Connection status
- INFO and above in production

### File (`bot.log`)
- Complete audit trail
- All log levels
- Full error tracebacks
- API call details

## Important Log Messages

### Startup Messages

```
🚀 Starting bot in dev environment           # Bot initialization
📊 Log level: DEBUG                           # Current log level
📦 Loading cached profiles from disk...       # Cache loading
✅ Database initialized                       # Database ready
💾 Cached profiles loaded: 10 profiles        # Cache count
👥 Admin IDs: [123456789]                     # Admin configuration
👑 Super admin ID: 123456789                  # Super admin ID
```

### Operation Messages

```
[INFO] handlers: new_profile_confirm_cb: user 123456 confirmed new profile @username
[INFO] handlers: admin_review_cb: admin 789 approved profile id=5
[INFO] cache_manager: Cached profile 5 saved to disk
```

### Error Messages

```
[ERROR] handlers: Failed to save profile: username already exists
[ERROR] main: Failed to send error message: Telegram API error
[ERROR] rate_limiter: Max retries exceeded for API call
```

## Configuration

Edit `config.py` to customize logging:

```python
# Log level (default: WARNING in prod, DEBUG in dev)
LOG_LEVEL = "INFO"

# Log file location
LOG_FILE = "bot.log"

# Console level
CONSOLE_LOG_LEVEL = "INFO"

# File level
FILE_LOG_LEVEL = "DEBUG"
```

## Troubleshooting

### Problem: No logs in console

**Solution**: Check LOG_LEVEL setting

```bash
# Force INFO level
export LOG_LEVEL=INFO
python3 main.py
```

### Problem: Log file not created

**Solution**: Check disk space and permissions

```bash
# Verify write permission
touch bot.log
rm bot.log

# Start bot
python3 main.py
```

### Problem: Too many DEBUG logs

**Solution**: Reduce log level

```bash
export BOT_ENV=prod
export LOG_LEVEL=WARNING
python3 main.py
```

### Problem: Logs are too verbose

**Solution**: You can suppress Telegram library logs in code

```python
# Already done in main.py:
logging.getLogger('telegram.ext._application').setLevel(logging.WARNING)
logging.getLogger('telegram.ext._dispatcher').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
```

## Log Rotation

To prevent `bot.log` from getting too large, rotate logs:

```bash
# Manual rotation
mv bot.log bot.log.$(date +%Y%m%d_%H%M%S)
gzip bot.log.*

# Or use logrotate with /etc/logrotate.d/tgbot:
/workspaces/tgbot-group/bot.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

## Useful Log Commands

```bash
# Follow logs in real time with color
tail -f bot.log | grep --color "\[ERROR\]\|\[WARNING\]"

# Show logs from last 5 minutes
grep "2025-12-09 11:" bot.log

# Show logs with timestamps
head -100 bot.log | tail -20

# Find slow operations
grep "duration\|timeout" bot.log

# Show all admin actions
grep "admin_" bot.log

# Export logs to text file
cp bot.log logs_backup_$(date +%Y%m%d).txt
```

## Best Practices

1. **Monitor logs regularly**: Check for unusual patterns
   ```bash
   tail -f bot.log
   ```

2. **Keep logs organized**: Rotate old logs
   ```bash
   gzip bot.log.* && mv bot.log.*.gz archives/
   ```

3. **Use appropriate log levels**: Not DEBUG in production
   ```bash
   export BOT_ENV=prod
   ```

4. **Search efficiently**: Use grep with patterns
   ```bash
   grep "\[ERROR\]" bot.log | sort | uniq
   ```

5. **Archive logs**: Keep historical records
   ```bash
   tar czf logs_$(date +%Y%m).tar.gz bot.log*
   ```

## Related Documentation

- [IMPROVEMENTS.md](IMPROVEMENTS.md) - Error handling details
- [INSTALL.md](INSTALL.md) - Configuration guide
- [config.py](config.py) - Logging configuration

---

**Last Updated**: December 9, 2025
**Status**: Production Ready ✅
