from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Domain Sales Scraper API"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 7852
    api_prefix: str = "/api/v1"

    request_timeout: float = 30.0
    cache_ttl_seconds: int = 3600
    max_concurrent_requests: int = 5
    user_agent: str = (
        "DomainSalesAPI/1.0 (+https://github.com/domain-sales-api; research use)"
    )

    dropdax_base_url: str = "https://dropdax.com"
    dropdax_category_path: str = "/blog/category/daily-market-reports/"


@lru_cache
def get_settings() -> Settings:
    return Settings()
