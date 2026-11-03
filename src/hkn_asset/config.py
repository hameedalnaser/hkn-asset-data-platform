"""Central configuration.

JD standard: "no credentials in code". All secrets come from environment
variables (loaded from a gitignored .env in dev; from App Service / VM
settings in production). Nothing sensitive is hardcoded here.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Azure SQL
    sql_server: str = Field(default="localhost")
    sql_database: str = Field(default="hkn_asset")
    sql_username: str = Field(default="sa")
    sql_password: str = Field(default="")
    sql_driver: str = Field(default="ODBC Driver 18 for SQL Server")

    # API
    api_key: str = Field(default="dev-key")

    # Paths
    incoming_dir: Path = Field(default=PROJECT_ROOT / "sample_data" / "incoming")
    processed_dir: Path = Field(default=PROJECT_ROOT / "sample_data" / "processed")

    @property
    def odbc_connection_string(self) -> str:
        """pyodbc connection string. Encrypt=yes is required by Azure SQL."""
        return (
            f"DRIVER={{{self.sql_driver}}};"
            f"SERVER={self.sql_server};"
            f"DATABASE={self.sql_database};"
            f"UID={self.sql_username};"
            f"PWD={self.sql_password};"
            "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
