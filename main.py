import asyncio
import logging
import os
import signal
import sys

from dotenv import load_dotenv

from bot.config import Config
from bot.database import Database
from bot.scraper import Yad2Scraper
from bot.notifier import TelegramNotifier

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def poll_once(scraper: Yad2Scraper, db: Database, notifier: TelegramNotifier) -> None:
    """Run a single poll cycle: fetch listings, filter new ones, notify."""
    try:
        listings = await scraper.fetch_listings()
        logger.info("Fetched %d listings from Yad2", len(listings))

        new_listings = [l for l in listings if not db.is_seen(l["id"])]
        logger.info("Found %d new listings", len(new_listings))

        for listing in new_listings:
            try:
                await notifier.send_listing(listing)
                db.mark_seen(listing["id"])
            except Exception:
                logger.exception("Failed to send listing %s", listing.get("id"))

    except Exception:
        logger.exception("Error during poll cycle")


async def main() -> None:
    config = Config.from_env()
    db = Database(config.redis_url)
    scraper = Yad2Scraper(config)
    notifier = TelegramNotifier(config.telegram_token, config.telegram_chat_id)

    stop_event = asyncio.Event()

    def handle_signal(*_):
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_event_loop().add_signal_handler(sig, handle_signal)

    logger.info(
        "Yad2Bot started — polling every %d minutes | %s",
        config.check_interval_minutes,
        config.active_filters_summary(),
    )

    try:
        await notifier.send_startup_message(config)
    except Exception:
        logger.exception("Failed to send startup message to Telegram")

    while not stop_event.is_set():
        await poll_once(scraper, db, notifier)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=config.check_interval_minutes * 60)
        except asyncio.TimeoutError:
            pass

    logger.info("Yad2Bot stopped")
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
