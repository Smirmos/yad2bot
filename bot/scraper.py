from __future__ import annotations

import base64
import json
import logging
import re
from collections import Counter
from typing import Any
from urllib.parse import urlencode

import requests

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

    async def fetch_listings(self) -> list[dict[str, Any]]:
        """Fetch listings: one request per city + optional area-based request."""
        all_listings: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        # One request per city
        for city_id in self.config.cities:
            city_listings = self._fetch_city(city_id=city_id)
            for listing in city_listings:
                if listing["id"] not in seen_ids:
                    seen_ids.add(listing["id"])
                    all_listings.append(listing)

        # Area-based request (e.g. הוד השרון with topArea/area, no cityValues)
        if self.config.area:
            area_listings = self._fetch_city(city_id=None)
            for listing in area_listings:
                if listing["id"] not in seen_ids:
                    seen_ids.add(listing["id"])
                    all_listings.append(listing)

        # Log city distribution
        city_counts = Counter(l["city"] for l in all_listings)
        for city, count in city_counts.most_common():
            logger.info("City '%s': %d listings", city, count)
        logger.info("Total unique listings: %d", len(all_listings))

        return all_listings

    # ── Per-city fetch with pagination ───────────────────────────────

    def _fetch_city(self, city_id: str | None) -> list[dict[str, Any]]:
        """Fetch all pages for a single city or area."""
        all_items: list[dict[str, Any]] = []
        label = f"city={city_id}" if city_id else f"area={self.config.area}"

        for page in range(1, MAX_PAGES + 1):
            url = self._build_search_url(city_id=city_id, page=page)
            logger.info("[%s page=%d] URL: %s", label, page, url)

            items = self._fetch_page(url)
            if not items:
                logger.info("[%s page=%d] No items, stopping pagination", label, page)
                break

            all_items.extend(items)
            logger.info("[%s page=%d] Got %d items (total so far: %d)", label, page, len(items), len(all_items))

            # If we got fewer than ~20 items, likely the last page
            if len(items) < 15:
                break

        logger.info("[%s] Total: %d listings across %d pages", label, len(all_items), min(page, MAX_PAGES))
        return all_items

    # ── URL builder ──────────────────────────────────────────────────

    def _build_search_url(self, city_id: str | None, page: int = 1) -> str:
        params: dict[str, str] = {
            "maxPrice": str(self.config.max_price),
            "roomValues": ",".join(self.config.rooms),
        }
        if city_id:
            params["cityValues"] = city_id
        else:
            # Area-only request (no city) — add area/topArea/region
            if self.config.area:
                params["area"] = self.config.area
            if self.config.top_area:
                params["topArea"] = self.config.top_area
            if self.config.region:
                params["region"] = ",".join(self.config.region)
        if self.config.min_price:
            params["minPrice"] = str(self.config.min_price)
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

    # ── Zyte browser fetch (single page) ─────────────────────────────

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

        # Check for pagination info
        pagination = page_props.get("pagination", {})
        if pagination:
            logger.info("Pagination info: %s", pagination)

        # Collect items from private + agency only
        items: list[dict] = []
        for key in FEED_KEYS:
            group = feed.get(key, [])
            if isinstance(group, list):
                items.extend(group)
                logger.info("feed[%s]: %d items", key, len(group))

        if not items:
            logger.warning("No items in feed[private/agency]")
            return []

        # Log sample listing on first page
        logger.info("Sample listing keys: %s", list(items[0].keys()))

        listings = []
        for item in items:
            if not isinstance(item, dict):
                continue
            listing = self._normalize(item)
            if listing and self._matches_price(listing):
                listings.append(listing)

        logger.info("Parsed %d listings from page", len(listings))
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
