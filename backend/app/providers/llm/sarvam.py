"""
Sarvam-M adapter -- primary LLM provider, per documnets/understanding/03_TECH_STACK.md §3.
Chosen for Indian-language/Hinglish tone and cost, and because it's also the ingestion-time
chunk-boundary-refinement model (documnets/understanding/07_INGESTION_PIPELINE.md §2 step 2).

Confirmed against Sarvam's real API reference (https://docs.sarvam.ai/api-reference/chat/chat-completions,
Sept 2026), not guessed:
- Endpoint is genuinely `{api_base}/v1/chat/completions` -- the old placeholder path was actually
  already correct; what was wrong was auth, model name, and streaming response parsing (below).
- Auth: Sarvam's native header is `api-subscription-key`, not `Authorization: Bearer` -- the docs
  note the Bearer form is only accepted as an OpenAI-compatible-tooling convenience. Sending both
  is harmless and maximizes the chance of working across Sarvam API versions.
- `"sarvam-m"` (the old hardcoded model) is a DEPRECATED model per Sarvam's own model list --
  confirmed separately when researching the embeddings gap. The two real chat models are
  `sarvam-105b` (128K context, reasoning/agentic) and `sarvam-105b-conversations` (tuned for
  real-time conversational/voice-agent workloads) -- the latter is the correct fit for this
  product and is now the default, but configurable via SARVAM_LLM_MODEL rather than hardcoded.
- Streaming is real Server-Sent Events: each line is `data: {...}` (a JSON chunk with
  `choices[0].delta.content`), terminated by a literal `data: [DONE]` line. The old code yielded
  every raw line verbatim -- including the `data: ` prefixes and the `[DONE]` terminator itself as
  if they were response text. Fixed to parse each chunk and yield only the actual content deltas.
"""

import json
from collections.abc import AsyncIterator

import httpx

from app.core.exceptions import ProviderError
from app.providers.base import LLMProvider


class SarvamLLMProvider(LLMProvider):
    def __init__(self, api_key: str, api_base: str, model: str):
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")
        self._model = model  # from SARVAM_LLM_MODEL -- never hardcode a model name here

    async def generate_stream(
        self, prompt: str, *, max_tokens: int | None = None, temperature: float = 0.7
    ) -> AsyncIterator[str]:
        if not self._api_key:
            raise ProviderError("sarvam_llm", "SARVAM_API_KEY is not configured.")

        async with httpx.AsyncClient(base_url=self._api_base, timeout=30.0) as client:
            async with client.stream(
                "POST",
                "/v1/chat/completions",
                headers={
                    "api-subscription-key": self._api_key,
                    "Authorization": f"Bearer {self._api_key}",
                },
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                },
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    raise ProviderError(
                        "sarvam_llm", f"Unexpected status {response.status_code}: {body.decode(errors='replace')}"
                    )
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[len("data: ") :]
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    choices = chunk.get("choices") or []
                    # Confirmed live: Sarvam sends a trailing chunk with an EMPTY choices array
                    # (usage/stats only) before the final [DONE] line -- skip it rather than crash
                    # on choices[0].
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
