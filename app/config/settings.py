from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    DATABASE_URL: str = "sqlite:///./data/wordagent.db"

    # Storage
    STORAGE_DIR: Path = Path("./data/files")
    TEMP_DIR: Path = Path("./data/temp")

    # Word COM
    WORD_COM_TIMEOUT_SECONDS: int = 30
    WORD_COM_RETRY_COUNT: int = 3

    # PDF
    PDF_RENDER_DPI: int = 300

    # Text Anchor
    TEXT_ANCHOR_MIN_CONFIDENCE: float = 0.6
    TEXT_ANCHOR_CHUNK_SIZE: int = 50

    # API
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000


settings = Settings()
