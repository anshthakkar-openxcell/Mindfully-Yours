"""
Sarvam Language Identification (`/text-lid`) -- a small, focused REST call used ONLY by the voice
layer (app.realtime.livekit_llm) to decide which language/voice Sarvam TTS should speak a reply
in. Not part of the shared app.providers.base abstraction used by text mode: this exists purely to
solve "the LLM just replied -- what language is that reply actually in, so TTS pronounces it
correctly," a problem that only exists because TTS (unlike the LLM) can't auto-detect language.

Why this exists instead of trusting the STT's own per-utterance language tag: confirmed live
(2026-10-01) that Sarvam's realtime STT language tag is NOT reliable for Hindi specifically --
the same genuine Hindi utterance was sometimes transcribed as Devanagari with a correct `hi-IN`
tag, and other times transliterated to Roman script and mistagged `en-IN` (0.72 confidence). A
dedicated text-based identifier is more reliable here, confirmed live against both scripts:
- Devanagari Hindi ("नमस्ते आप कैसे हैं") -> {"language_code": "hi-IN", "script_code": "Deva"}
- Romanized/Hinglish Hindi ("Namaste, aap kaise hain?", "Yaar mujhe thoda sad feel ho raha hai
  aajkal.") -> {"language_code": "hi-IN", "script_code": "Latn"} -- correctly identified as Hindi
  even written in Latin script, which a naive Unicode-range check would have missed entirely.
- Plain English -> {"language_code": "en-IN", "script_code": "Latn"}

Confirmed against Sarvam's real API reference (docs.sarvam.ai, Oct 2026) AND a live call, same
diligence as every other Sarvam adapter in this codebase.
"""

import httpx

from app.core.exceptions import ProviderError

# Phase 1 only ever needs to distinguish these two -- see documnets/understanding/
# 13_LANGUAGE_PHASING.md. Sarvam's /text-lid supports 11 Indian languages; only mapping the ones
# this product's TTS speaker (bulbul:v3 "shubh") actually needs to voice today.
_SUPPORTED_TTS_LANGUAGES = {"en-IN", "hi-IN"}


async def identify_language(text: str, *, api_key: str, api_base: str, fallback: str = "en") -> str:
    """Returns a short code ("en" or "hi") for TTS language selection. Falls back to `fallback`
    on any error or an unsupported/unexpected detected language -- a wrong guess here means a
    reply gets voiced in the wrong accent, not a safety issue, so failing soft is correct."""
    if not text.strip():
        return fallback
    try:
        async with httpx.AsyncClient(base_url=api_base.rstrip("/"), timeout=5.0) as client:
            response = await client.post(
                "/text-lid",
                headers={"api-subscription-key": api_key},
                json={"input": text[:1000]},  # API's own documented input limit
            )
            if response.status_code != 200:
                raise ProviderError("sarvam_text_lid", f"Unexpected status {response.status_code}")
            detected = response.json().get("language_code")
    except (httpx.HTTPError, ProviderError):
        return fallback

    if detected not in _SUPPORTED_TTS_LANGUAGES:
        return fallback
    return detected.split("-")[0]  # "hi-IN" -> "hi", "en-IN" -> "en"
