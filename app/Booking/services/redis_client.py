"""
Redis Client — Booking timer management using Redis TTL keys
"""
import asyncio
import os
import logging

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
BOOKING_TIMER_TTL = int(os.getenv("BOOKING_TIMER_TTL", "120"))  # 2 minutes

# Global async Redis connection
_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get or create an async Redis connection."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis


async def close_redis():
    """Close the Redis connection on shutdown."""
    global _redis
    if _redis:
        await _redis.close()
        _redis = None


# ─────────────── Booking Timer Operations ───────────────

async def set_booking_timer(booking_id: str, ttl_seconds: int = BOOKING_TIMER_TTL) -> bool:
    """
    Set a Redis key with TTL for the booking accept window.
    Key format: booking:timer:<booking_id>
    """
    r = await get_redis()
    key = f"booking:timer:{booking_id}"
    await r.set(key, "pending", ex=ttl_seconds)
    logger.info(f"Booking timer set: {key} (TTL={ttl_seconds}s)")
    return True


async def cancel_booking_timer(booking_id: str) -> bool:
    """Cancel the booking timer (artist responded in time)."""
    r = await get_redis()
    key = f"booking:timer:{booking_id}"
    result = await r.delete(key)
    logger.info(f"Booking timer cancelled: {key} (deleted={result})")
    return result > 0


async def is_booking_active(booking_id: str) -> bool:
    """Check if the booking timer is still active."""
    r = await get_redis()
    key = f"booking:timer:{booking_id}"
    return await r.exists(key) > 0


async def get_booking_ttl(booking_id: str) -> int:
    """Get remaining TTL in seconds for a booking timer. Returns -2 if key doesn't exist."""
    r = await get_redis()
    key = f"booking:timer:{booking_id}"
    return await r.ttl(key)


# ─────────────── Keyspace Notification Listener ───────────────

async def start_expiry_listener(on_expired_callback):
    """
    Listen for Redis keyspace expiry events on booking timer keys.
    Calls `on_expired_callback(booking_id)` when a timer expires.
    
    Requires Redis config: notify-keyspace-events Ex
    """
    r = await get_redis()

    # Enable keyspace notifications for expired events
    await r.config_set("notify-keyspace-events", "Ex")

    pubsub = r.pubsub()
    await pubsub.psubscribe("__keyevent@0__:expired")

    logger.info("Redis expiry listener started")

    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            expired_key = message["data"]
            if isinstance(expired_key, bytes):
                expired_key = expired_key.decode()

            # Only handle our booking timer keys
            if expired_key.startswith("booking:timer:"):
                booking_id = expired_key.replace("booking:timer:", "")
                logger.info(f"Booking timer expired: {booking_id}")
                try:
                    await on_expired_callback(booking_id)
                except Exception as e:
                    logger.error(f"Error handling booking expiry for {booking_id}: {e}")
