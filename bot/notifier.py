import asyncio
import logging
from typing import Any

from telegram import Bot
from telegram.error import RetryAfter

logger = logging.getLogger(__name__)

MESSAGE_DELAY = 3


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str) -> None:
        self.bot = Bot(token=token)
        self.chat_id = chat_id

    async def _send(self, text: str, disable_preview: bool = True) -> None:
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

    async def send_startup(self, city_name: str) -> None:
        await self._send(f"🤖 <b>Yad2Bot</b> active for <b>{city_name}</b>")

    async def send_listing(self, listing: dict[str, Any], city_name: str) -> None:
        message = self._format_message(listing, city_name)
        await self._send(message, disable_preview=False)
        logger.info("Sent listing %s to Telegram", listing["id"])
        await asyncio.sleep(MESSAGE_DELAY)

    @staticmethod
    def _format_message(listing: dict[str, Any], city_name: str) -> str:
        price = listing.get("price", "?")
        rooms = listing.get("rooms", "?")
        neighborhood = listing.get("neighborhood", "")
        street = listing.get("street", "")
        floor = listing.get("floor", "")
        sqm = listing.get("square_meters", "")
        link = listing.get("link", "")

        lines = [
            f"🏠 <b>דירה להשכרה — {city_name}</b>",
        ]
        if price:
            lines.append(f"💰 מחיר: ₪{price}")
        if rooms:
            lines.append(f"🛏 חדרים: {rooms}")
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
