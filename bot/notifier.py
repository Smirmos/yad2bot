import asyncio
import logging
from typing import Any

from telegram import Bot
from telegram.error import RetryAfter

from bot.config import Config

logger = logging.getLogger(__name__)

MESSAGE_DELAY = 3  # seconds between messages


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str) -> None:
        self.bot = Bot(token=token)
        self.chat_id = chat_id

    async def _send(self, text: str, disable_preview: bool = True) -> None:
        """Send a message with retry on 429 rate limit."""
        while True:
            try:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=disable_preview,
                )
                return
            except RetryAfter as e:
                wait = e.retry_after + 1
                logger.warning("Telegram 429 — waiting %d seconds", wait)
                await asyncio.sleep(wait)

    async def send_startup_message(self, config: Config) -> None:
        filters = []
        if config.balcony:
            filters.append("balcony / מרפסת")
        if config.parking:
            filters.append("parking / חניה")
        if config.elevator:
            filters.append("elevator / מעלית")
        if config.mamad:
            filters.append("mamad / ממ\"ד")

        lines = [
            "🤖 <b>Yad2Bot started</b>",
            f"🏙 Cities: {', '.join(config.cities)}",
        ]
        if config.area:
            lines.append(f"📍 Area: {config.area}")
        if config.top_area:
            lines.append(f"📍 Top area: {config.top_area}")
        if config.region:
            lines.append(f"📍 Region: {', '.join(config.region)}")
        lines.extend([
            f"🛏 Rooms: {', '.join(config.rooms)}",
            f"💰 Price: ₪{config.min_price}–₪{config.max_price}",
            f"⏱ Interval: {config.check_interval_minutes}min",
        ])
        if filters:
            lines.append(f"🔎 Filters: {', '.join(filters)}")
        else:
            lines.append("🔎 Filters: none")

        await self._send("\n".join(lines))

    async def send_listing(self, listing: dict[str, Any]) -> None:
        message = self._format_message(listing)
        await self._send(message, disable_preview=False)
        logger.info("Sent listing %s to Telegram", listing["id"])
        await asyncio.sleep(MESSAGE_DELAY)

    @staticmethod
    def _format_message(listing: dict[str, Any]) -> str:
        price = listing.get("price", "?")
        rooms = listing.get("rooms", "?")
        city = listing.get("city", "")
        neighborhood = listing.get("neighborhood", "")
        street = listing.get("street", "")
        floor = listing.get("floor", "")
        sqm = listing.get("square_meters", "")
        link = listing.get("link", "")

        lines = [f"🏠 <b>דירה להשכרה</b>"]

        if price:
            lines.append(f"💰 מחיר: ₪{price}")
        if rooms:
            lines.append(f"🛏 חדרים: {rooms}")
        if city:
            lines.append(f"🏙 עיר: {city}")
        if neighborhood:
            lines.append(f"📍 שכונה: {neighborhood}")
        if street:
            lines.append(f"🏡 רחוב: {street}")
        if floor:
            lines.append(f"🏢 קומה: {floor}")
        if sqm:
            lines.append(f"📐 מ״ר: {sqm}")
        if link:
            lines.append(f"\n🔗 <a href=\"{link}\">צפה במודעה</a>")

        return "\n".join(lines)
