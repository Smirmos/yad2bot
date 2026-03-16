import logging

import redis

logger = logging.getLogger(__name__)

SEEN_KEY = "seen_listings"
TTL_DAYS = 30


class Database:
    def __init__(self, redis_url: str) -> None:
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.r.ping()
        count = self.r.scard(SEEN_KEY)
        logger.info("Connected to Redis — %d seen listings stored", count)

    def seen_count(self) -> int:
        return self.r.scard(SEEN_KEY)

    def is_seen(self, listing_id: str) -> bool:
        result = self.r.sismember(SEEN_KEY, str(listing_id))
        if result:
            logger.debug("Listing %s already seen, skipping", listing_id)
        return bool(result)

    def mark_seen(self, listing_id: str) -> None:
        self.r.sadd(SEEN_KEY, str(listing_id))
        self.r.expire(SEEN_KEY, TTL_DAYS * 86400)
        logger.debug("Marked listing %s as seen", listing_id)

    def close(self) -> None:
        self.r.close()
