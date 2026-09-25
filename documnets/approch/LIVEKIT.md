# Mindfully Yours — LiveKit Integration Guide

Companion reference to `APPROACH.md`, `CLAUDE.md`, `LATENCY.md`, and `INGESTION.md`. This file exists because LiveKit isn't a single component — it's the real-time transport layer running underneath three different parts of the system (the AI Companion, practitioner consultations, and SOS calls), and each one uses it slightly differently.

---

## 1. Why LiveKit, in one sentence

It replaces two separate real-time needs — the AI Companion's voice/avatar loop, and human-to-human practitioner/SOS calling (originally scoped as Agora/Daily/Twilio) — with **one** technology, and it's built on WebRTC, which is inherently lower-latency than HTTP-based approaches for continuous audio, because it's a direct, persistent, UDP-based connection rather than repeated request/response calls.

---

## 2. The core concepts, in plain terms

- **Room** — a real-time session container. Every AI Companion conversation, every practitioner consultation, and every SOS call is its own Room.
- **Participant** — anyone or anything publishing or receiving media in a Room. A user is a participant. The AI itself is also a participant — a server-side one, not a human.
- **Track** — a single audio or video stream published into a Room (a user's mic, the AI's synthesized voice, the avatar's video).
- **LiveKit Agents framework** — a purpose-built SDK for exactly this kind of STT → LLM → TTS voice pipeline. It handles voice activity detection, turn-taking, and interruption (barge-in) — this is what plugs into your existing pipeline, not a replacement for any part of it.
- **Egress** — LiveKit's built-in recording feature, capable of writing directly to S3.
- **Token-based access** — each participant joins a Room with a signed token scoped to exactly that Room, which is what enforces that a user can only ever join their own session.

---

## 3. How each part of the system uses it

### The AI Companion (voice/avatar mode)
The user's microphone audio is published as a track into a Room. A **LiveKit Agent** — a server-side participant representing the AI — subscribes to that track and feeds it through the existing pipeline exactly as already designed: Deepgram/Sarvam for STT, the RAG + triage + interlock + LLM pipeline for the response, Sarvam TTS for the voice, and Spatius.ai for lip-synced avatar video. The result is published back into the same Room as an outgoing track, and the user's client plays it. **LiveKit only carries the media — it makes no decisions.** Triage, the safety interlock, and grounding all remain entirely separate application logic, receiving the transcript text from the Agent exactly as they do today.

### Text-only conversations
**Don't route text-only chat through LiveKit.** There's no continuous audio/video to carry, so a Room and WebRTC transport add complexity for no latency benefit. Keep text mode on a simple API/websocket call, as already scoped — LiveKit is specifically for the voice and avatar modes.

### Practitioner consultations
A Room is created per booked session. The user and the practitioner each join with a token scoped only to that Room. This is a standard two-party WebRTC call — no AI Agent participant involved.

### SOS / crisis calls
Same Room-per-session model, user plus the client's on-shift crisis team. This is the single most latency- and reliability-sensitive use of LiveKit in the whole system — connection speed and stability here matter more than anywhere else, because of what's at stake in the moment.

### Recording, transcription & summaries
LiveKit **Egress** records the Room directly to S3. This recording is the input to the transcription + AI-assisted summary pipeline that's already scoped for practitioner sessions — LiveKit doesn't change that pipeline, it just becomes the source of the recording. **Only record practitioner and SOS calls, not every AI Companion turn** — recording every Companion conversation by default would be a real, unnecessary storage cost with no product requirement behind it.

---

## 4. What to get right for latency specifically

- **Co-locate everything.** The LiveKit media server (self-hosted or the nearest LiveKit Cloud region), the AI service, and the Sarvam/Deepgram endpoints should all sit as close together as possible — ideally the same region as your AWS ap-south-1 infrastructure. Every region boundary crossed adds a real, avoidable hop, exactly as `LATENCY.md` already warns about for any provider call.
- **Run the Agent in the same region as the Room it's serving.** If the Agent process itself is far from the LiveKit media server, you've reintroduced a network hop between the AI and the audio it's supposed to be processing in real time.
- **Use LiveKit's built-in interruption handling, don't build your own.** Barge-in (the user interrupting the AI mid-response) is a solved problem in the Agents framework — use it rather than reimplementing voice-activity detection from scratch.
- **Let avatar video degrade before audio does.** LiveKit supports adaptive bitrate/simulcast — on a weak connection, video quality should drop before the conversation's responsiveness does. Voice is the priority; avatar is the enhancement, consistent with the existing "avatar is opt-in, cost/latency-gated" principle.
- **The filler-words latency-masking technique still applies here** — LiveKit doesn't remove the need for it, it just gives you a lower-latency pipe to deliver it through.

---

## 5. Decisions that still need to be made explicitly, not assumed

- **Self-hosted vs. LiveKit Cloud.** Self-hosting means your backend/DevOps capacity has to run and maintain media servers — real ongoing operational load for a 4-person team. LiveKit Cloud is managed, but becomes a new recurring, usage-based cost line, the same way Agora/Daily/Twilio would have been.
- **DPDP data residency.** If using LiveKit Cloud, confirm exactly where call data and recordings physically reside — don't assume it matches your configured region without checking. If self-hosting, this is fully within your control by hosting in AWS ap-south-1.
- **This replaces a shortlist named in the signed business proposal** (Agora/Daily/Twilio). It's a well-justified change, but it should be explicitly communicated to the client as a technology-review recommendation, not silently swapped into delivery.

---

## 6. What NOT to do

- Don't route text-only conversations through a LiveKit Room — that's solving a problem that doesn't exist for that mode.
- Don't let LiveKit's transport layer become a place where safety logic accidentally lives — triage and the interlock operate on the transcript text, entirely outside of and unaffected by how the audio got there.
- Don't record every AI Companion conversation by default — only practitioner and SOS calls need Egress-based recording.
- Don't assume LiveKit Cloud's nearest region is good enough without checking it against AWS ap-south-1 specifically — "close" and "same region as everything else in this system" aren't automatically the same thing.
- Don't build custom interruption/turn-taking logic when the Agents framework already solves it — that's reinventing a well-tested wheel for no benefit.

---

*Companion file to `APPROACH.md`, `CLAUDE.md`, `LATENCY.md`, and `INGESTION.md` — derived from the finalized Mindfully Yours architecture (OpenXcell Technolabs Pvt. Ltd. / Mindfully Yours Private Limited). Keep all five files in sync if any decision here changes.*
