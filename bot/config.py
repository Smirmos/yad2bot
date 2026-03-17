from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    telegram_chat_id: str
    max_price: int = 9000
    min_price: int = 0
    rooms: list[str] = field(default_factory=lambda: ["3", "3.5", "4"])
    check_interval_minutes: int = 300
    redis_url: str = ""
    zyte_api_key: str = ""
    balcony: bool = False
    parking: bool = False
    elevator: bool = False
    mamad: bool = False

    @classmethod
    def from_env(cls) -> Config:
        rooms_raw = os.getenv("ROOMS", "3,3.5,4")
        return cls(
            telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
            max_price=int(os.getenv("MAX_PRICE", "9000")),
            min_price=int(os.getenv("MIN_PRICE", "0")),
            rooms=[r.strip() for r in rooms_raw.split(",")],
            check_interval_minutes=int(os.getenv("CHECK_INTERVAL_MINUTES", "300")),
            redis_url=os.environ["REDIS_URL"],
            zyte_api_key=os.environ["ZYTE_API_KEY"],
            balcony=os.getenv("FILTER_BALCONY", "0") == "1",
            parking=os.getenv("FILTER_PARKING", "0") == "1",
            elevator=os.getenv("FILTER_ELEVATOR", "0") == "1",
            mamad=os.getenv("FILTER_MAMAD", "0") == "1",
        )
