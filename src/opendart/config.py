"""Configuration management for OpenDART ETL."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def find_dotenv() -> Path | None:
    """Find .env file by walking up from current directory."""
    current = Path.cwd()
    while current != current.parent:
        env_file = current / ".env"
        if env_file.exists():
            return env_file
        current = current.parent
    return None


# Load .env file
env_path = find_dotenv()
if env_path:
    load_dotenv(env_path)


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    dart_api_key: str
    database_url: str

    # Rate limiting
    request_delay: float = 0.15  # seconds between API requests
    rate_limit_pause: int = 3600  # seconds to pause on rate limit (1 hour)

    # Backfill settings
    backfill_start_year: int = 2015

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        dart_api_key = os.getenv("DART_API_KEY")
        database_url = os.getenv("DATABASE_URL")

        if not dart_api_key:
            raise ValueError("DART_API_KEY environment variable is required")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")

        return cls(
            dart_api_key=dart_api_key,
            database_url=database_url,
        )


def get_settings() -> Settings:
    """Get application settings (cached)."""
    return Settings.from_env()


def get_config() -> dict[str, str | None]:
    """Get all config values as a dict (for optional settings like SMTP).

    Returns environment variables directly, useful for optional config
    that may not be set.
    """
    return {
        "DART_API_KEY": os.getenv("DART_API_KEY"),
        "DATABASE_URL": os.getenv("DATABASE_URL"),
        "SMTP_HOST": os.getenv("SMTP_HOST"),
        "SMTP_PORT": os.getenv("SMTP_PORT", "587"),
        "SMTP_USER": os.getenv("SMTP_USER"),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD"),
        "NOTIFICATION_EMAIL": os.getenv("NOTIFICATION_EMAIL"),
    }
