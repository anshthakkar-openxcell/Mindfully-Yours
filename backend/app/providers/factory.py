"""
Provider factory -- the ONE place in the codebase allowed to know which vendor backs each
interface. Everything else (app/pipeline, app/safety, app/ingestion) depends only on the
interfaces in app.providers.base and receives an instance from here, typically via FastAPI
dependency injection or a constructed-once app-state object.

This is what makes a provider swap a one-line config change (documnets/understanding/02_ARCHITECTURE.md
§2) -- if you find yourself branching on `settings.llm_provider` anywhere outside this file,
that's a sign the abstraction is leaking.
"""

from functools import lru_cache

from app.core.config import get_settings
from app.providers.base import AvatarProvider, EmbeddingProvider, LLMProvider, STTProvider, TTSProvider
from app.providers.embeddings.openai_embeddings import OpenAIEmbeddingProvider
from app.providers.llm.sarvam import SarvamLLMProvider
from app.providers.stt.deepgram import DeepgramSTTProvider
from app.providers.tts.sarvam_tts import SarvamTTSProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "sarvam":
        return SarvamLLMProvider(
            api_key=settings.sarvam_api_key,
            api_base=settings.sarvam_api_base,
            model=settings.sarvam_llm_model,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")


@lru_cache
def get_stt_provider() -> STTProvider:
    settings = get_settings()
    if settings.stt_provider == "deepgram":
        return DeepgramSTTProvider(api_key=settings.deepgram_api_key)
    raise ValueError(f"Unknown STT_PROVIDER: {settings.stt_provider!r}")


@lru_cache
def get_tts_provider() -> TTSProvider:
    settings = get_settings()
    if settings.tts_provider == "sarvam":
        return SarvamTTSProvider(api_key=settings.sarvam_api_key, api_base=settings.sarvam_api_base)
    raise ValueError(f"Unknown TTS_PROVIDER: {settings.tts_provider!r}")


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            dimensions=settings.embed_dim,
        )
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {settings.embedding_provider!r}")


def get_avatar_provider() -> AvatarProvider | None:
    """Returns None when avatar is disabled/unconfigured -- callers MUST treat that as "skip
    avatar, fall back to voice" per the graceful-degradation ladder in
    documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §10, never as an error."""
    settings = get_settings()
    if not settings.avatar_enabled or not settings.avatar_provider:
        return None
    if settings.avatar_provider == "heygen":
        from app.providers.avatar.heygen import HeyGenAvatarProvider

        return HeyGenAvatarProvider(api_key="")  # TODO: real avatar API key setting once vendor is final
    raise ValueError(f"Unknown AVATAR_PROVIDER: {settings.avatar_provider!r}")
