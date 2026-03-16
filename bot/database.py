import logging

import redis

logger = logging.getLogger(__name__)

SEEN_KEY = "seen_listings"
TTL_DAYS = 30


class Database:
    def __init__(self, redis_url: str) -> None:
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.r.ping()
        logger.info("Connected to Redis")

    def is_seen(self, listing_id: str) -> bool:
        return self.r.sismember(SEEN_KEY, str(listing_id))

    def mark_seen(self, listing_id: str) -> None:
        self.r.sadd(SEEN_KEY, str(listing_id))
        # Refresh TTL on every write so the set stays alive while the bot runs
        self.r.expire(SEEN_KEY, TTL_DAYS * 86400)

    def close(self) -> None:
        self.r.close()
