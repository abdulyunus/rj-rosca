"""
Caching layer for Google Sheets data
"""

from typing import Any, Optional, Dict
import time
import logging
from core.config import settings

logger = logging.getLogger(__name__)

# In-memory cache
_cache: Dict[str, dict] = {}


def init_cache():
    """Initialize cache"""
    logger.info("Cache initialized")


def get_cached(key: str) -> Optional[Any]:
    """Get value from cache if not expired"""
    if key not in _cache:
        return None
    
    entry = _cache[key]
    if time.time() > entry['expires_at']:
        del _cache[key]
        return None
    
    logger.debug(f"Cache hit: {key}")
    return entry['value']


def set_cache(key: str, value: Any, ttl: Optional[int] = None):
    """Set value in cache with TTL"""
    if ttl is None:
        ttl = settings.CACHE_TTL_SECONDS
    
    _cache[key] = {
        'value': value,
        'expires_at': time.time() + ttl
    }
    logger.debug(f"Cache set: {key} (TTL: {ttl}s)")


def clear_cache(key: Optional[str] = None):
    """Clear specific cache entry or all cache"""
    if key:
        if key in _cache:
            del _cache[key]
            logger.debug(f"Cache cleared: {key}")
    else:
        _cache.clear()
        logger.debug("All cache cleared")


def get_cache_keys() -> list:
    """Get all cache keys"""
    return list(_cache.keys())


def get_cache_info() -> dict:
    """Get cache statistics"""
    return {
        'keys_count': len(_cache),
        'keys': get_cache_keys()
    }
