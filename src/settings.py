from __future__ import annotations

import logging
import sys
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

import structlog
from pydantic import (
    Field,
    PostgresDsn,
    SecretStr,
    computed_field,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

_DB_DEFAULTS = "postgres"


BASE_SETTINGS_CONFIG = SettingsConfigDict(
    extra="ignore",
    case_sensitive=False,
    env_file=".env",
    env_nested_delimiter="__",
    env_ignore_empty=True,
)


class Environment(StrEnum):
    DEV = "DEV"
    PROD = "PROD"


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict({**BASE_SETTINGS_CONFIG, "env_prefix": "DB__"})

    host: SecretStr = SecretStr("localhost")
    user: SecretStr = SecretStr(_DB_DEFAULTS)
    password: SecretStr = SecretStr(_DB_DEFAULTS)
    database_name: SecretStr = SecretStr(_DB_DEFAULTS)
    port: int = 5432
    driver: str | None = "psycopg"

    @field_validator("port", mode="before")
    @classmethod
    def setDefaultPort(cls, port: object) -> object:
        return 5432 if not port else port

    @computed_field
    @property
    def dsn(self) -> str:
        return str(
            PostgresDsn.build(
                scheme=f"postgresql+{self.driver}",
                username=self.user.get_secret_value(),
                password=self.password.get_secret_value(),
                host=self.host.get_secret_value(),
                port=self.port,
                path=self.database_name.get_secret_value(),
            )
        )


class LoggerSettings(BaseSettings):
    model_config = SettingsConfigDict(**BASE_SETTINGS_CONFIG)

    display_all_logs: bool = False
    log_dir: Path | None = Path(".logs")


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(**BASE_SETTINGS_CONFIG)
    env: Environment = Environment.DEV

    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logger: LoggerSettings = Field(default_factory=LoggerSettings)


@lru_cache
def getSettings() -> AppSettings:
    return AppSettings()


def configureLogging(settings: AppSettings) -> None:
    handlers = [logging.StreamHandler(sys.stdout)]

    if settings.env == Environment.DEV and settings.logger.log_dir:
        settings.logger.log_dir.mkdir(exist_ok=True, parents=True)
        handlers.append(logging.FileHandler(settings.logger.log_dir / "log.log"))

    logging.basicConfig(
        level=logging.DEBUG if settings.env == Environment.DEV else logging.INFO,
        format="%(message)s",
        handlers=handlers,
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            (
                structlog.dev.ConsoleRenderer(pad_level=False)
                if settings.env == Environment.DEV
                else structlog.processors.JSONRenderer()
            ),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    if not settings.logger.display_all_logs:
        for name in ("httpx2", "httpcore2"):
            logging.getLogger(name).setLevel(logging.WARNING)
