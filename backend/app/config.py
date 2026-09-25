"""Game constants and environment configuration.

Every value can be overridden with an environment variable of the same name
(or a line in ``backend/.env``). Services read rules from here so tests and
demos can change them without touching code.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Infrastructure
    DATABASE_URL: str = "sqlite:///./app.db"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    AUTO_SEED: bool = True
    DEMO_USERNAME: str = "arnav"
    APP_NAME: str = "Duolingo"

    # Game rules (§3.1)
    MAX_HEARTS: int = 5
    HEART_REGEN_MINUTES: int = 30
    HEART_REFILL_GEM_COST: int = 350
    BASE_LESSON_XP: int = 10
    PERFECT_BONUS_XP: int = 5
    PRACTICE_XP: int = 5
    DEFAULT_DAILY_GOAL_XP: int = 20
    APP_TIMEZONE: str = "Asia/Kolkata"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def resolved_database_url(self) -> str:
        """Resolve a relative SQLite path against backend/ instead of the CWD."""
        prefix = "sqlite:///"
        url = self.DATABASE_URL
        if url.startswith(prefix) and not url.startswith(prefix + "/") and ":memory:" not in url:
            path = Path(url[len(prefix):])
            if not path.is_absolute():
                return prefix + (BACKEND_DIR / path).resolve().as_posix()
        return url


settings = Settings()
