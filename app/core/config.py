from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://redis:6379"

    # LLM — provider-agnostic settings
    # Supported providers: "openai", "google", "anthropic"
    LLM_PROVIDER: str = "google"
    LLM_MODEL: str = "gemini-2.0-flash"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 300

    # Embeddings — defaults to same provider as LLM
    EMBEDDING_PROVIDER: str = ""  # falls back to LLM_PROVIDER
    EMBEDDING_MODEL: str = ""     # falls back to provider default

    # STT (speech-to-text) provider: "openai" (Whisper) or "google"
    STT_PROVIDER: str = "google"

    # API Keys — only the key matching your provider is required
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # ElevenLabs
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = ""

    # Google Maps
    GOOGLE_MAPS_API_KEY: str = ""

    # Vector DB
    FAISS_INDEX_PATH: str = "./faiss_index"

    # Twilio (Guardian notification)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""


settings = Settings()
