from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CityConfig:
    name: str
    top_area: int
    area: int
    city_id: int | None
    token_env: str
    slug: str = ""  # ASCII key for Redis, derived from token_env


CITIES: list[CityConfig] = [
    CityConfig(
        name="רמת גן",
        top_area=2,
        area=3,
        city_id=8600,
        token_env="TELEGRAM_TOKEN_RAMAT_GAN",
        slug="ramat_gan",
    ),
    CityConfig(
        name="הרצליה",
        top_area=19,
        area=18,
        city_id=6400,
        token_env="TELEGRAM_TOKEN_HERZLIYA",
        slug="herzliya",
    ),
    CityConfig(
        name="רעננה",
        top_area=19,
        area=42,
        city_id=8700,
        token_env="TELEGRAM_TOKEN_RAANANA",
        slug="raanana",
    ),
    CityConfig(
        name="פתח תקווה",
        top_area=2,
        area=4,
        city_id=7900,
        token_env="TELEGRAM_TOKEN_PETAH_TIKVA",
        slug="petah_tikva",
    ),
    CityConfig(
        name="הוד השרון",
        top_area=19,
        area=54,
        city_id=None,
        token_env="TELEGRAM_TOKEN_HOD_HASHARON",
        slug="hod_hasharon",
    ),
]
