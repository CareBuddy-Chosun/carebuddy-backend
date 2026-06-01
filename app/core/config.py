from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Application
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./carebuddy.db"

    # Redis
    REDIS_URL: str = "redis://redis:6379"

    # LLM (OpenAI-compatible: works with OpenAI, Ollama, LM Studio)
    OPENAI_API_KEY: str = "ollama"
    OPENAI_BASE_URL: str = "http://localhost:11434/v1"
    LLM_MODEL: str = "gemma2"
    EMBEDDING_MODEL: str = "text-embedding-nomic-embed-text-v1.5"

    # Maps (Naver Local Search API — Naver Developers credentials)
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""

    # Maps (Naver Cloud Platform — NCP Maps reverse geocoding, separate creds)
    NAVER_MAPS_KEY_ID: str = ""
    NAVER_MAPS_KEY: str = ""

    # Vector DB
    FAISS_INDEX_PATH: str = "./faiss_index"


settings = Settings()
