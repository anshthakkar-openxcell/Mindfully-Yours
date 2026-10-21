"""Translator behaviour with a fake HTTP transport -- no network, no API key needed."""

import asyncio
import json

import httpx

from app.pipeline.guardrail import check_rephrase_faithful
from app.providers.translation import SarvamTranslator, split_for_translation


def _translator(handler) -> SarvamTranslator:
    t = SarvamTranslator(api_key="k", api_base="https://example.test", model="mayura:v1", timeout=3.0)
    t._client = httpx.AsyncClient(base_url="https://example.test", transport=httpx.MockTransport(handler))
    return t


def test_short_text_is_one_chunk_and_long_text_is_split_without_losing_anything():
    assert split_for_translation("short.") == ["short."]
    long = " ".join(f"This is sentence number {i}." for i in range(80))  # ~2.3k chars
    chunks = split_for_translation(long, max_chars=900)
    assert len(chunks) >= 3 and all(len(c) <= 900 for c in chunks)
    assert " ".join(chunks).split() == long.split()  # nothing dropped, order kept -- a crisis line at the end survives
    assert all(len(c) <= 900 for c in split_for_translation("x" * 2500, max_chars=900))  # one huge "sentence"


def test_to_english_sends_hindi_source_and_modern_colloquial_mode():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        seen["key"] = request.headers["api-subscription-key"]
        return httpx.Response(200, json={"translated_text": "I feel like dying."})

    out = asyncio.run(_translator(handler).to_english("mujhe marne ka mann kar raha hai"))
    assert out == "I feel like dying."
    assert seen["source_language_code"] == "hi-IN" and seen["target_language_code"] == "en-IN"
    assert seen["model"] == "mayura:v1" and seen["mode"] == "modern-colloquial" and seen["key"] == "k"
    assert "output_script" not in seen


def test_hinglish_reply_asks_for_roman_script_and_hindi_does_not():
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"translated_text": "ok"})

    t = _translator(handler)
    asyncio.run(t.from_english("Hello there.", style="hinglish"))
    asyncio.run(t.from_english("Hello there.", style="hi"))
    assert bodies[0]["output_script"] == "roman" and "output_script" not in bodies[1]


def test_api_error_raises_so_callers_can_fall_back():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    try:
        asyncio.run(_translator(handler).to_english("kya karu"))
    except Exception as exc:  # noqa: BLE001
        assert "500" in str(exc)
    else:
        raise AssertionError("expected an error")


def test_overlap_check_is_skipped_only_for_cross_language_rephrasing():
    original = "That sounds hard. What has been the toughest part?"
    hindi = "यह सुनकर बुरा लगा। सबसे मुश्किल हिस्सा क्या रहा है?"
    assert check_rephrase_faithful(hindi, original=original, check_overlap=False).passed
    # English-vs-English still catches drift when the overlap check is on:
    assert not check_rephrase_faithful("You should try meditation daily and exercise more.", original=original).passed
    # but numbers/links are still blocked when the overlap check is off
    assert not check_rephrase_faithful("कॉल करें 9152987821", original=original, check_overlap=False).passed
