import asyncio
import logging
import os
import signal
import sys

from dotenv import load_dotenv

from bot.cities import CITIES, CityConfig
from bot.config import Config
from bot.database import Database
from bot.notifier import TelegramNotifier
from bot.scraper import Yad2Scraper

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def poll_city(
    city: CityConfig,
    scraper: Yad2Scraper,
    db: Database,
    notifier: TelegramNotifier,
) -> None:
    slug = city.slug
    logger.info("--- Checking %s — %d seen IDs ---", city.name, db.seen_count(slug))

    listings = scraper.fetch_city(city)
    logger.info("[%s] Fetched %d listings", city.name, len(listings))

    new_count = 0
    skip_count = 0
    for listing in listings:
        lid = listing["id"]
        if db.is_seen(slug, lid):
            skip_count += 1
            continue
        new_count += 1
        try:
            await notifier.send_listing(listing, city.name)
            db.mark_seen(slug, lid)
            logger.info("Sent %s (%s, ₪%s)", lid, city.name, listing.get("price"))
        except Exception:
            logger.exception("Failed to send listing %s", lid)

    logger.info("[%s] New: %d | Skipped: %d", city.name, new_count, skip_count)


async def main() -> None:
    config = Config.from_env()
    db = Database(config.redis_url)
    scraper = Yad2Scraper(config)
    chat_id = config.telegram_chat_id

    # Build per-city notifiers (skip cities without a token)
    city_notifiers: list[tuple[CityConfig, TelegramNotifier]] = []
    for city in CITIES:
        token = os.getenv(city.token_env, "")
        if not token:
            logger.warning("No token for %s (%s), skipping", city.name, city.token_env)
            continue
        notifier = TelegramNotifier(token, chat_id)
        city_notifiers.append((city, notifier))
        logger.info("Loaded %s (topArea=%d area=%d city=%s)", city.name, city.top_area, city.area, city.city_id)

    if not city_notifiers:
        logger.error("No city tokens configured, exiting")
        return

    stop_event = asyncio.Event()

    def handle_signal(*_):
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_event_loop().add_signal_handler(sig, handle_signal)

    logger.info(
        "Yad2Bot started — %d cities, polling every %d minutes, price %d-%d, rooms %s",
        len(city_notifiers),
        config.check_interval_minutes,
        config.min_price,
        config.max_price,
        ",".join(config.rooms),
    )

    # Send startup messages
    for city, notifier in city_notifiers:
        try:
            await notifier.send_startup(city.name)
        except Exception:
            logger.exception("Failed to send startup for %s", city.name)

    # Main loop
    while not stop_event.is_set():
        for city, notifier in city_notifiers:
            try:
                await poll_city(city, scraper, db, notifier)
            except Exception:
                logger.exception("Error polling %s", city.name)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=config.check_interval_minutes * 60)
        except asyncio.TimeoutError:
            pass

    logger.info("Yad2Bot stopped")
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
