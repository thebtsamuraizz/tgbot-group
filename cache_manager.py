"""
Persistent cache manager for profiles with JSON storage.
Ensures new profiles are preserved after bot restart.
"""
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from threading import Lock
import config

logger = logging.getLogger(__name__)

_lock = Lock()


class PersistentProfileCache:
    """
    Manages profile caching with JSON persistence.
    Automatically saves new profiles to disk for recovery after restart.
    """
    
    def __init__(self, cache_file: str = None):
        self.cache_file = cache_file or config.PROFILE_CACHE_FILE
        self.cache: Dict[int, Dict[str, Any]] = {}
        self.timestamps: Dict[int, datetime] = {}
        self.ttl = config.PROFILE_CACHE_TTL
        self._load_from_disk()
    
    def _load_from_disk(self) -> None:
        """Load cache from JSON file on startup"""
        with _lock:
            try:
                cache_path = Path(self.cache_file)
                if cache_path.exists():
                    with open(cache_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.cache = data.get('cache', {})
                        # Convert string keys back to integers
                        self.cache = {int(k): v for k, v in self.cache.items()}
                        logger.info(f'Loaded {len(self.cache)} profiles from cache file')
                        
                        # Initialize timestamps
                        for pid in self.cache:
                            self.timestamps[pid] = datetime.now()
            except Exception as e:
                logger.warning(f'Failed to load cache from disk: {e}')
                self.cache = {}
                self.timestamps = {}
    
    def _save_to_disk(self) -> None:
        """Persist cache to JSON file"""
        try:
            cache_path = Path(self.cache_file)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert integer keys to strings for JSON
            cache_data = {
                'cache': {str(k): v for k, v in self.cache.items()},
                'saved_at': datetime.now().isoformat()
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f'Failed to save cache to disk: {e}')
    
    def get(self, pid: int) -> Optional[Dict[str, Any]]:
        """Get profile from cache if not expired"""
        with _lock:
            if pid not in self.cache:
                return None
            
            # Check if cache entry has expired
            if pid in self.timestamps:
                age = datetime.now() - self.timestamps[pid]
                if age > timedelta(seconds=self.ttl):
                    del self.cache[pid]
                    del self.timestamps[pid]
                    return None
            
            return self.cache.get(pid)
    
    def set(self, pid: int, profile: Dict[str, Any]) -> None:
        """Set profile in cache and persist to disk"""
        with _lock:
            self.cache[pid] = profile
            self.timestamps[pid] = datetime.now()
        self._save_to_disk()
    
    def update(self, pid: int, updates: Dict[str, Any]) -> None:
        """Update specific fields of a cached profile"""
        with _lock:
            if pid in self.cache:
                self.cache[pid].update(updates)
                self.timestamps[pid] = datetime.now()
        self._save_to_disk()
    
    def invalidate(self, pid: int) -> None:
        """Remove profile from cache"""
        with _lock:
            if pid in self.cache:
                del self.cache[pid]
            if pid in self.timestamps:
                del self.timestamps[pid]
        self._save_to_disk()
    
    def invalidate_all(self) -> None:
        """Clear entire cache"""
        with _lock:
            self.cache.clear()
            self.timestamps.clear()
        self._save_to_disk()
    
    def get_all(self) -> List[Dict[str, Any]]:
        """Get all cached profiles (not expired)"""
        with _lock:
            result = []
            expired_pids = []
            
            for pid, profile in self.cache.items():
                if pid in self.timestamps:
                    age = datetime.now() - self.timestamps[pid]
                    if age > timedelta(seconds=self.ttl):
                        expired_pids.append(pid)
                        continue
                
                result.append(profile)
            
            # Clean up expired entries
            for pid in expired_pids:
                del self.cache[pid]
                if pid in self.timestamps:
                    del self.timestamps[pid]
            
            return result
    
    def exists(self, pid: int) -> bool:
        """Check if profile exists in cache and not expired"""
        return self.get(pid) is not None


# Global cache instance
profile_cache = PersistentProfileCache()
