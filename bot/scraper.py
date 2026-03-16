from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any
from urllib.parse import urlencode

import requests

from bot.config import Config

logger = logging.getLogger(__name__)

ZYTE_API_URL = "https://api.zyte.com/v1/extract"

YAD2_SEARCH_URL = "https://www.yad2.co.il/realestate/rent"


class Yad2Scraper:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._zyte_auth = base64.b64encode(
            f"{config.zyte_api_key}:".encode()
        ).decode()

    async def fetch_listings(self) -> list[dict[str, Any]]:
        """Fetch Yad2 listings via Zyte browser rendering."""
        url = self._build_search_url()
        return self._fetch_browser(url)

    # ── URL builder ──────────────────────────────────────────────────

    def _build_search_url(self) -> str:
        params: dict[str, str] = {
            "cityValues": self.config.city_id,
            "maxPrice": str(self.config.max_price),
            "roomValues": ",".join(self.config.rooms),
        }
        if self.config.min_price:
            params["minPrice"] = str(self.config.min_price)
        if self.config.area:
            params["area"] = self.config.area
        if self.config.region:
            params["region"] = ",".join(self.config.region)
        if self.config.balcony:
            params["balcony"] = "1"
        if self.config.parking:
            params["parking"] = "1"
        if self.config.elevator:
            params["elevator"] = "1"
        if self.config.mamad:
            params["shelter"] = "1"
        return f"{YAD2_SEARCH_URL}?{urlencode(params)}"

    # ── Zyte browser fetch ───────────────────────────────────────────

    def _fetch_browser(self, target_url: str) -> list[dict[str, Any]]:
        try:
            logger.info("Fetching Yad2 via Zyte browserHtml: %s", target_url)

            resp = requests.post(
                ZYTE_API_URL,
                headers={
                    "Authorization": f"Basic {self._zyte_auth}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": target_url,
                    "browserHtml": True,
                },
                timeout=90,
            )
            logger.info("Zyte API status: %d", resp.status_code)

            if resp.status_code != 200:
                logger.warning("Zyte API returned %d: %s", resp.status_code, resp.text[:500])
                return []

            zyte_data = resp.json()
            html = zyte_data.get("browserHtml", "")
            if not html:
                logger.warning("Zyte API returned empty browserHtml")
                return []

            logger.info("Got %d chars of HTML", len(html))
            return self._parse_next_data(html)

        except Exception:
            logger.exception("Zyte API request failed")
            return []

    # ── HTML / __NEXT_DATA__ parsing ─────────────────────────────────

    # Feed categories we want (real listings, not boosted ads)
    FEED_KEYS = ("private", "agency")

    def _parse_next_data(self, html: str) -> list[dict[str, Any]]:
        match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        if not match:
            logger.warning("__NEXT_DATA__ not found in HTML")
            logger.debug("HTML preview: %s", html[:500])
            return []

        try:
            next_data = json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.exception("Failed to parse __NEXT_DATA__ JSON")
            logger.warning("Raw __NEXT_DATA__ preview: %s", match.group(1)[:500])
            return []

        page_props = next_data.get("props", {}).get("pageProps", {})
        feed = page_props.get("feed", {})

        if not isinstance(feed, dict):
            logger.warning("pageProps['feed'] is not a dict: %s", type(feed).__name__)
            return []

        # Log feed structure
        for key, val in feed.items():
            count = len(val) if isinstance(val, list) else "N/A"
            logger.info("  feed[%s]: %s items", key, count)

        # Collect items from private + agency only
        items: list[dict] = []
        for key in self.FEED_KEYS:
            group = feed.get(key, [])
            if isinstance(group, list):
                items.extend(group)
                logger.info("feed[%s]: %d items", key, len(group))

        if not items:
            logger.warning("No items in feed[private/agency]")
            return []

        # Log first item's full structure for field mapping
        logger.info("Sample listing keys: %s", list(items[0].keys()))
        logger.info("Sample listing: %s", json.dumps(items[0], ensure_ascii=False, default=str)[:1000])

        listings = []
        for item in items:
            if not isinstance(item, dict):
                continue
            listing = self._normalize(item)
            if listing and self._matches_price(listing):
                listings.append(listing)

        logger.info("Parsed %d listings from __NEXT_DATA__", len(listings))
        return listings

    # ── Listing normalization ────────────────────────────────────────

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
        token = item.get("token") or item.get("id") or item.get("orderId")
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
