from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ENV_FILE), ".env"),
        extra="ignore",
    )

    nvidia_api_key: SecretStr = SecretStr("")
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_database: str = "querypilot_db"
    mysql_user: str = "querypilot_readonly"
    mysql_password: str = ""
    mysql_allowed_tables: str = ""
    max_rows: int = 100
    query_timeout_seconds: int = 8
    max_conversation_turns: int = 6

    @property
    def allowed_tables(self) -> set[str] | None:
        if not self.mysql_allowed_tables.strip():
            return None
        return {table.strip() for table in self.mysql_allowed_tables.split(",") if table.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
