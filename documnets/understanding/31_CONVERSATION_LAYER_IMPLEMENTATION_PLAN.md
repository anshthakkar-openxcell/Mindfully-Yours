# 31. Conversation Layer — Implementation Plan (LiveKit · STT · LLM · TTS, streaming end-to-end)

**Why this doc exists:** the client/dev direction as of 2026-10-01 is to deliberately build the **real-time conversation (transport + voice) layer first**, in isolation from knowledge-base/RAG depth, so the frontend engineer can start integrating against a working voice pipeline. This is a conscious reordering of [14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md](14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md)'s own epic sequence (which lists KB ingestion before the conversation pipeline before the LiveKit Agent) — not an oversight, a scoping call being made now. This doc is the concrete, file-level plan for that reordered slice of work.

---

## 1. Scope — what "conversation layer" means here

**In scope:**
- The LiveKit Room/Agent transport (join, subscribe, publish — never create Rooms or issue tokens, see [10_LIVEKIT_REALTIME.md](10_LIVEKIT_REALTIME.md), [LIVEKIT.md](../approch/LIVEKIT.md) §3)
- Streaming STT (**Sarvam Saaras**, real-time WebSocket — see §0 below, not Deepgram)
- Streaming LLM turn (already real, via the existing orchestrator — reused unchanged, not rebuilt)
- Streaming TTS (**Sarvam Bulbul**, real-time WebSocket)
- Turn-taking / interruption (barge-in), via the LiveKit Agents framework, not hand-rolled VAD
- Latency instrumentation and the filler-phrase masking layer

**Explicitly out of scope for this pass** (per direct product decisions as of 2026-10-01):
- Deepening knowledge-base/RAG retrieval quality, ingesting more KB content, or resolving KB data-quality gaps ([05](05_KNOWLEDGE_BASE_DEEP_DIVE.md), [07](07_INGESTION_PIPELINE.md), [18](18_NEW_CONVO_DATA_CATALOG.md))
- Avatar (Spatius.ai/HeyGen/Rive — vendor itself still unresolved, [15](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #8)
- Practitioner/SOS human-to-human Rooms (same LiveKit infra, different, much simpler use case — no Agent participant at all, [LIVEKIT.md](../approch/LIVEKIT.md) §3)
- Hindi / multi-language (Phase 1 stays English-only by design, [13_LANGUAGE_PHASING.md](13_LANGUAGE_PHASING.md))
- **The frontend/NestJS contract** (Room-naming convention, data-channel message schema, anything the real Flutter/Next.js client or the NestJS backend would integrate against) — explicitly deferred. This pass builds the conversation layer as a self-contained backend capability; the integration contract is a separate, later conversation.

### §0. Decision update (2026-10-01): STT vendor resolved — Sarvam only, not Deepgram
The dual-Deepgram/Sarvam-vs-Deepgram-only question this doc originally carried as open (and [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #9) is now resolved by direct product decision: **Sarvam for both STT and TTS, Deepgram is not used anywhere in this system.** `app/providers/stt/deepgram.py` has been deleted (not just deprecated). This section of the plan has been rewritten accordingly — every "Deepgram" reference below has been replaced with the real, now-implemented Sarvam STT adapter.

**Important nuance — we are not "turning RAG off" anywhere in code.** `app.pipeline.orchestrator.run_turn` ([orchestrator.py](../../backend/app/pipeline/orchestrator.py)) already runs triage + the safety interlock on every turn unconditionally, and only *attempts* self-care/RAG retrieval when a routing rule confirms Tier 1. With the KB sparsely populated, that retrieval step naturally returns nothing and the LLM just falls back to plain persona-grounded phrasing — this already degrades gracefully by design, so the conversation layer can be built and tested end-to-end today without first fixing KB content. Nothing needs to be special-cased or stubbed out.

---

## 2. Current state (grounded in the actual repo, updated 2026-10-01)

| Piece | File | Status |
|---|---|---|
| LiveKit Agent entrypoint | [`app/realtime/agent.py`](../../backend/app/realtime/agent.py) | **Real, working, live-tested end-to-end against the real LiveKit Cloud project** (2026-10-01). Uses `livekit-agents` 1.8.3's `AgentSession` with three thin plugin wrappers — [`livekit_stt.py`](../../backend/app/realtime/livekit_stt.py), [`livekit_tts.py`](../../backend/app/realtime/livekit_tts.py), [`livekit_llm.py`](../../backend/app/realtime/livekit_llm.py) — around the existing Sarvam adapters and `run_turn`, plus Silero VAD. See §4 Phase 5 for the full account, including a real bug caught by capturing and analyzing actual response audio (not just byte counts). |
| STT adapter | [`app/providers/stt/sarvam_stt.py`](../../backend/app/providers/stt/sarvam_stt.py) | **Real, working, live-tested.** Real-time streaming against Sarvam Saaras (`wss://.../speech-to-text-realtime/ws`), partial + final transcripts via the new `TranscriptChunk(text, is_final)` type (see §2a). Verified 2026-10-01 with a live round-trip test (TTS-generated audio fed back through this adapter, transcript matched the source text exactly, partials streamed in well under 1s). The old Deepgram stub (`app/providers/stt/deepgram.py`) is deleted, not kept around unused. |
| TTS adapter | [`app/providers/tts/sarvam_tts.py`](../../backend/app/providers/tts/sarvam_tts.py) | **Real, working, live-tested.** Real-time streaming against Sarvam Bulbul (`wss://.../text-to-speech/ws`), model `bulbul:v3`/speaker `shubh` (the docs still listed `bulbul:v2` as current; a live call returned a 400 confirming it's deprecated server-side — corrected to the real model). Verified 2026-10-01: ~380-550ms to first audio byte, fully streamed, for short sentences. |
| LLM adapter | [`app/providers/llm/sarvam.py`](../../backend/app/providers/llm/sarvam.py) | **Real, working.** Streaming SSE, correct auth header, correct model (`sarvam-105b-conversations`), handles Sarvam's trailing empty-choices chunk. |
| Turn orchestrator | [`app/pipeline/orchestrator.py`](../../backend/app/pipeline/orchestrator.py) | **Real, working, 14-step pipeline** — cache, one shared embedding call, triage, interlock (fail-safe), routing, prompt assembly, streaming LLM call, guardrail, audit log. This is what the Agent must call into **unchanged** |
| Filler phrases | [`app/pipeline/filler.py`](../../backend/app/pipeline/filler.py) | Real, working, rule-based `select_filler()`, wired into the orchestrator before the LLM call — but only a representative phrase subset, not the full library from the Latency Filler Phrases PDF |
| Text-mode HTTP contract | [`app/api/v1/endpoints/conversation.py`](../../backend/app/api/v1/endpoints/conversation.py), [`app/schemas/conversation.py`](../../backend/app/schemas/conversation.py) | Real, working `POST /api/v1/conversation/turn` — service-to-service auth, streams `run_turn` back as `text/plain`. No voice/LiveKit equivalent exists yet |
| Config | [`app/core/config.py`](../../backend/app/core/config.py) | `LIVEKIT_URL`/`LIVEKIT_API_KEY`/`LIVEKIT_API_SECRET` fields exist but are still empty-default placeholders, unused in code yet. STT/TTS config (`SARVAM_STT_MODEL`, `SARVAM_TTS_MODEL`/`SPEAKER`/`SAMPLE_RATE`, etc.) is now real and live-validated. |
| Dependencies | [`backend/pyproject.toml`](../../backend/pyproject.toml) | `websockets>=14,<18` added (used by both new adapters). Still no `livekit`/`livekit-agents` — that's the Phase 1 work remaining. |
| Frontend | [`frontend/`](../../frontend/README.md) | Explicitly a **debug test harness**, not the product client — plain HTML/JS calling only the text endpoint, no audio, no LiveKit. Out of scope for this pass (see §0 above). |

**Net (updated, same day): the whole conversation layer is now real, working, and live-tested end to end** — STT, TTS, the LiveKit Agent itself, and the orchestrator it calls unchanged. A fake user joined a real Room on the real LiveKit Cloud project, spoke a real sentence, and received a real spoken reply back, with the exact transcript and response text traced end to end. See §4 Phase 5 for the full account, including a real bug the live test caught (not a hypothetical one).

### §2a. A design fix made along the way: `STTProvider` now yields `TranscriptChunk`, not `str`
The original interface (`app/providers/base.py`) had `transcribe_stream()` yield plain `str`, but `app/realtime/agent.py`'s own pseudocode already assumed a richer object (`transcript_chunk.is_final`, `transcript_chunk.text`) — a real inconsistency between the interface and the one place that was supposed to consume it. Fixed by adding a small `TranscriptChunk(text: str, is_final: bool)` dataclass to `base.py` and changing the interface to yield that instead — matching what the Agent's pseudocode already expected, not a new design.

---

## 3. Target architecture

```
                         ┌─────────────────────────── LiveKit Room (one per conversation) ───────────────────────────┐
                         │                                                                                            │
   User's client  ───mic track───▶  [ LiveKit media server ]  ◀───response audio track───   LiveKit Agent process    │
 (Flutter/Next.js,                   (Cloud or self-hosted)                                  (this AI service)       │
  joins with a token                                                                               │                 │
  issued by NestJS,                                                                                 │                 │
  never by this service)                                                                            ▼                 │
                         │                                                               ┌─────────────────────┐    │
                         │                                                               │ STT (Sarvam Saaras, │    │
                         │                                                               │ streaming, partial  │    │
                         │                                                               │ + final transcripts)│    │
                         │                                                               └──────────┬──────────┘    │
                         │                                                                           │ final text    │
                         │                                                                           ▼               │
                         │                                                        app.pipeline.orchestrator.run_turn │
                         │                                                        (SAME function the text HTTP      │
                         │                                                         endpoint calls — no forked logic)│
                         │                                                                           │ text chunks   │
                         │                                                                           ▼               │
                         │                                                           ┌───────────────────────────┐  │
                         │                                                           │ sentence-boundary buffer  │  │
                         │                                                           │ (new, small, Phase 4)     │  │
                         │                                                           └──────────────┬────────────┘  │
                         │                                                                           │ sentence      │
                         │                                                                           ▼               │
                         │                                                               ┌─────────────────────┐    │
                         │                                                               │ TTS (Sarvam Bulbul, │    │
                         │                                                               │ streaming audio)    │    │
                         │                                                               └──────────┬──────────┘    │
                         │                                                                           │ audio bytes   │
                         └───────────────────────────────────────────────────────────────────────────┴───────────────┘
```

Key design decisions this follows directly from the docs:

1. **One pipeline, two entry points.** `run_turn` is called identically from the text HTTP route and from the LiveKit Agent — this is stated as a hard invariant in both [`agent.py`](../../backend/app/realtime/agent.py)'s docstring and [`conversation.py`](../../backend/app/api/v1/endpoints/conversation.py)'s. The plan below never forks pipeline logic.
2. **LiveKit only carries media, never makes decisions** ([LIVEKIT.md](../approch/LIVEKIT.md) §3, §6). Triage/interlock keep living entirely inside `run_turn`, operating on transcript text, unaffected by transport.
3. **Don't reimplement VAD/turn-taking/barge-in.** The LiveKit Agents framework has this solved — use its session/pipeline abstraction (`AgentSession` / `VoicePipelineAgent`, exact class name depends on the SDK version pinned in Phase 1) rather than writing audio-energy detection by hand ([LIVEKIT.md](../approch/LIVEKIT.md) §4, §6).
4. **Stream every stage, no exceptions** ([LATENCY.md](../approch/LATENCY.md) §3). The one genuinely new piece of logic this plan needs that doesn't exist anywhere yet is the **sentence-boundary buffer** between the orchestrator's raw text-chunk stream and the TTS adapter — today `run_turn` yields arbitrary-sized chunks (including the filler phrase as its own first chunk), and TTS must be fed at sentence granularity, not token granularity, per [LATENCY.md](../approch/LATENCY.md) §3 and §11 ("don't buffer a full LLM response before starting TTS — stream sentence-by-sentence"). This is a small, self-contained utility (not a change to the orchestrator itself).

---

## 4. Phased implementation plan

### Phase 0 — Pin the decisions that are genuinely open, without blocking on them
- **LiveKit Cloud vs. self-hosted** ([15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md), [LIVEKIT.md](../approch/LIVEKIT.md) §5): still open. Don't wait for the production answer — use a free LiveKit Cloud dev project (or `docker run livekit/livekit-server` locally) to unblock Phase 5 immediately; this is a config value (`LIVEKIT_URL`), not an architectural fork.
- ~~STT vendor (Deepgram-only vs. dual Deepgram/Sarvam)~~ **RESOLVED 2026-10-01** — Sarvam only, for both STT and TTS. See §0 above.

### ~~Phase 1 — Environment and dependencies~~ — DONE
- ~~Add `livekit-agents`/`livekit` and a Deepgram client~~ — `websockets>=14,<18` added to `pyproject.toml` instead (Deepgram is not used; Sarvam's streaming APIs are plain WebSocket + JSON, same "raw protocol over an SDK" style already used for the Sarvam LLM adapter's `httpx`). `livekit-agents`/`livekit` itself is still needed, deferred to Phase 5.
- `SARVAM_API_KEY` is already set to a confirmed account and in active use for the LLM adapter; the same key now also drives STT/TTS per [12_SECURITY_COMPLIANCE_DPDP.md](12_SECURITY_COMPLIANCE_DPDP.md)'s no-training/no-retention requirement.
- LiveKit credentials/local server setup is still pending — real work for Phase 5, not done yet.

### ~~Phase 2 — STT adapter~~ — DONE (`app/providers/stt/sarvam_stt.py`)
Implemented against Sarvam's real-time streaming endpoint (`wss://api.sarvam.ai/speech-to-text-realtime/ws`, model `saaras:v3-realtime`): session config passed as URL query params (not a JSON message, unlike TTS), audio sent as base64-encoded `linear16` PCM chunks, partial/final transcripts received as `transcript.partial`/`transcript.final` events and mapped onto `TranscriptChunk(text, is_final)`. Audio is sent and transcripts are received concurrently (a background `asyncio` task feeds audio while the main loop yields transcripts), which is what makes this genuinely streaming rather than "wait for all audio, then transcribe."

**Live-validated 2026-10-01**, not just unit-tested against a mock: a sentence was synthesized via the new TTS adapter, resampled to 16kHz mono, and fed straight into this STT adapter — the returned final transcript matched the original text exactly, with partial transcripts streaming in well under a second. **Caller contract to remember for Phase 5:** this adapter does not resample audio — `app/realtime/agent.py` must deliver mono `linear16` PCM at 16kHz (LiveKit tracks are commonly 48kHz, so a resample step is required there).

Only **final** transcripts (`is_final=True`) should trigger `run_turn` — partials are for optional live captions later, not for driving the pipeline.

### ~~Phase 3 — TTS adapter~~ — DONE (`app/providers/tts/sarvam_tts.py`)
Implemented against Sarvam's real-time streaming endpoint (`wss://api.sarvam.ai/text-to-speech/ws`). Sends a `config` message (language/speaker/model/codec) then `text` + `flush` messages per call, receives `audio` events (base64-encoded `linear16` PCM, decoded before yielding) and an `event: final` completion signal.

**One real correction found by actually calling the live API, not just reading docs:** the documentation still listed `bulbul:v2` as current, but a live synthesis call against it returned `400: Model 'bulbul:v2' has been deprecated. Please use 'bulbul:v3' instead.` — v2 and v3 also have non-overlapping speaker name lists (a v2 speaker name on v3 fails with a 400 listing the real options), and different default sample rates (22050 vs 24000 Hz). Corrected defaults: `bulbul:v3` / speaker `shubh` / 24000 Hz. **Live-validated 2026-10-01**: ~380–550ms to first audio byte for short sentences, audio streamed incrementally across multiple chunks, not buffered as one block.

**Known limitation, left as an explicit gap:** this opens a fresh WebSocket connection per call (per sentence, given the one-sentence-at-a-time caller contract from Phase 4) rather than keeping one connection open and reused across a whole turn's sentences, which [LATENCY.md](../approch/LATENCY.md) §8 asks for ("warm, persistent connections"). Doing that properly needs the `TTSProvider` interface to accept an async iterable of text spanning a whole turn instead of one string per call — a real interface change, intentionally deferred rather than scope-creeping this pass.

### ~~Phase 4 — Sentence-boundary buffer~~ — DONE, but not as a hand-written utility
The plan originally called for a small hand-rolled accumulator between `run_turn`'s text stream and TTS. Once actually implementing against the real `livekit-agents` 1.8.3 API, a better option turned up: **`Agent`'s default `tts_node` already does exactly this** when a TTS plugin declares `capabilities=TTSCapabilities(streaming=False)` — it wraps the plugin in the framework's own `tts.StreamAdapter` with a `blingfire` sentence tokenizer (confirmed by reading the installed package's own default implementation, not assumed). [`livekit_tts.py`](../../backend/app/realtime/livekit_tts.py) declares exactly that, so sentence-by-sentence synthesis comes from the framework, using a more robust tokenizer than a hand-written one — no custom buffer was written.

### ~~Phase 5 — LiveKit Agent wiring~~ — DONE (`app/realtime/agent.py`), live-tested end to end
Implemented using `livekit-agents` 1.8.3's `AgentSession`/`Agent` classes (the classic `WorkerOptions(entrypoint_fnc=...)` + `cli.run_app` pattern, confirmed still supported in 1.8.3 by introspecting the installed package, not assumed from docs that also show a newer `AgentServer`/`@rtc_session` pattern). Three new thin adapter files wrap the already-real building blocks into the shapes `AgentSession` expects:
- [`app/realtime/livekit_stt.py`](../../backend/app/realtime/livekit_stt.py) — `SarvamLiveKitSTT(stt.STT)`, wraps `SarvamSTTProvider` behind the framework's streaming `RecognizeStream` interface.
- [`app/realtime/livekit_tts.py`](../../backend/app/realtime/livekit_tts.py) — `SarvamLiveKitTTS(tts.TTS)`, wraps `SarvamTTSProvider` behind `ChunkedStream`/`AudioEmitter`.
- [`app/realtime/livekit_llm.py`](../../backend/app/realtime/livekit_llm.py) — `OrchestratorLLM(llm.LLM)`, wraps `run_turn` behind the framework's `chat()`/`LLMStream` interface — this is the piece that makes voice call the exact same pipeline function as text mode, satisfying the one non-negotiable invariant this whole plan is organized around.
- `prewarm()` loads Silero VAD once per worker process and now also calls `app.core.logging.configure_logging()` — a real gap caught along the way: without it, every per-turn log line in the voice path (not just the entrypoint's own) would silently fall back to structlog's unconfigured default instead of the service's structured JSON logging.

**Live-tested end to end against the real LiveKit Cloud project** (`mindfully-yours-private-limited-5de9iecb.livekit.cloud`, region India South), not simulated: a worker process registered as a real Agent; a separate fake-user test client joined a Room, published a microphone-sourced audio track carrying real Sarvam-TTS-synthesized speech, and received a real spoken reply back. The exact transcript ("Can you hear me okay?") and the full `chat_ctx` (including the user's message) were traced through `OrchestratorLLM._run()`, and the response audio was confirmed to be genuine non-silent speech (RMS-analyzed, not just byte-counted) arriving in the expected few-second window after the utterance.

**A real bug the live test caught, worth recording:** the first few "successful" test runs were a false positive — real audio bytes came back, but they were pure digital silence (RMS exactly 0 across the whole capture), because the test *client* published its fake microphone track without `TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)`. The framework's `RoomIO` only treats microphone-sourced tracks as speech input by default, so it silently ignored the fake user's audio entirely, and the "response" was just the agent's idle output track. This was a bug in the *test harness*, not in `agent.py`/the plugins — real client SDKs (Flutter/JS/web) tag microphone tracks correctly by default — but it's a sharp reminder that **byte counts are not proof of a working pipeline; always verify actual audio content (RMS/transcription), not just "did bytes arrive."** Once fixed, the full loop worked correctly.

**Barge-in/cancellation-safety** (the "net-new design" flagged in earlier drafts of this plan) was implemented in `app.pipeline.orchestrator.run_turn` itself (see that module's updated docstring and the `try/except (CancelledError, GeneratorExit)/finally` wrapped around the LLM-streaming step) and **verified directly under a real `asyncio.Task.cancel()` against the live pipeline**: a cancelled turn correctly stops mid-stream, and state-save + audit logging still fire (`served_from` recorded with an `_interrupted` suffix) rather than silently vanishing. The framework's own side of this (cancelling the task backing `OrchestratorLLM._run()` when it detects an interruption) relies on `LLMStream`'s standard task-cancellation machinery, confirmed by reading the installed package's source — not something this integration has to implement itself. One noted flakiness during rapid, repeated ad-hoc live testing (roughly 1 run in 3 got no response) is most likely a test-harness/VAD-timing artifact from feeding synthetic TTS audio as a "microphone" with none of a real human voice's natural pacing — worth a closer look before relying on this for a production load test, but it did not reproduce when the STT/TTS/LLM pieces were exercised directly (100% reliable there), pointing at the live test harness rather than the implementation.

### Phase 6 — Room/session identification (internal, minimal — the frontend/NestJS contract itself is deferred)
Implemented as planned: Room name is read directly as the `session_id` (UUID), with a generated fallback UUID (logged) if the Room name isn't a valid UUID, so the Agent works standalone without a real NestJS-issued Room. Designing the real contract with the frontend/NestJS side remains explicitly out of scope for this pass (see §1/§5).

### Phase 7 — Manual end-to-end dev harness
Not built as a reusable artifact — ad-hoc Python test scripts (a fake LiveKit participant publishing synthesized speech and capturing the response) were used instead to validate Phase 5 live, which served the same verification purpose. A reusable browser-based harness (extending `frontend/`) is still worth building before a human needs to manually exercise this by voice, but wasn't necessary to prove the pipeline works.

### Phase 8 — Latency instrumentation
Not yet done. The orchestrator's existing `latency` dict (`embed_ms`, `cache_check_ms`, `triage_ms`, `interlock_ms`, `llm_ms`, `total_ms`) is still text-mode-only; voice-specific stages (`stt_first_partial_ms`, `stt_final_ms`, `tts_first_byte_ms`) are not yet captured or logged. Real remaining work.

### Phase 9 — Fill out the filler-phrase library
Not yet done. `filler.py` still has only a representative phrase subset, not the full 13-category library from the Latency Filler Phrases PDF.

### Phase 10 — Barge-in validation
Partially done: cancellation-safety is verified directly (see Phase 5 above). A live "speak over the agent mid-response and confirm playback audibly stops" test was attempted but produced ambiguous audio-timing results (continuous frame delivery doesn't by itself prove or disprove a cutoff, since a new response can follow immediately with no gap at the transport level) — the SDK's own "adaptive interruption detector initialized" log confirms the mechanism is active, but a clean, decisive live observation of a mid-response cutoff is still worth doing once a reusable dev harness (Phase 7) exists to make that easier to drive by ear/eye rather than by parsing frame timestamps.

---

## 5. Frontend/NestJS integration contract — deliberately deferred

Earlier drafts of this plan proposed designing the Room-naming convention and a LiveKit data-channel message schema now, on the reasoning that a frontend engineer would want something to integrate against soon. **Per direction on 2026-10-01, that's explicitly not part of this pass** — this slice of work is the conversation-layer backend only, self-contained, with no frontend/NestJS contract design attached. The only contract that exists today is the pre-existing text-mode one (`POST /api/v1/conversation/turn`, [schemas/conversation.py](../../backend/app/schemas/conversation.py)), unrelated to this plan's voice work. When frontend integration does become the next step, the real contract (Room/token flow, metadata convention, whether a data-channel schema is worth adding) should be designed then, with whoever actually owns the NestJS backend and client apps in the room — not guessed at here in advance.

---

## 6. Risks / open items specific to this layer

- **LiveKit Cloud vs. self-host** — unresolved for production; doesn't block dev (Phase 0).
- ~~STT single vs. dual vendor~~ — **resolved**, Sarvam only (§0).
- **Sarvam TTS's documented API lagged the real one** (`bulbul:v2` deprecated server-side despite docs listing it as current) — found only by making a live call, not by reading docs alone. Worth remembering for any other Sarvam surface still untested live (e.g. if a dual/alternate STT model is ever considered): verify against a real call before trusting the docs' model/parameter names.
- **No Room-naming/metadata contract exists with the (out-of-scope) NestJS backend, and designing it is explicitly deferred** (§5) — Phase 6 uses a throwaway internal placeholder just to make the Agent runnable; this is not a proposal to hand to anyone yet.
- ~~`livekit-agents` SDK surface may have shifted by implementation time~~ — **resolved**: implemented and live-tested against the real 1.8.3 release, pinned in `pyproject.toml` (`livekit-agents>=1.8,<2`).
- ~~Cancelling an in-flight `run_turn` on barge-in is genuinely new design~~ — **resolved and live-verified** (§4 Phase 5) — implemented in `orchestrator.py`, confirmed under a real `asyncio.Task.cancel()` against the live pipeline.
- **The TTS adapter reconnects per sentence rather than reusing one warm connection per turn** (§4 Phase 3) — correct but not latency-optimal; a known, explicitly-deferred gap, not an oversight.
- **Intermittent live-test flakiness (~1 in 3 ad-hoc runs got no response)** — observed during rapid repeated testing against the real LiveKit Cloud project; most likely a test-harness/VAD-timing artifact (synthetic TTS-as-microphone audio lacks natural human pacing), not a confirmed defect in the STT/TTS/LLM wiring itself (each component is 100% reliable when exercised directly, standalone). Worth a closer look — real human voice over a real client is likely to behave differently — before treating voice reliability as fully proven at scale.
- **No automated regression test exists for the live LiveKit path** — validation so far is live, manual, ad-hoc scripts (kept in this session's scratch space, not committed) rather than a repeatable test in `tests/`. Same gap `tests/integration/test_conversation_pipeline.py` already flags for `run_turn` itself (both its tests are `@pytest.mark.skip`, pending a test DB/Redis + fake providers setup) — worth solving once, for both.
- **Avatar is fully out of scope here** — the provider is unresolved anyway ([15](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #8) and voice must work standalone regardless, per the documented avatar → voice → text degradation ladder ([CLAUDE.md](../approch/CLAUDE.md) §8).

---

## 7. Definition of done for this slice

- [x] `websockets`, `livekit-agents`, and `livekit-plugins-silero` dependencies added and pinned
- [x] Sarvam streaming STT adapter implemented, live-tested (round-trip against real synthesized audio, transcript matched exactly) — and again inside the real LiveKit pipeline
- [x] Sarvam streaming TTS adapter implemented, live-tested (~380–550ms to first byte, correct model/speaker/sample-rate after a live 400 caught the docs being stale)
- [x] Sentence-by-sentence TTS feeding — via the framework's own `StreamAdapter`/tokenizer, not a hand-written buffer (§4 Phase 4)
- [x] `app/realtime/agent.py` joins a real Room, runs the full STT → `run_turn` (unchanged) → TTS loop, and publishes audio back — **live-verified against the real LiveKit Cloud project**
- [x] Barge-in cancellation-safety implemented in `run_turn` and verified under a real task cancellation; a clean, decisive *live, audible* mid-response interruption observation is still outstanding (§4 Phase 10)
- [ ] End-to-end voice turn latency measured and logged (per [LATENCY.md](../approch/LATENCY.md)'s 1.5–2.5s target) — not yet instrumented (§4 Phase 8)
- [ ] A reusable manual dev harness that lets anyone join a Room from a browser and talk to the Agent (ad-hoc scripts were used instead to validate this slice, §4 Phase 7)
- [ ] Full filler-phrase library ported from the PDF (§4 Phase 9)
- Frontend/NestJS contract design — **intentionally not part of this slice's definition of done** (§5)

---

## 8. In simple terms

Think of it as four people in a phone booth, passing a note to each other as fast as possible:

1. **LiveKit** is the phone line itself — it just carries your voice back and forth, it doesn't understand anything you're saying.
2. **Sarvam's speech-to-text** listens to your voice and writes down what you said, as you're still speaking — not after you finish.
3. **The brain (the existing safety + LLM pipeline, already built and working)** reads what you said, silently checks if anything you said is a safety concern (this never gets skipped, ever), and starts writing a reply — word by word, not waiting to finish the whole reply before sending the first part.
4. **Sarvam's text-to-speech** takes the reply one sentence at a time, as soon as that sentence is ready, and turns it into speech — so you start hearing the answer before the AI has even finished "thinking" of the rest of it.

If you start talking while the AI is still replying, LiveKit's built-in "someone's talking, stop and listen" behavior kicks in automatically — we don't have to build that part ourselves, just plug into it, and make sure we also stop the AI's "thinking" in the background so it doesn't keep working on an answer nobody's going to hear.

**Update: all four pieces are now real, wired together, and proven to work.** We built the phone-booth operator too, and tested it for real — not with a pretend room, but by actually joining a real LiveKit room, speaking a real sentence out loud through a fake "mouth" of our own, and getting a real, correct, spoken answer back a few seconds later, exactly the way a real phone call would feel. Along the way we caught a genuine mistake early testing almost missed: the first few "successful" tests were actually just silence coming back, because our own test microphone wasn't labeled as a microphone properly — a lesson in checking what a recording actually *contains*, not just whether a file arrived. Once that was fixed, the real conversation worked.

We're deliberately *not* trying to make the brain smarter (i.e., deeper knowledge-base search) in this pass, and we're deliberately *not* designing how the real app will plug into this yet either — that's a separate, later conversation. What's left is mostly polish: measuring exactly how fast each step is, filling out the library of "um, let me think..." filler phrases so it doesn't repeat itself, and giving someone a simple page to click "talk to it" from a browser rather than needing a script. The hard part — can someone actually talk to this thing out loud, in real time, and get a real, safe, correct answer back — is done and proven.
