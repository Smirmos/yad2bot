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
    area: str = ""
    region: list[str] = field(default_factory=list)
    check_interval_minutes: int = 15
    db_path: str = "seen_listings.db"
    scraper_api_key: str = ""
    balcony: bool = False
    parking: bool = False
    elevator: bool = False
    mamad: bool = False

    @classmethod
    def from_env(cls) -> Config:
        rooms_raw = os.getenv("ROOMS", "3,3.5,4")
        region_raw = os.getenv("REGION", "")
        region = [r.strip() for r in region_raw.split(",") if r.strip()]
        return cls(
            telegram_token=os.environ["TELEGRAM_TOKEN"],
            telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
            max_price=int(os.getenv("MAX_PRICE", "9000")),
            min_price=int(os.getenv("MIN_PRICE", "0")),
            rooms=[r.strip() for r in rooms_raw.split(",")],
            city_id=os.getenv("CITY_ID", "5000"),
            area=os.getenv("AREA", ""),
            region=region,
            check_interval_minutes=int(os.getenv("CHECK_INTERVAL_MINUTES", "15")),
            db_path=os.getenv("DB_PATH", "seen_listings.db"),
            scraper_api_key=os.environ["SCRAPER_API_KEY"],
            balcony=os.getenv("FILTER_BALCONY", "0") == "1",
            parking=os.getenv("FILTER_PARKING", "0") == "1",
            elevator=os.getenv("FILTER_ELEVATOR", "0") == "1",
            mamad=os.getenv("FILTER_MAMAD", "0") == "1",
        )

    def active_filters_summary(self) -> str:
        """Human-readable summary of active search filters."""
        parts = [
            f"city={self.city_id}",
            f"rooms={','.join(self.rooms)}",
            f"price={self.min_price}-{self.max_price}",
        ]
        if self.area:
            parts.append(f"area={self.area}")
        if self.region:
            parts.append(f"region={','.join(self.region)}")
        filters = []
        if self.balcony:
            filters.append("balcony")
        if self.parking:
            filters.append("parking")
        if self.elevator:
            filters.append("elevator")
        if self.mamad:
            filters.append("mamad")
        if filters:
            parts.append(f"filters={','.join(filters)}")
        return " | ".join(parts)
