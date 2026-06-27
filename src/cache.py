"""Redis caching layer for dashboard queries.

Design decisions:
- Sync redis-py, NOT aioredis (our handlers are sync; mixing caused event loop conflicts)
- Per-section caching with independent TTLs
- Connection pooling (max 20 connections, matches our worker count)
"""

import json
import random
import logging
from typing import Any, Optional

import redis
from .config import settings

logger = logging.getLogger(__name__)

# Connection pool shared across all workers in this process
_pool = redis.ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=0,
    max_connections=20,
    decode_responses=True,
)

_client = redis.Redis(connection_pool=_pool)


# TTLs per section (seconds) — tuned based on how often each metric changes
SECTION_TTLS = {
    "status_breakdown": 30,    # changes on every task move
    "velocity": 300,           # only changes when sprint closes
    "cycle_time": 900,         # slow-moving, 15min is fine
    "workload": 60,            # changes on assignment
    "overdue": 300,            # recalculated with sprint boundary
}

# Jitter range: ±20% of TTL to prevent stampede
JITTER_FACTOR = 0.2


def _cache_key(team_id: int, section: str) -> str:
    return f"dashboard:{team_id}:{section}"


def _ttl_with_jitter(section: str) -> int:
    base = SECTION_TTLS.get(section, 60)
    jitter = int(base * JITTER_FACTOR)
    return base + random.randint(-jitter, jitter)


def get_cached(team_id: int, section: str) -> Optional[Any]:
    """Retrieve a cached dashboard section. Returns None on miss or Redis failure."""
    try:
        raw = _client.get(_cache_key(team_id, section))
        if raw is not None:
            return json.loads(raw)
        return None
    except (redis.ConnectionError, redis.TimeoutError) as e:
        logger.warning(f"Redis read failed, falling back to DB: {e}")
        return None


def set_cached(team_id: int, section: str, data: Any) -> None:
    """Cache a dashboard section with jittered TTL."""
    try:
        ttl = _ttl_with_jitter(section)
        _client.setex(_cache_key(team_id, section), ttl, json.dumps(data, default=str))
    except (redis.ConnectionError, redis.TimeoutError) as e:
        logger.warning(f"Redis write failed, skipping cache: {e}")


def invalidate_team(team_id: int, sections: list[str] | None = None) -> None:
    """Invalidate specific sections or all sections for a team."""
    targets = sections or list(SECTION_TTLS.keys())
    keys = [_cache_key(team_id, s) for s in targets]
    try:
        _client.delete(*keys)
    except (redis.ConnectionError, redis.TimeoutError) as e:
        logger.warning(f"Redis invalidation failed: {e}")


def health_check() -> bool:
    """Check if Redis is reachable."""
    try:
        return _client.ping()
    except Exception:
        return False
