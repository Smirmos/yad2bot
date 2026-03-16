from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    telegram_token: str
    telegram_chat_id: str
    max_price: int = 9000
    min_price: int = 0
    rooms: list[str] = field(default_factory=lambda: ["3", "3.5", "4"])
    city_id: str = "5000"
    check_interval_minutes: int = 15
    db_path: str = "seen_listings.db"
    scraper_api_key: str = ""

    @classmethod
    def from_env(cls) -> Config:
        rooms_raw = os.getenv("ROOMS", "3,3.5,4")
        return cls(
            telegram_token=os.environ["TELEGRAM_TOKEN"],
            telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
            max_price=int(os.getenv("MAX_PRICE", "9000")),
            min_price=int(os.getenv("MIN_PRICE", "0")),
            rooms=[r.strip() for r in rooms_raw.split(",")],
            city_id=os.getenv("CITY_ID", "5000"),
            check_interval_minutes=int(os.getenv("CHECK_INTERVAL_MINUTES", "15")),
            db_path=os.getenv("DB_PATH", "seen_listings.db"),
            scraper_api_key=os.getenv("SCRAPER_API_KEY", ""),
        )
