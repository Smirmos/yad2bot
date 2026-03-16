from __future__ import annotations

import logging
import random
from typing import Any
from urllib.parse import urlencode

import httpx

from bot.config import Config

logger = logging.getLogger(__name__)

API_URL = "https://gw.yad2.co.il/recommendations/items/realestate"
YAD2_SEARCH_URL = "https://www.yad2.co.il/realestate/rent"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
]


def _build_headers() -> dict[str, str]:
    ua = random.choice(USER_AGENTS)
    is_chrome = "Chrome" in ua
    return {
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.yad2.co.il/",
        "Origin": "https://www.yad2.co.il",
        **(
            {
                "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
            }
            if is_chrome
            else {}
        ),
    }


class Yad2Scraper:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._playwright_available: bool | None = None

    async def fetch_listings(self) -> list[dict[str, Any]]:
        """Try httpx first, fall back to Playwright on 403/failure."""
        listings = await self._fetch_via_httpx()
        if listings:
            return listings

        logger.warning("httpx fetch failed or returned 0 results, falling back to Playwright")
        return await self._fetch_via_playwright()

    # ── httpx (lightweight) ──────────────────────────────────────────

    async def _fetch_via_httpx(self) -> list[dict[str, Any]]:
        params = {
            "type": "home",
            "count": "40",
            "categoryId": "2",
            "roomValues": ",".join(self.config.rooms),
            "cityValues": self.config.city_id,
            "subCategoriesIds": "2",
        }

        try:
            headers = _build_headers()
            async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=True) as client:
                resp = await client.get(API_URL, params=params)
                logger.info("httpx Yad2 API status: %d", resp.status_code)

                if resp.status_code == 403:
                    logger.warning("Got 403 — Yad2 blocked the request")
                    return []

                if resp.status_code != 200:
                    logger.warning("Yad2 API returned %d: %s", resp.status_code, resp.text[:500])
                    return []

                data = resp.json()
                return self._parse_api_response(data)

        except Exception:
            logger.exception("httpx request failed")
            return []

    # ── Playwright (headless browser fallback) ───────────────────────

    async def _fetch_via_playwright(self) -> list[dict[str, Any]]:
        if self._playwright_available is False:
            logger.warning("Playwright previously failed to import, skipping")
            return []

        try:
            from playwright.async_api import async_playwright
            self._playwright_available = True
        except ImportError:
            logger.error("Playwright is not installed — run: pip install playwright && playwright install chromium")
            self._playwright_available = False
            return []

        params = {
            "city": self.config.city_id,
            "maxPrice": str(self.config.max_price),
            "rooms": f"{min(self.config.rooms)}-{max(self.config.rooms)}",
        }
        if self.config.min_price:
            params["minPrice"] = str(self.config.min_price)

        search_url = f"{YAD2_SEARCH_URL}?{urlencode(params)}"
        logger.info("Playwright: navigating to %s", search_url)

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = await browser.new_context(
                    locale="he-IL",
                    user_agent=random.choice(USER_AGENTS),
                    viewport={"width": 1920, "height": 1080},
                )
                page = await context.new_page()

                api_data: dict | None = None

                async def capture_api_response(response):
                    nonlocal api_data
                    url = response.url
                    if "recommendations/items/realestate" in url or "feed-search" in url:
                        try:
                            body = await response.json()
                            api_data = body
                            logger.info("Playwright: captured API response from %s", url)
                        except Exception:
                            pass

                page.on("response", capture_api_response)

                await page.goto(search_url, wait_until="networkidle", timeout=60_000)
                # Give extra time for XHR calls
                await page.wait_for_timeout(5_000)

                await browser.close()

            if api_data:
                return self._parse_api_response(api_data)

            logger.warning("Playwright: no API response captured, parsing page HTML")
            return []

        except Exception:
            logger.exception("Playwright scraping failed")
            return []

    # ── Response parsing ─────────────────────────────────────────────

    def _parse_api_response(self, data: dict) -> list[dict[str, Any]]:
        """Parse the recommendations API response.

        Response structure: { "data": [ [item, item, ...] ], "message": "" }
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
