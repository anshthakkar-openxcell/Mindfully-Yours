# 10 — LiveKit Real-Time Transport

> LiveKit isn't a single component — it's the real-time transport layer running underneath three different parts of the system (AI Companion, practitioner consultations, SOS calls), each using it slightly differently.
>
> **Scope note**: per [14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md](14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md) Epic G, only **§3's "AI Companion" subsection is in scope** for this build — the LiveKit Agent process that joins a Room and feeds audio through the AI pipeline. Practitioner consultations, SOS calls, and Egress recording (§3's other subsections) are NestJS/infra responsibilities, described here only so the AI service's boundary (it joins Rooms, it never creates them) is unambiguous.

## 1. Why LiveKit, in one sentence

It replaces two separate real-time needs — the AI Companion's voice/avatar loop, and human-to-human practitioner/SOS calling (originally scoped as **Agora/Daily/Twilio** in the signed business proposal) — with **one** technology, built on WebRTC, which is inherently lower-latency than HTTP-based approaches for continuous audio (a direct, persistent, UDP-based connection rather than repeated request/response calls). **This is a well-justified change but must be explicitly communicated to the client as a technology-review recommendation, not silently swapped into delivery** — per Clause 2.8, see [12_SECURITY_COMPLIANCE_DPDP.md](12_SECURITY_COMPLIANCE_DPDP.md) §2.

## 2. Core concepts

- **Room** — a real-time session container. Every AI Companion conversation, every practitioner consultation, and every SOS call is its own Room.
- **Participant** — anyone or anything publishing/receiving media in a Room. A user is a participant; the AI itself is also a participant — a server-side one.
- **Track** — a single audio or video stream published into a Room (a user's mic, the AI's synthesized voice, the avatar's video).
- **LiveKit Agents framework** — a purpose-built SDK for exactly this STT → LLM → TTS voice pipeline. It handles voice-activity detection, turn-taking, and interruption (barge-in) — this plugs into the existing pipeline, it doesn't replace any part of it.
- **Egress** — LiveKit's built-in recording feature, capable of writing directly to S3.
- **Token-based access** — each participant joins a Room with a signed token scoped to exactly that Room, enforcing that a user can only ever join their own session.

## 3. How each part of the system uses it

### AI Companion (voice/avatar mode)
The user's mic audio is published as a track into a Room. A **LiveKit Agent** (server-side participant representing the AI) subscribes to that track and feeds it through the existing pipeline exactly as designed: Deepgram/Sarvam for STT, RAG + triage + interlock + LLM for the response, Sarvam TTS for voice, and the avatar renderer (HeyGen or 2-D fallback — see [03_TECH_STACK.md](03_TECH_STACK.md) for the vendor discrepancy) for lip-synced video. The result is published back into the same Room as an outgoing track. **LiveKit only carries the media — it makes no decisions.** Triage, the safety interlock, and grounding remain entirely separate application logic, receiving the transcript text from the Agent exactly as they would in any other transport.

### Text-only conversations
**Don't route text-only chat through LiveKit.** No continuous audio/video to carry, so a Room and WebRTC transport add complexity for no latency benefit. Keep text mode on a simple API/WebSocket call — LiveKit is specifically for voice and avatar modes.

### Practitioner consultations
A Room is created per booked session. User and practitioner each join with a token scoped only to that Room — a standard two-party WebRTC call, no AI Agent participant involved.

### SOS / crisis calls
Same Room-per-session model, user plus the client's on-shift crisis team. **This is the single most latency- and reliability-sensitive use of LiveKit in the whole system** — connection speed and stability matter more here than anywhere else, because of what's at stake in the moment.

### Recording, transcription & summaries
LiveKit **Egress** records the Room directly to S3 — the input to the transcription + AI-assisted summary pipeline already scoped for practitioner sessions. **Only record practitioner and SOS calls, not every AI Companion turn** — recording every Companion conversation by default would be a real, unnecessary storage cost with no product requirement behind it.

## 4. What to get right for latency specifically

- **Co-locate everything**: the LiveKit media server, the AI service, and the Sarvam/Deepgram endpoints should sit as close together as possible — ideally the same region as AWS ap-south-1 infrastructure. Every region boundary crossed adds a real, avoidable hop (per [09_LATENCY_AND_PERFORMANCE.md](09_LATENCY_AND_PERFORMANCE.md) §9).
- **Run the Agent in the same region as the Room it's serving** — if the Agent process is far from the LiveKit media server, you've reintroduced a network hop between the AI and the audio it's processing in real time.
- **Use LiveKit's built-in interruption handling, don't build your own.** Barge-in is a solved problem in the Agents framework.
- **Let avatar video degrade before audio does.** LiveKit supports adaptive bitrate/simulcast — on a weak connection, video quality should drop before responsiveness does. Voice is the priority; avatar is the enhancement.
- **The filler-words latency-masking technique still applies** ([09_LATENCY_AND_PERFORMANCE.md](09_LATENCY_AND_PERFORMANCE.md) §4) — LiveKit doesn't remove the need for it, it just gives a lower-latency pipe to deliver it through.

## 5. Decisions that still need to be made explicitly, not assumed

- **Self-hosted vs. LiveKit Cloud.** Self-hosting means backend/DevOps capacity has to run and maintain media servers — real ongoing operational load for a small team. LiveKit Cloud is managed but becomes a new recurring, usage-based cost line, the same way Agora/Daily/Twilio would have been.
- **DPDP data residency.** If using LiveKit Cloud, confirm exactly where call data and recordings physically reside — don't assume it matches the configured region without checking. Self-hosting keeps this fully within control by hosting in AWS ap-south-1.
- **This replaces a shortlist named in the signed business proposal.** Communicate the change explicitly at the technology review.

## 6. What NOT to do

- Don't route text-only conversations through a LiveKit Room.
- Don't let LiveKit's transport layer become a place where safety logic accidentally lives — triage and the interlock operate on transcript text, entirely outside of and unaffected by how the audio got there.
- Don't record every AI Companion conversation by default.
- Don't assume LiveKit Cloud's nearest region is good enough without checking it against AWS ap-south-1 specifically.
- Don't build custom interruption/turn-taking logic when the Agents framework already solves it.

---
*Source material: `documnets/approch/LIVEKIT.md` (full).*
