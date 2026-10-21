# 33. Client Drop #2 — what arrived, what it became, how it's used

**Date:** 2026-10-09. Source: `documnets/new uploaded documents/` (3 password-protected Word files + 1 Excel; decrypted copies in `decrypted/`, also copied to `documnets/Knowledge Base Source Files/5_Client_Drop_2/`). The password was supplied by the client and is intentionally **not** recorded anywhere in the repo.

Load everything with one command (idempotent):
`python -m app.ingestion.cli ingest-client-drop-2 --drop-dir "documnets/new uploaded documents/decrypted"`

## What each file became

| File | What it is | Became | Rows |
|---|---|---|---|
| `Copy of Situational Routing.xlsx` | 137 everyday situations in ~13 groups; for each: what Tier 1 / 2 / 3 looks like, plus a therapist-written self-care strategy | `kb_situational_routing` (situation embedded) **and** each strategy → `kb_content_chunks` (`self_care_tool`, tier 1) | 137 situations; **125 self-care chunks** (12 situations have no strategy — left empty, not invented) |
| `AI WELCOME RESPONSES.docx` | The therapists' opening messages ("Hi user, what's on your mind today?") | `kb_welcome_responses` | 24 (23 approved; 1 — "thank you for sharing this with me" — isn't a greeting, so it's held) |
| `Best Conversations- Final.docx` | The team's best "User / AI" dialogues | `kb_therapist_turns`, flagged `is_preferred` | 236 pairs |
| `Conversations With AI Companion.docx` | Casual "AI companion" chats (everyday stuff, emotional discussions) | `kb_therapist_turns` | 196 pairs |

Parser additions: speaker labels `Female` (user side) and `AI Companion` (AI side) are now recognised.

## Results (loaded into the dev DB)
- `kb_therapist_turns`: **6,440 rows, 5,230 approved** (all match-eligible rows approved per the 2026-10-09 decision; held rows — crisis/Tier 3, too-short, stray-heading, governance — stay unapproved). 236 rows flagged `is_preferred` (a tie-breaker at match time).
- Self-care chunks: `kb_content_chunks` went from **5 → 130**. This is the first time the Tier 1 recommendation step ([04](04_CONVERSATION_PIPELINE.md) Step F) has real therapist content to search.

## It already changes live behaviour — and was checked
`search_self_care_content` was already wired in; adding rows is enough. Tested against the live function with 7 messages: the top result was the correct situation for all of them ("laid off" → *Losing a job*, "failed my exam" → *Failing an exam*, "boss keeps yelling" → *Toxic boss*, "worrying about money" → *Fear of the future financially*, "interview tomorrow" → *Job interview stress*, "lonely, new city" → *Moving to a new city and feeling alone*). An off-topic message ("weather today") returned only 1 weak match (*Weather / heat / monsoon disruption* — arguably correct). The existing confidence threshold (0.30) is permissive, and the orchestrator uses only the top chunk, so calibrate that threshold in step 7 of [32](32_THERAPIST_FIRST_RESPONSE_APPROACH.md).

## Not done yet (deliberately)
1. ~~Welcome messages are stored but not served.~~ **Done 2026-10-09 — see the section below.**
2. **Situational Routing's tier wording is stored, not used for routing.** It has its own Tier 1/2/3 definitions (Sheet2 states them generally) that must be reconciled with the existing routing rules and the tier-scoring logic first — [15](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #25 — before it can change any tier decision. Tier 3 text is extra input for the red-flag review, never a replacement for the verbatim red-flag scripts.
3. **The AI Companion chats are everyday conversation, not wellness support.** They are loaded and approved like the rest, but a casual reply could be matched to a user in distress if the match threshold is loose. Crisis messages are still caught first by the interlock, and step 7 calibration should be run with these in the set. If the product treats "companion chat" as a separate mode, give them their own tag/filter — one UPDATE on `kb_therapist_turns` holds them.
4. ~113 replies that already existed from drop 1 and also appear in Best Conversations now list Best Conversations as their source file.

## Files added or changed
`app/db/models/kb_convo_content.py` (+`KBWelcomeResponse`, `KBSituationalRouting`, `is_preferred`) · migration `b7d2f4a18c33` · `parsers/welcome_responses.py`, `parsers/situational_routing.py` · `parsers/therapist_turns.py` · `cli.py` (`ingest-client-drop-2`; therapist-turn upsert now keeps original `source_file` and ORs `is_preferred`) · tests: `test_client_drop_2_parsers.py`, 2 new cases in `test_therapist_turns_parser.py` (34 unit tests pass).


## Update 2026-10-09 — welcome messages are now served
- [welcome.py](../../backend/app/pipeline/welcome.py): picks a random approved welcome message and fills the name slot ("Hi user, …" → "Hi Asha, …", or "Hi there, …" when the name is unknown — never the literal word "user"). No LLM, no embedding; one tiny query. If the table is empty or the lookup fails it falls back to a neutral greeting, so a conversation never fails to open.
- **Text mode:** new endpoint `POST /api/v1/conversation/welcome` (service auth + `consent_verified`, same contract as a turn) — the NestJS side calls it once when a conversation starts. Confirmed registered in the OpenAPI schema; the picker was run against the real DB (names filled, random choice varies).
- **Voice mode:** [agent.py](../../backend/app/realtime/agent.py) speaks a welcome right after the session starts (interruptible, best-effort — a failure is logged and never breaks the session). **Not live-tested** against a real LiveKit room; only the import and the `AgentSession.say` signature were checked.
- Not yet done: the debug harness in `frontend/` doesn't call the endpoint; the spoken welcome isn't added to the conversation memory, so the LLM doesn't "remember" having greeted.
- The therapist-first matching that uses the new dialogues is described in [32 §8](32_THERAPIST_FIRST_RESPONSE_APPROACH.md).
