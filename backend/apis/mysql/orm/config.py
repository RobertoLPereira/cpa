import os
from decimal import Decimal
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 1. Configurações Globais do Aplicativo
    ENVIRONMENT: Literal["development", "production", "testing"] = "development"
    DEBUG: bool = True

    # 2. Infraestrutura (String de Conexão Validada)
    DATABASE_URL_MYSQL: str

    # 3. Parâmetros Fiscais (Tipados estritamente em Decimal)
    ALIQUOTA_BASE_IBS: Decimal = Decimal("0.01")
    ALIQUOTA_BASE_CBS: Decimal = Decimal("0.09")
    MATRIZ_API_URL: str = "https://matriz-sistema.com.br"

    # Carrega automaticamente do arquivo .env localizado na raiz
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore" # Ignora variáveis extras caso existam no .env
    )

# Instancia o objeto de configurações global para o projeto
settings = Settings()
