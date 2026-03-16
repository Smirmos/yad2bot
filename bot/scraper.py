from __future__ import annotations

import logging
from typing import Any

import httpx

from bot.config import Config

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.yad2.co.il/",
    "Origin": "https://www.yad2.co.il",
}

API_URL = "https://gw.yad2.co.il/recommendations/items/realestate"


class Yad2Scraper:
    def __init__(self, config: Config) -> None:
        self.config = config

    async def fetch_listings(self) -> list[dict[str, Any]]:
        """Fetch rental listings from the Yad2 recommendations API."""
        params = {
            "type": "home",
            "count": "40",
            "categoryId": "2",
            "roomValues": ",".join(self.config.rooms),
            "cityValues": self.config.city_id,
            "subCategoriesIds": "2",
        }

        try:
            async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
                resp = await client.get(API_URL, params=params)
                logger.info("Yad2 API status: %d", resp.status_code)

                if resp.status_code != 200:
                    logger.warning("Yad2 API returned %d: %s", resp.status_code, resp.text[:500])
                    return []

                data = resp.json()
                return self._parse_response(data)

        except Exception:
            logger.exception("Failed to fetch listings from Yad2")
            return []

    def _parse_response(self, data: dict) -> list[dict[str, Any]]:
        """Parse the recommendations API response.

        Response structure: { "data": [ [item, item, ...] ], "message": "" }
        Each item has: token, price, additionalDetails, address, metaData, etc.
        """
        raw_data = data.get("data", [])

        # data is a list of lists — flatten
        items: list[dict] = []
        if isinstance(raw_data, list):
            for group in raw_data:
                if isinstance(group, list):
                    items.extend(group)
                elif isinstance(group, dict):
                    items.append(group)

        listings = []
        for item in items:
            listing = self._normalize(item)
            if listing and self._matches_price(listing):
                listings.append(listing)

        return listings

    def _matches_price(self, listing: dict[str, Any]) -> bool:
        """Filter by configured price range."""
        try:
            price = int(listing["price"])
        except (ValueError, TypeError):
            return True  # Include listings with unknown price

        if self.config.max_price and price > self.config.max_price:
            return False
        if self.config.min_price and price < self.config.min_price:
            return False
        return True

    def _normalize(self, item: dict) -> dict[str, Any] | None:
        """Normalize a raw API item into a clean listing dict."""
        token = item.get("token")
        if not token:
            return None

        address = item.get("address", {})
        details = item.get("additionalDetails", {})
        meta = item.get("metaData", {})

        neighborhood = address.get("neighborhood", {}).get("text", "")
        street = address.get("street", {}).get("text", "")
        city = address.get("city", {}).get("text", "")
        floor = address.get("house", {}).get("floor", "")
        rooms = details.get("roomsCount", "")
        sqm = details.get("squareMeter", "")
        price = item.get("price", "")
        description = meta.get("description", "")

        return {
            "id": str(token),
            "price": str(price),
            "rooms": str(rooms),
            "neighborhood": neighborhood,
            "street": street,
            "city": city,
            "floor": str(floor) if floor else "",
            "square_meters": str(sqm) if sqm else "",
            "description": description,
            "link": f"https://www.yad2.co.il/item/{token}",
        }
