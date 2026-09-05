"""
ClaimLens AI - Configuration Management
Handles environment variables and system settings.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Base directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    POLICY_DIR: Path = DATA_DIR / "policy"
    CLAIMS_DIR: Path = DATA_DIR / "claims"
    PROCESSED_DIR: Path = DATA_DIR / "processed"
    FRONTEND_DIR: Path = BASE_DIR / "frontend"

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # Project metadata
    PROJECT_NAME: str = "ClaimLens AI"
    VERSION: str = "0.1.0"
    PROBLEM_STATEMENT: str = "PS02 — Insurance Claims Evidence Review Assistant"

    # Gemini AI configuration
    # ONLY external API allowed: Gemini (embeddings & LLM)
    GEMINI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    LLM_MODEL: str = "gemini-1.5-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
