"""
Sarvam translation (`POST /translate`, model mayura:v1) -- used so Hindi / Hinglish users get the same
safety checks and therapist library as English users, and a reply in their own language (doc 34).

Confirmed by live calls (2026-10-09), not assumed:
- mayura:v1, mode "modern-colloquial", source hi-IN -> en-IN translated Devanagari, Romanised Hindi and
  code-mixed text accurately ("mujhe marne ka mann kar raha hai, ab aur jeena nahi chahta" ->
  "I feel like dying, now I don't want to live anymore."). sarvam-translate:v1 was faster (~0.6 s) but
  mangled a mixed sentence, so it is NOT used.
- ~0.7 s per call (about 1.5 s when an output_script option is set). That is why fixed replies are
  pre-translated offline (app.pipeline.localize) instead of translated per turn.
- The input limit is ~1000 characters per call, so longer text is split on sentence boundaries and the
  pieces are translated concurrently -- never truncated (a crisis statement at the end of a long
  message must not be lost).
"""

from __future__ import annotations

import asyncio
import re
from typing import Literal

import httpx

from app.core.exceptions import ProviderError

Style = Literal["hi", "hinglish"]
_MAX_CHARS = 900  # safely under the API's documented ~1000-character input limit
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।])\s+")


def split_for_translation(text: str, max_chars: int = _MAX_CHARS) -> list[str]:
    """Split on sentence boundaries into chunks <= max_chars (a single over-long sentence is hard-split)."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current = ""
    for sentence in _SENTENCE_SPLIT.split(text):
        while len(sentence) > max_chars:  # one enormous "sentence": hard split rather than drop text
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if current and len(current) + 1 + len(sentence) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


class SarvamTranslator:
    def __init__(self, api_key: str, api_base: str, model: str, timeout: float):
        self._api_key = api_key
        self._model = model
        # ONE persistent client (same reasoning as the embeddings provider): no TCP+TLS handshake per call.
        self._client = httpx.AsyncClient(base_url=api_base.rstrip("/"), timeout=timeout)

    async def _translate_chunk(self, text: str, *, source: str, target: str, script: str | None) -> str:
        body: dict = {
            "input": text,
            "source_language_code": source,
            "target_language_code": target,
            "model": self._model,
            "mode": "modern-colloquial",  # everyday speech, how people actually talk -- not textbook Hindi
        }
        if script:
            body["output_script"] = script
        response = await self._client.post("/translate", headers={"api-subscription-key": self._api_key}, json=body)
        if response.status_code != 200:
            raise ProviderError("sarvam_translate", f"Unexpected status {response.status_code}: {response.text[:200]}")
        translated = (response.json().get("translated_text") or "").strip()
        if not translated:
            raise ProviderError("sarvam_translate", "Empty translation returned.")
        return translated

    async def _translate(self, text: str, *, source: str, target: str, script: str | None = None) -> str:
        if not self._api_key:
            raise ProviderError("sarvam_translate", "SARVAM_API_KEY is not configured.")
        parts = await asyncio.gather(
            *[self._translate_chunk(c, source=source, target=target, script=script) for c in split_for_translation(text)]
        )
        return " ".join(parts)

    async def to_english(self, text: str) -> str:
        """Hindi / Hinglish / mixed -> English. Source is always hi-IN: that handled Devanagari,
        Romanised and code-mixed input correctly in testing and is ~0.4 s faster than 'auto'."""
        return await self._translate(text, source="hi-IN", target="en-IN")

    async def from_english(self, text: str, *, style: Style) -> str:
        """English -> Hindi. 'hi' keeps Devanagari (English loanwords stay in Latin, as people write them);
        'hinglish' asks for Roman script so the reply matches how the user typed."""
        return await self._translate(
            text, source="en-IN", target="hi-IN", script="roman" if style == "hinglish" else None
        )

    async def aclose(self) -> None:
        await self._client.aclose()
