#!/usr/bin/env python3
"""
Test script to verify cache and validation functionality.
Run this to ensure all improvements are working correctly.
"""
import sys
import json
from pathlib import Path

# Test imports
try:
    from cache_manager import profile_cache
    from validators import (
        validate_profile_text,
        sanitize_text,
        validate_username,
        validate_age,
        is_spam
    )
    from rate_limiter import rate_limiter
    print("✅ All imports successful\n")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


def test_cache():
    """Test persistent cache functionality"""
    print("=" * 50)
    print("Testing Persistent Cache...")
    print("=" * 50)
    
    # Test 1: Set and get
    test_profile = {
        'id': 1,
        'username': 'testuser',
        'age': 16,
        'country': 'Russia',
        'status': 'pending'
    }
    
    profile_cache.set(1, test_profile)
    retrieved = profile_cache.get(1)
    
    if retrieved == test_profile:
        print("✅ Set/Get: PASS")
    else:
        print("❌ Set/Get: FAIL")
        return False
    
    # Test 2: Update
    profile_cache.update(1, {'status': 'approved'})
    updated = profile_cache.get(1)
    
    if updated['status'] == 'approved':
        print("✅ Update: PASS")
    else:
        print("❌ Update: FAIL")
        return False
    
    # Test 3: Check persistence
    cache_file = Path(profile_cache.cache_file)
    if cache_file.exists():
        print("✅ Persistence: PASS (cache file exists)")
        with open(cache_file, 'r') as f:
            data = json.load(f)
            if '1' in data.get('cache', {}):
                print("   └─ Data persisted to disk: ✅")
            else:
                print("   └─ Data NOT in file: ❌")
    else:
        print("⚠️  Persistence: WARNING (no cache file yet)")
    
    # Test 4: Invalidate
    profile_cache.invalidate(1)
    if profile_cache.get(1) is None:
        print("✅ Invalidate: PASS")
    else:
        print("❌ Invalidate: FAIL")
        return False
    
    print()
    return True


def test_validators():
    """Test input validation"""
    print("=" * 50)
    print("Testing Input Validators...")
    print("=" * 50)
    
    # Test 1: Valid profile text
    is_valid, msg = validate_profile_text("This is a valid profile description")
    if is_valid:
        print("✅ Valid text: PASS")
    else:
        print(f"❌ Valid text: FAIL - {msg}")
        return False
    
    # Test 2: Too short
    is_valid, msg = validate_profile_text("short")
    if not is_valid:
        print("✅ Too short rejection: PASS")
    else:
        print("❌ Too short rejection: FAIL")
        return False
    
    # Test 3: Valid username
    is_valid, msg = validate_username("testuser123")
    if is_valid:
        print("✅ Valid username: PASS")
    else:
        print(f"❌ Valid username: FAIL - {msg}")
        return False
    
    # Test 4: Invalid username
    is_valid, msg = validate_username("abc")
    if not is_valid:
        print("✅ Invalid username rejection: PASS")
    else:
        print("❌ Invalid username rejection: FAIL")
        return False
    
    # Test 5: Valid age
    is_valid, msg = validate_age(16)
    if is_valid:
        print("✅ Valid age: PASS")
    else:
        print(f"❌ Valid age: FAIL - {msg}")
        return False
    
    # Test 6: Too young
    is_valid, msg = validate_age(5)
    if not is_valid:
        print("✅ Too young rejection: PASS")
    else:
        print("❌ Too young rejection: FAIL")
        return False
    
    # Test 7: Sanitize text
    dirty = "Check this link: https://evil.com/malware"
    clean = sanitize_text(dirty, remove_urls=True)
    if "https" not in clean and "[ссылка]" in clean:
        print("✅ Text sanitization: PASS")
    else:
        print(f"❌ Text sanitization: FAIL - {clean}")
        return False
    
    # Test 8: Spam detection
    spam_text = "XXXXXX!!!!!!@@@@@  SPAM SPAM SPAM"
    if is_spam(spam_text, threshold=0.5):
        print("✅ Spam detection: PASS")
    else:
        print("❌ Spam detection: FAIL")
        return False
    
    print()
    return True


def test_rate_limiting():
    """Test rate limiting functionality"""
    print("=" * 50)
    print("Testing Rate Limiting...")
    print("=" * 50)
    
    user_id = 12345
    
    # Test 1: Allow initial requests
    allowed = 0
    for i in range(5):
        if rate_limiter.is_allowed(user_id):
            allowed += 1
    
    if allowed == 5:
        print("✅ Initial requests allowed: PASS")
    else:
        print(f"❌ Initial requests allowed: FAIL (got {allowed}/5)")
        return False
    
    # Test 2: Rate limit exceeded
    rate_limiter.requests[user_id] = []  # Reset for clean test
    for i in range(15):
        rate_limiter.is_allowed(user_id)
    
    # After rate limit should be exceeded
    if not rate_limiter.is_allowed(user_id):
        print("✅ Rate limit enforced: PASS")
    else:
        print("❌ Rate limit enforced: FAIL")
        return False
    
    # Test 3: Get reset time
    reset_time = rate_limiter.get_reset_time(user_id)
    if reset_time > 0:
        print(f"✅ Reset time calculation: PASS ({reset_time}s)")
    else:
        print("❌ Reset time calculation: FAIL")
        return False
    
    print()
    return True


def test_config():
    """Test configuration"""
    print("=" * 50)
    print("Testing Configuration...")
    print("=" * 50)
    
    try:
        import config
        
        # Check required config values
        checks = [
            ('BOT_ENV', config.BOT_ENV),
            ('LOG_LEVEL', config.LOG_LEVEL),
            ('PROFILE_CACHE_TTL', config.PROFILE_CACHE_TTL),
            ('RATE_LIMIT_PER_SECOND', config.RATE_LIMIT_PER_SECOND),
            ('MIN_PROFILE_LENGTH', config.MIN_PROFILE_LENGTH),
            ('MAX_PROFILE_LENGTH', config.MAX_PROFILE_LENGTH),
        ]
        
        for name, value in checks:
            if value is not None:
                print(f"✅ {name}: {value}")
            else:
                print(f"⚠️  {name}: Not set (using default)")
        
        # Check directories
        from pathlib import Path
        cache_dir = Path(config.CACHE_DIR)
        backup_dir = Path(config.BACKUP_DIR)
        
        if cache_dir.exists():
            print(f"✅ Cache directory: {cache_dir}")
        else:
            print(f"⚠️  Cache directory: {cache_dir} (will be created)")
        
        if backup_dir.exists():
            print(f"✅ Backup directory: {backup_dir}")
        else:
            print(f"⚠️  Backup directory: {backup_dir} (will be created)")
        
        print()
        return True
    
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 50)
    print("🧪 BOT IMPROVEMENTS TEST SUITE")
    print("=" * 50 + "\n")
    
    results = {
        'Cache': test_cache(),
        'Validators': test_validators(),
        'Rate Limiting': test_rate_limiting(),
        'Configuration': test_config(),
    }
    
    print("=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Improvements are working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check output above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
