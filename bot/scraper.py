from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import requests

from bot.config import Config

logger = logging.getLogger(__name__)

SCRAPER_API_URL = "http://api.scraperapi.com"

# Primary: recommendations API (verified working locally)
YAD2_RECOMMENDATIONS_URL = "https://gw.yad2.co.il/recommendations/items/realestate"
# Fallback: realestate/rent endpoint
YAD2_REALESTATE_URL = "https://gw.yad2.co.il/realestate/rent"

HEADERS = {
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
}


class Yad2Scraper:
    def __init__(self, config: Config) -> None:
        self.config = config

    async def fetch_listings(self) -> list[dict[str, Any]]:
        """Fetch Yad2 listings via ScraperAPI, trying two endpoints."""
        # Try primary endpoint
        listings = self._fetch(self._build_recommendations_url())
        if listings:
            return listings

        # Try fallback endpoint
        logger.warning("Primary endpoint returned 0 results, trying fallback")
        listings = self._fetch(self._build_realestate_url())
        if listings:
            return listings

        logger.error("Both Yad2 endpoints failed to return listings")
        return []

    def _build_recommendations_url(self) -> str:
        params = {
            "type": "home",
            "count": "40",
            "categoryId": "2",
            "roomValues": ",".join(self.config.rooms),
            "cityValues": self.config.city_id,
            "subCategoriesIds": "2",
        }
        return f"{YAD2_RECOMMENDATIONS_URL}?{urlencode(params)}"

    def _build_realestate_url(self) -> str:
        params = {
            "cityValues": self.config.city_id,
            "maxPrice": str(self.config.max_price),
            "roomValues": ",".join(self.config.rooms),
        }
        if self.config.min_price:
            params["minPrice"] = str(self.config.min_price)
        return f"{YAD2_REALESTATE_URL}?{urlencode(params)}"

    def _fetch(self, target_url: str) -> list[dict[str, Any]]:
        try:
            logger.info("Fetching Yad2 via ScraperAPI: %s", target_url)
            resp = requests.get(
                SCRAPER_API_URL,
                params={
                    "api_key": self.config.scraper_api_key,
                    "url": target_url,
                    "render": "false",
                    "country_code": "il",
                },
                headers=HEADERS,
                timeout=60,
            )
            logger.info("ScraperAPI status: %d", resp.status_code)

            if resp.status_code != 200:
                logger.warning("ScraperAPI returned %d: %s", resp.status_code, resp.text[:500])
                return []

            data = resp.json()
            return self._parse_api_response(data)

        except Exception:
            logger.exception("ScraperAPI request failed")
            return []

    # ── Response parsing ─────────────────────────────────────────────

    def _parse_api_response(self, data: dict) -> list[dict[str, Any]]:
        """Parse Yad2 API response (handles multiple response formats)."""
        raw_data = data.get("data", {})

        items: list[dict] = []

        # Format 1: feed-search style — data.feed.feed_items
        if isinstance(raw_data, dict):
            feed = raw_data.get("feed", {})
            items = feed.get("feed_items", [])

        # Format 2: recommendations style — data is list of lists
        if not items and isinstance(raw_data, list):
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

        logger.info("Parsed %d listings from Yad2 response", len(listings))
        return listings

    def _matches_price(self, listing: dict[str, Any]) -> bool:
        try:
            price = int(listing["price"])
        except (ValueError, TypeError):
            return True

        if self.config.max_price and price > self.config.max_price:
            return False
        if self.config.min_price and price < self.config.min_price:
            return False
        return True

    def _normalize(self, item: dict) -> dict[str, Any] | None:
        token = item.get("token") or item.get("id")
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
