import logging

import redis

logger = logging.getLogger(__name__)

TTL_DAYS = 30


class Database:
    def __init__(self, redis_url: str) -> None:
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.r.ping()
        logger.info("Connected to Redis")

    def _key(self, city_slug: str) -> str:
        return f"seen:{city_slug}"

    def seen_count(self, city_slug: str) -> int:
        return self.r.scard(self._key(city_slug))

    def is_seen(self, city_slug: str, listing_id: str) -> bool:
        return bool(self.r.sismember(self._key(city_slug), str(listing_id)))

    def mark_seen(self, city_slug: str, listing_id: str) -> None:
        key = self._key(city_slug)
        self.r.sadd(key, str(listing_id))
        self.r.expire(key, TTL_DAYS * 86400)

    def close(self) -> None:
        self.r.close()
