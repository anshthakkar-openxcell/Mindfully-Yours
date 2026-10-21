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
    # "sarvam-m" (the old default) is DEPRECATED per Sarvam's own model list, confirmed Sept 2026.
    # sarvam-105b-conversations is tuned for real-time conversational/voice-agent workloads --
    # the right fit for this product -- vs. sarvam-105b's reasoning/agentic focus.
    sarvam_llm_model: str = Field(default="sarvam-105b-conversations", alias="SARVAM_LLM_MODEL")
    llm_fallback_provider: str = Field(default="", alias="LLM_FALLBACK_PROVIDER")

    # --- STT ---
    # RESOLVED 2026-10-01 (direct product decision, overriding the dual Deepgram/Sarvam-vs-
    # Deepgram-only discrepancy in documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #9):
    # Sarvam only, for both STT and TTS. Deepgram is not used anywhere in this system.
    stt_provider: str = Field(default="sarvam", alias="STT_PROVIDER")
    # saaras:v3-realtime is Sarvam's real-time streaming STT model (wss://.../speech-to-text-realtime/ws)
    # -- confirmed against Sarvam's live API reference (docs.sarvam.ai, Oct 2026), not guessed.
    sarvam_stt_model: str = Field(default="saaras:v3-realtime", alias="SARVAM_STT_MODEL")
    # Caller (app.realtime.agent) must deliver audio already resampled to this rate, mono, linear16
    # -- this adapter does not resample. 16kHz is Sarvam's documented best-supported rate.
    sarvam_stt_sample_rate: int = Field(default=16000, alias="SARVAM_STT_SAMPLE_RATE")

    # --- TTS ---
    tts_provider: str = Field(default="sarvam", alias="TTS_PROVIDER")
    # bulbul:v3 -- confirmed live (2026-10-01): a real synthesis call against bulbul:v2 (what the
    # docs still listed as current) returned "400: Model 'bulbul:v2' has been deprecated. Please
    # use 'bulbul:v3' instead." -- the docs lagged the real API here.
    sarvam_tts_model: str = Field(default="bulbul:v3", alias="SARVAM_TTS_MODEL")
    # v2 and v3 have non-overlapping speaker lists -- "shubh" confirmed live as a valid v3 speaker
    # (a v2 speaker name on v3 fails with a 400 listing the real options).
    sarvam_tts_speaker: str = Field(default="shubh", alias="SARVAM_TTS_SPEAKER")
    sarvam_tts_sample_rate: int = Field(default=24000, alias="SARVAM_TTS_SAMPLE_RATE")  # v3's default rate

    # --- Embeddings ---
    # NOT Sarvam -- confirmed Sarvam has no embeddings product at all (checked their live model
    # list + API reference directly, Sept 2026). OpenAI's text-embedding-3-small was already the
    # documented fallback/benchmark vendor (03_TECH_STACK.md), so it's promoted to primary here.
    embedding_provider: str = Field(default="openai", alias="EMBEDDING_PROVIDER")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_embedding_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")

    # --- Avatar ---
    # Vendor unresolved -- 15_OPEN_QUESTIONS_AND_BLOCKERS.md #8. Opt-in + cost-gated by design.
    avatar_provider: str = Field(default="", alias="AVATAR_PROVIDER")
    avatar_enabled: bool = Field(default=False, alias="AVATAR_ENABLED")

    # --- LiveKit (AI Companion Agent only) ---
    livekit_url: str = Field(default="", alias="LIVEKIT_URL")
    livekit_api_key: str = Field(default="", alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field(default="", alias="LIVEKIT_API_SECRET")

    # --- Safety / retrieval thresholds ---
    # Defaults below match what was actually live-tested and validated against OpenAI's real
    # embeddings (2026-09-28-29, see 15_OPEN_QUESTIONS_AND_BLOCKERS.md #28) -- NOT the original
    # guessed values (0.75 / 0.55) from when Sarvam embeddings were still assumed to exist.
    retrieval_confidence_threshold: float = Field(
        default=0.30, alias="RETRIEVAL_CONFIDENCE_THRESHOLD"
    )
    # Deliberately more permissive than a normal RAG match -- 08_SAFETY_INTERLOCK_AND_TRIAGE.md §4:
    # a false positive here costs a moment's extra caution; a false negative costs a missed danger signal.
    redflag_match_threshold: float = Field(default=0.44, alias="REDFLAG_MATCH_THRESHOLD")
    # Upper bound of the "soft zone" for the small, explicit set of flags in
    # app.safety.interlock.SOFT_ZONE_ELIGIBLE_FLAGS (currently just RF-028) -- confirmed
    # false-positive-prone on ordinary language (see 15_OPEN_QUESTIONS_AND_BLOCKERS.md #28,
    # "I want to leave my partner" scoring 0.46-0.59 against RF-028 with zero danger content).
    # A match at/above this still hard-escalates exactly as before; a match between
    # REDFLAG_MATCH_THRESHOLD and this value gets a gentle real clarifying question instead of an
    # alarming crisis script. Deliberately NOT applied to suicide/self-harm flags -- see that
    # module's docstring for why.
    redflag_soft_zone_threshold: float = Field(default=0.55, alias="REDFLAG_SOFT_ZONE_THRESHOLD")
    # Lower, more sensitive threshold applied ONLY to app.safety.interlock.CRITICAL_SELF_HARM_FLAGS
    # (RF-018/RF-019 -- suicide ideation), checked among the top-15 candidates rather than just the
    # single nearest flag. Live-tested (2026-09-29): real disclosures scored 0.366-0.409 against these
    # two flags, while ordinary messages ("fight with my mom") scored only 0.19-0.29 -- a clean gap.
    # RF-025 was deliberately left out of this list: its own trigger_phrases include "slamming my fist
    # in the wall", so it matches ordinary anger-at-someone-else language (0.39-0.48) even higher than
    # some real self-harm disclosures (0.47) -- no threshold separates those two bands for RF-025, and
    # it doesn't need to be here anyway since genuine self-harm disclosures already clear the ordinary
    # 0.44 threshold via the normal top-1 path. See .env and that module's CRITICAL_SELF_HARM_FLAGS
    # docstring for the full numbers -- this is NOT a solved boundary, and a real validation dataset
    # (plus fixing RF-025's trigger phrases) is still needed.
    redflag_critical_threshold: float = Field(default=0.36, alias="REDFLAG_CRITICAL_THRESHOLD")
    # How many candidate chunks search_self_care_content() considers before the confidence
    # threshold filters them down -- a ceiling, not a guarantee (see that function's docstring).
    retrieval_top_k: int = Field(default=3, alias="RETRIEVAL_TOP_K")

    # --- Translation for Hindi / Hinglish users (app.providers.translation; doc 34) ---
    # mayura:v1 chosen after a live comparison (2026-10-09): it translated code-mixed and Romanised
    # Hindi accurately ("mujhe marne ka mann kar raha hai..." -> "I feel like dying, ..."), while
    # sarvam-translate:v1 mangled a mixed sentence. ~0.7 s per call (1.5 s with a script option).
    translation_enabled: bool = Field(default=True, alias="TRANSLATION_ENABLED")
    sarvam_translate_model: str = Field(default="mayura:v1", alias="SARVAM_TRANSLATE_MODEL")
    translation_timeout_seconds: float = Field(default=5.0, alias="TRANSLATION_TIMEOUT_SECONDS")

    # --- Therapist-first response (app.pipeline.curated_match; doc 32) ---
    # PROVISIONAL starting points chosen from a 5-message spot check against the real table (a clear
    # paraphrase scored 0.80, a right-topic-different-wording message 0.66, wrong matches 0.50-0.56)
    # -- NOT calibrated. Doc 32 step 7 (therapist-labelled test set) must set these before relying on
    # them; until then they are deliberately conservative (strong = serve as written, so it is rare).
    curated_match_enabled: bool = Field(default=True, alias="CURATED_MATCH_ENABLED")
    curated_strong_similarity: float = Field(default=0.85, alias="CURATED_STRONG_SIMILARITY")
    curated_partial_similarity: float = Field(default=0.62, alias="CURATED_PARTIAL_SIMILARITY")
    # A reply taken from the MIDDLE of a conversation only makes sense in context, so it needs this
    # much extra similarity to count as strong.
    curated_non_opening_margin: float = Field(default=0.05, alias="CURATED_NON_OPENING_MARGIN")
    # What a PARTIAL match does: "rephrase" = the LLM lightly rewords the therapist's reply (buffered,
    # checked, falls back to the verbatim reply if it drifts); "verbatim" = serve the therapist's reply
    # as written, no LLM at all (fastest, most faithful). Client decision pending (doc 32 §5 #1).
    curated_partial_mode: str = Field(default="rephrase", alias="CURATED_PARTIAL_MODE")
    # How many therapist clarifying questions to ask in a row before the LLM is allowed to answer.
    curated_clarify_limit: int = Field(default=1, alias="CURATED_CLARIFY_LIMIT")
    curated_top_k: int = Field(default=5, alias="CURATED_TOP_K")
    # On a PARTIAL match the LLM is shown up to this many close therapist examples (the best one plus
    # other close ones above the partial threshold), so it gets the full idea of how the team handles
    # this kind of situation instead of working from a single reply.
    curated_max_examples: int = Field(default=3, alias="CURATED_MAX_EXAMPLES")

    # --- Triage thresholds (app.safety.triage) ---
    # PROVISIONAL, same caveat as above -- a small-sample starting point (live-tested against
    # kb_signals/kb_symptoms real rows, 2026-09-29), not a validated production threshold. A real
    # validation set is still needed (the already-deferred validation gate).
    #
    # CONFIRMED HONEST LIMITATION: kb_signals matching is noisier than red-flag or pattern-name
    # matching. Live test: "I had a really productive day at work" (a benign, positive message)
    # scored 0.488 similarity to SIG-228 "Hypomania" -- HIGHER than the real stomach-pain message's
    # genuine match to SIG-261 "Emotional Pain" (0.479). There is no threshold that cleanly
    # separates real signal from noise at the individual-signal level with this small a sample --
    # 0.45 is a conservative compromise, not a solved problem. This is exactly why matched signals
    # feed an ACCUMULATED per-conversation record (see app.pipeline.state.ConversationState) rather
    # than being treated as fact from a single turn -- one noisy match should never be decisive.
    triage_signal_threshold: float = Field(default=0.45, alias="TRIAGE_SIGNAL_THRESHOLD")
    triage_top_k: int = Field(default=5, alias="TRIAGE_TOP_K")
    # Separate from triage_signal_threshold -- pattern_name_embedding matches a short label (e.g.
    # "situational low mood") against a whole sentence, a different similarity distribution than
    # phrase-to-phrase signal matching, so it needs its own bar, not a reused one.
    pattern_match_threshold: float = Field(default=0.30, alias="PATTERN_MATCH_THRESHOLD")

    # --- Tier scoring (app.pipeline.tier_scoring) ---
    # See documnets/understanding/28_TIER_SCORING_APPROACH.md for the full design. ALL of these are
    # illustrative starting points, same caveat as every other threshold above -- not clinically
    # validated, pending real review with the clinical team.
    #
    # ONLY ONE cutoff -- the running score decides between Tier 1 (ordinary) and Tier 2 (worth
    # attention, working toward a booking suggestion once confident). There is deliberately NO
    # score-based Tier 3: Tier 3 is exclusively the safety interlock's crisis/SOS path (see
    # app.safety.interlock), triggered only by genuinely critical content, never by accumulating
    # points from an ordinary conversation. CORRECTED 2026-09-30 -- a `TIER3_SCORE_MIN` used to exist
    # here, letting an ordinary but concerning conversation (e.g. sustained work stress) reach a
    # bracket literally called "Tier 3", the same label as a genuine self-harm disclosure. Removed.
    tier2_score_min: int = Field(default=40, alias="TIER2_SCORE_MIN")
    # Points removed from the running score for each turn that contributes no NEW signal -- lets a
    # one-off spike ease back down instead of permanently sticking the conversation at a high tier.
    tier_score_decay_per_quiet_turn: int = Field(default=5, alias="TIER_SCORE_DECAY_PER_QUIET_TURN")
    # Ceiling on how many points a SINGLE turn can add, regardless of how many signals it matched.
    # Necessary because kb_signals matching is confirmed noisy at the individual-signal level (see
    # TRIAGE_SIGNAL_THRESHOLD's comment) -- one message can trip 8-10 simultaneous signal/symptom
    # matches from the top-K triage lookup, which without this cap summed straight past 100 on the
    # very first turn in live testing (2026-09-30), defeating the entire point of a running score
    # that's meant to accumulate gradually across a conversation, not spike from one noisy message.
    tier_score_max_gain_per_turn: int = Field(default=25, alias="TIER_SCORE_MAX_GAIN_PER_TURN")
    # How many genuinely DISTINCT signals must have accumulated before the conversation is
    # considered confident enough to redirect toward booking a consultation -- see
    # 28_TIER_SCORING_APPROACH.md's "Score and redirect are two different decisions" section. A
    # score crossing tier2_score_min is not by itself enough; redirecting is a much bigger action
    # than one more reply, so it needs corroboration across turns, not a single strong message.
    redirect_min_distinct_signals: int = Field(default=3, alias="REDIRECT_MIN_DISTINCT_SIGNALS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
