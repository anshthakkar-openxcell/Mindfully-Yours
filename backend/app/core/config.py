"""
App configuration, loaded from environment variables (see .env.example for every key and why
it exists). Reference: documnets/understanding/03_TECH_STACK.md for vendor choices,
11_DATA_MODEL_AND_STORAGE.md for storage, 12_SECURITY_COMPLIANCE_DPDP.md for why vendor keys
must belong to a confirmed no-training/no-retention account before touching real data.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://mindfully:mindfully@localhost:5432/mindfully_ai",
        alias="DATABASE_URL",
    )
    embed_dim: int = Field(default=1024, alias="EMBED_DIM")

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # --- LLM ---
    llm_provider: str = Field(default="sarvam", alias="LLM_PROVIDER")
    sarvam_api_key: str = Field(default="", alias="SARVAM_API_KEY")
    sarvam_api_base: str = Field(default="https://api.sarvam.ai", alias="SARVAM_API_BASE")
    llm_fallback_provider: str = Field(default="", alias="LLM_FALLBACK_PROVIDER")

    # --- STT ---
    # NOTE: 15_OPEN_QUESTIONS_AND_BLOCKERS.md #9 -- dual Deepgram/Sarvam vs Deepgram-only unresolved.
    stt_provider: str = Field(default="deepgram", alias="STT_PROVIDER")
    deepgram_api_key: str = Field(default="", alias="DEEPGRAM_API_KEY")

    # --- TTS / Embeddings ---
    tts_provider: str = Field(default="sarvam", alias="TTS_PROVIDER")
    embedding_provider: str = Field(default="sarvam", alias="EMBEDDING_PROVIDER")

    # --- Avatar ---
    # Vendor unresolved -- 15_OPEN_QUESTIONS_AND_BLOCKERS.md #8. Opt-in + cost-gated by design.
    avatar_provider: str = Field(default="", alias="AVATAR_PROVIDER")
    avatar_enabled: bool = Field(default=False, alias="AVATAR_ENABLED")

    # --- LiveKit (AI Companion Agent only) ---
    livekit_url: str = Field(default="", alias="LIVEKIT_URL")
    livekit_api_key: str = Field(default="", alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field(default="", alias="LIVEKIT_API_SECRET")

    # --- Safety / retrieval thresholds ---
    retrieval_confidence_threshold: float = Field(
        default=0.75, alias="RETRIEVAL_CONFIDENCE_THRESHOLD"
    )
    # Deliberately more permissive than a normal RAG match -- 08_SAFETY_INTERLOCK_AND_TRIAGE.md §4:
    # a false positive here costs a moment's extra caution; a false negative costs a missed danger signal.
    redflag_match_threshold: float = Field(default=0.55, alias="REDFLAG_MATCH_THRESHOLD")


@lru_cache
def get_settings() -> Settings:
    return Settings()
