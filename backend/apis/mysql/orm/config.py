import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

if getattr(sys, "frozen", False):
    ENV_PATH = Path(sys.executable).resolve().parent / ".env"
else:
    ENV_PATH = Path(".env")

class Settings(BaseSettings):
    ENVIRONMENT: Literal["development", "production", "testing"] = "development"
    DEBUG: bool = False

    DATABASE_URL_MYSQL: str
    TOTAL_CAIXAS_LOJA: int = 5
    ALIQUOTA_BASE_IBS: Decimal = Decimal("0.01")
    ALIQUOTA_BASE_CBS: Decimal = Decimal("0.09")
    MATRIZ_API_URL: str = "https://matriz-sistema.com.br"

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
