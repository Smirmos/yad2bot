from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any
from urllib.parse import urlencode

import requests

from bot.cities import CityConfig
from bot.config import Config

logger = logging.getLogger(__name__)

ZYTE_API_URL = "https://api.zyte.com/v1/extract"
YAD2_SEARCH_URL = "https://www.yad2.co.il/realestate/rent"

MAX_PAGES = 10
FEED_KEYS = ("private", "agency")


class Yad2Scraper:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._zyte_auth = base64.b64encode(
            f"{config.zyte_api_key}:".encode()
        ).decode()

    def fetch_city(self, city: CityConfig) -> list[dict[str, Any]]:
        """Fetch all pages for a single city."""
        all_items: list[dict[str, Any]] = []

        for page in range(1, MAX_PAGES + 1):
            url = self._build_url(city, page)
            logger.info("[%s page=%d] %s", city.name, page, url)

            items = self._fetch_page(url)
            if not items:
                logger.info("[%s page=%d] No items, stopping", city.name, page)
                break

            all_items.extend(items)
            logger.info("[%s page=%d] %d items (total: %d)", city.name, page, len(items), len(all_items))

            if len(items) < 15:
                break

        logger.info("[%s] Total: %d listings", city.name, len(all_items))
        return all_items

    # ── URL builder ──────────────────────────────────────────────────

    def _build_url(self, city: CityConfig, page: int = 1) -> str:
        params: dict[str, str] = {
            "topArea": str(city.top_area),
            "area": str(city.area),
        }
        if city.city_id is not None:
            params["city"] = str(city.city_id)
        params["maxPrice"] = str(self.config.max_price)
        if self.config.min_price:
            params["minPrice"] = str(self.config.min_price)
        params["roomValues"] = ",".join(self.config.rooms)
        if self.config.balcony:
            params["balcony"] = "1"
        if self.config.parking:
            params["parking"] = "1"
        if self.config.elevator:
            params["elevator"] = "1"
        if self.config.mamad:
            params["shelter"] = "1"
        if page > 1:
            params["page"] = str(page)
        return f"{YAD2_SEARCH_URL}?{urlencode(params)}"

    # ── Zyte browser fetch ───────────────────────────────────────────

    def _fetch_page(self, target_url: str) -> list[dict[str, Any]]:
        try:
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
            logger.info("Zyte status: %d", resp.status_code)

            if resp.status_code != 200:
                logger.warning("Zyte returned %d: %s", resp.status_code, resp.text[:500])
                return []

            html = resp.json().get("browserHtml", "")
            if not html:
                logger.warning("Zyte returned empty browserHtml")
                return []

            return self._parse_next_data(html)

        except Exception:
            logger.exception("Zyte request failed")
            return []

    # ── __NEXT_DATA__ parsing ────────────────────────────────────────

    def _parse_next_data(self, html: str) -> list[dict[str, Any]]:
        match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        if not match:
            logger.warning("__NEXT_DATA__ not found in HTML")
            return []

        try:
            next_data = json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.exception("Failed to parse __NEXT_DATA__ JSON")
            return []

        query = next_data.get("query", {})
        if query:
            logger.info("Yad2 resolved query: %s", query)

        page_props = next_data.get("props", {}).get("pageProps", {})
        feed = page_props.get("feed", {})

        if not isinstance(feed, dict):
            logger.warning("feed is not a dict: %s", type(feed).__name__)
            return []

        for key, val in feed.items():
            count = len(val) if isinstance(val, list) else "N/A"
            logger.info("  feed[%s]: %s", key, count)

        pagination = page_props.get("pagination", {})
        if pagination:
            logger.info("Pagination: %s", pagination)

        items: list[dict] = []
        for key in FEED_KEYS:
            group = feed.get(key, [])
            if isinstance(group, list):
                items.extend(group)

        if not items:
            logger.warning("No items in feed[private/agency]")
            return []

        listings = []
        for item in items:
            if not isinstance(item, dict):
                continue
            listing = self._normalize(item)
            if listing and self._matches_price(listing):
                listings.append(listing)

        logger.info("Parsed %d listings from page", len(listings))
        return listings

    # ── Normalization ────────────────────────────────────────────────

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

        return {
            "id": str(token),
            "price": str(item.get("price", "")),
            "rooms": str(details.get("roomsCount", "")),
            "neighborhood": address.get("neighborhood", {}).get("text", ""),
            "street": address.get("street", {}).get("text", ""),
            "city": address.get("city", {}).get("text", ""),
            "floor": str(address.get("house", {}).get("floor", "") or ""),
            "square_meters": str(details.get("squareMeter", "") or ""),
            "description": meta.get("description", ""),
            "link": f"https://www.yad2.co.il/item/{token}",
        }
