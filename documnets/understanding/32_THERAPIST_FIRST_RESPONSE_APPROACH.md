# 32. Therapist-First Response Approach — build plan

**Status:** Steps 1–4 are BUILT and tested end to end (data §7, matching + orchestrator + enforcing guardrail §8). Not built: Step 5 (reply variety), Step 6 (gap queue — see §8 for why), Step 7 (therapist-labelled calibration — thresholds are provisional). Written 2026-10-07 in response to the client's question that replies must come from the therapist team's conversation library, not from the LLM, whenever a similar conversation exists.

**Read this first — two non-negotiable gates.** The approach below is only acceptable if it passes BOTH. If a design choice below ever conflicts with a gate, the gate wins.

---

## 0. The two gates (these outrank everything else in this doc)

### Gate 1 — It must NOT add latency
Target stays **1.5–2.5s end of speech → start of response** ([09](09_LATENCY_AND_PERFORMANCE.md)).

| Rule | Why |
|---|---|
| **No new embedding call.** Reuse the one `query_embedding` already computed in `run_turn` ([orchestrator.py](../../backend/app/pipeline/orchestrator.py)). | An embedding call is ~300–400ms (network). A second one would eat the budget. |
| **No extra LLM call to decide anything** (no "judge" or "router" LLM). Match decisions are vector distance + thresholds only. | An LLM call costs hundreds of ms. |
| **Retrieval is one indexed pgvector query**, run concurrently with triage/interlock where possible (`asyncio.gather`). Budget: **≤ 30ms p95**. | Must be invisible next to the LLM. |
| **HNSW index required** on the new table's embedding column. No sequential scans. | Without it the query degrades as the library grows. |
| **A strong match must skip the LLM entirely.** | This is where the approach *saves* time. |
| **No-match turns must cost the same as today ± the retrieval query.** | The fallback path must not get slower. |
| **Measure it:** log `curated_match_ms` in the existing `latency` dict and the audit log. | Never guess where time goes ([09](09_LATENCY_AND_PERFORMANCE.md) §2). |

**Acceptance:** p95 `curated_match_ms` ≤ 30ms; p95 total turn on no-match turns ≤ today's baseline + 30ms; p50 time-to-first-token on strong-match turns below today's.

### Gate 2 — It must make the product more accurate, not just "more therapist-flavoured"
A wrong therapist reply served word for word is *worse* than an LLM reply, because it looks authoritative. So:

| Rule | Why |
|---|---|
| **Safety is untouched and always first.** Triage + interlock run before the curated match and can override it ([08](08_SAFETY_INTERLOCK_AND_TRIAGE.md)). | Principle #2 of the project. |
| **Strict, data-calibrated thresholds.** Verbatim is served only above a high-confidence cutoff, set from a therapist-labelled test set, never guessed. | Today's thresholds are explicitly unvalidated. |
| **Match on conversation context, not one message** (last 2–3 turns + detected emotion + layer + tier). | A single sentence like "I'm tired" matches almost anything. |
| **The LLM may only rephrase therapist text, never add advice.** Grounding guardrail becomes enforcing, not log-only. | Otherwise "adapted" quietly becomes "LLM-authored". |
| **Prefer a therapist clarifying question over a wrong answer.** | Asking is always safer than guessing. |
| **Every reply carries its source** (`therapist_verbatim` / `therapist_adapted` / `therapist_clarify` / `llm_fallback`) and the conversation ID. | Auditable, and lets us measure accuracy per path. |

**Acceptance (measured on the labelled set before launch):** precision of the *strong* band ≥ 95% (therapists judge the served reply as appropriate); zero safety regressions on the red-flag test set; every `llm_fallback` turn logged to the gap queue.

---

## 1. The flow (per turn)

```
user text
  │
  ├─ [existing] one embedding → triage → tier score → INTERLOCK   (unchanged, always first)
  │         │
  │   interlock triggered? ──yes──▶ verbatim red-flag script. STOP.
  │
  ├─ [NEW] curated match  (one pgvector query on the SAME embedding, context-aware)
  │         │
  │         ├─ STRONG   (distance ≤ T_strong)  → therapist reply as written       [no LLM]
  │         ├─ PARTIAL  (T_strong < d ≤ T_weak) → LLM rephrases ONLY that text     [small prompt]
  │         ├─ WEAK/NONE                        → therapist clarifying question    [no LLM]
  │         └─ still unclear after N clarifications → LLM fallback (constrained)   [flagged → gap queue]
  │
  └─ [existing] guardrail → save state → cache → audit log (now with source + conversation_id)
```

Existing paths stay as they are: red-flag scripts (verbatim), Tier-1 self-care RAG (`kb_content_chunks`), tier-redirect guidance. The curated match slots in **after the interlock and before prompt assembly** (step 8), and takes priority over the generic probing guidance.

---

## 2. What to build (in order)

### Step 1 — Data: a therapist conversation-turn table (the real prerequisite)
Today's tables (`kb_layer_content`, `kb_tier_question_bank`, …) are *question/phrase banks*, not "situation → therapist reply" pairs, and nothing at runtime searches them. Add `kb_therapist_turns`:

| Column | Notes |
|---|---|
| `id`, `conversation_id`, `turn_index` | trace back to the source conversation |
| `context_text` | the user turn(s) that preceded the reply — **this is what gets embedded** |
| `reply_text` | therapist-written reply, served as written |
| `scenario`, `emotion`, `tier`, `layer` | filters + sanity checks (reconcile vocabulary first: [15](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #23, #25) |
| `author`, `source_file`, `version`, `approved` (bool) | only `approved = true` rows are ever served |
| `context_embedding` Vector + **HNSW index** | Gate 1 |
| `language` | `en` for Phase 1 ([13](13_LANGUAGE_PHASING.md)) |

Source: the Sept 2026 dialogue files (Anam, Tanisha, Ankita, Shreya, `Convo_Samples`, topic conversations — see [18](18_NEW_CONVO_DATA_CATALOG.md), [19](19_DATA_USAGE_MAP.md)). Needs a new parser in `app/ingestion/parsers/` that splits each dialogue into (preceding user turns → therapist reply) pairs. Skip incomplete/locked files and unresolved placeholders (`[technique]`) rather than guessing. Pause content flagged in [15](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #26.

### Step 2 — Retrieval function
`app/pipeline/curated_match.py`:
- Build the query from the **current embedding** (reuse — Gate 1). If context-aware matching needs a blended vector, blend the already-stored embeddings of the last turns with the current one; do **not** make a new embedding call.
- One query: `WHERE approved AND language = :lang ORDER BY cosine_distance LIMIT 3`, optionally pre-filtered by detected `tier`/`layer`.
- Return `(reply, distance, conversation_id, band)`.
- Run concurrently with the interlock/triage `await`s where the data dependencies allow; the interlock result still gates serving.

### Step 3 — Orchestrator branch
In `run_turn`, after the interlock-triggered return and before prompt assembly:
- `STRONG` → `yield reply_text`, record state, audit with `served_from="therapist_verbatim"`. No LLM.
- `PARTIAL` → build a **minimal** prompt: persona + the therapist reply + the user message + "rephrase only, add nothing". Run the enforcing guardrail on the output; on failure, serve the verbatim therapist reply instead.
- `WEAK/NONE` → serve a clarifying question from `kb_clarification_phrases` / the "Questions When AI Is Not Sure" bank (already ingested and embedded).
- Else → today's LLM path, constrained, with `served_from="llm_fallback"`.

### Step 4 — Make the guardrail enforcing
`check_grounding` ([guardrail.py](../../backend/app/pipeline/guardrail.py)) currently only logs ([orchestrator.py](../../backend/app/pipeline/orchestrator.py), step 11). For PARTIAL, a failed check must fall back to the verbatim therapist text.

### Step 5 — Variety (so verbatim isn't robotic)
Vary only the opening/closing connector sentence (small rule-based lookup, like `filler.py`). Never change the clinical content. Slot-fill only whitelisted placeholders.

### Step 6 — Gap queue + reporting
Every `llm_fallback` / `therapist_clarify` turn writes (user context, best distance, nearest conversation) to a review table. The therapists write new conversations from it; ingestion adds them. Dashboard: % of replies per source, top-used conversations, gap list.

### Step 7 — Calibration (do this BEFORE launch, and before trusting any threshold)
1. Therapists label ~100–200 real/synthetic messages: for each, which library reply fits, or "none fits".
2. Sweep `T_strong` / `T_weak` against the labels; pick the strong cutoff for ≥ 95% precision (Gate 2), then maximise coverage within it.
3. Re-run on every library update; thresholds are config (`.env`), not code.
4. Run the red-flag regression set to prove zero safety change.

---

## 3. Files touched

| File | Change |
|---|---|
| `backend/app/db/models/kb_convo_content.py` (or new model file) + Alembic migration | `kb_therapist_turns`, HNSW index, gap-queue table |
| `backend/app/ingestion/parsers/therapist_turns.py` + `cli.py` | dialogue → turn-pair parser and embed/load |
| `backend/app/pipeline/curated_match.py` | new — the one query + banding |
| `backend/app/pipeline/orchestrator.py` | new branch, new `served_from` labels, `curated_match_ms` latency key |
| `backend/app/pipeline/guardrail.py` | enforcing mode for PARTIAL |
| `backend/app/pipeline/prompt_builder.py` | minimal "rephrase-only" prompt variant |
| `backend/app/core/config.py` / `.env.example` | `CURATED_STRONG_THRESHOLD`, `CURATED_WEAK_THRESHOLD`, `CURATED_CLARIFY_LIMIT` |
| `backend/app/workers/audit_writer.py` | store `conversation_id` + source |

---

## 4. Risks and what we say honestly

- **Coverage drives the benefit.** With a thin library most turns fall to clarify/fallback. The approach pays off as the library grows; the gap queue is how it grows.
- **Wrong strong match.** Mitigated by Gate 2 thresholds, tier/layer filters and the labelled set — not by hope.
- **Repetition** in long chats — Step 5 mitigates it; watch it in testing.
- **Voice transcripts** differ from typed text; matching is by meaning, but test with real STT output.
- **Vocabulary conflicts** (emotion lists, Layer vs Tier vs Severity) must be reconciled before tagging is trustworthy ([15](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #23, #25).
- **Index gap:** confirm the embedding columns are indexed; none were found in the model definitions when this doc was written.

## 5. Decisions needed from the client

1. Is word-for-word reuse always preferred, or is light adaptation fine on partial matches?
2. On no-match: always ask a therapist clarifying question first, or is a constrained LLM reply acceptable?
3. Who on the therapist team labels the calibration set, and how soon?

## 6. Definition of done

- [ ] Both gates' acceptance criteria measured and met (not assumed)
- [ ] `kb_therapist_turns` populated from the approved dialogue files, HNSW-indexed
- [ ] Curated match wired after the interlock; safety regression set shows no change
- [ ] Thresholds set from the therapist-labelled set, strong-band precision ≥ 95%
- [ ] Guardrail enforcing on the adapted path
- [ ] Every turn logged with its source; gap queue and source-share report working

---

## 7. Implementation status — Step 1 (ingestion) DONE, 2026-10-08

### What was built
| Piece | Where |
|---|---|
| Table `kb_therapist_turns` (+ model `KBTherapistTurn`) | [kb_convo_content.py](../../backend/app/db/models/kb_convo_content.py) |
| Migration with a **partial HNSW index** (`WHERE approved AND match_eligible`) | [a3c1e7d09b52_add_kb_therapist_turns.py](../../backend/alembic/versions/a3c1e7d09b52_add_kb_therapist_turns.py) — applied to the dev DB |
| Dialogue parser (User/AI files → reply pairs) | [therapist_turns.py](../../backend/app/ingestion/parsers/therapist_turns.py) |
| CLI: `python -m app.ingestion.cli ingest-therapist-turns --convo-dir "<…>/decrypted/MYPL - Mindfully Yours Work"` (`--dry-run`, `--no-embed`, `--approve-eligible`) | [cli.py](../../backend/app/ingestion/cli.py) |
| Optional `timeout` on the OpenAI embedding client (runtime default stays 3.0s) | [openai_embeddings.py](../../backend/app/providers/embeddings/openai_embeddings.py) |
| 5 parser tests (one per real bug found) | [test_therapist_turns_parser.py](../../backend/tests/unit/test_therapist_turns_parser.py) |

### What the real data produced (all dialogue files in the Sept drop)
- **6,121 unique pairs** (user message → therapist reply) from ~25 files; 493 exact duplicates dropped; `Career Conversation Sets 1.docx` skipped (1 template ×500, already deduplicated elsewhere).
- **4,985 match-eligible and embedded** (635 of them are opening replies). **1,136 held, never embedded**, so a search physically cannot return them:

| Held reason | Rows | Why |
|---|---|---|
| `user_message_too_short_to_match` | 450 | "Yes", "Okay how so?" — would match anything |
| `governance_hold_paraphilic_content_#26` | 374 | Week 2 file, on hold per [15](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #26 |
| `crisis_or_tier3_handled_by_interlock` | 285 | Tier-3 / crisis conversations — the red-flag interlock owns those, verbatim |
| `reply_may_contain_stray_heading` | 19 | Reply might have a scenario heading glued on — not trusted |
| `reply_has_placeholder` | 6 | e.g. `[technique]` left in the text |
| `reply_has_drafting_note` | 2 | e.g. `*Detailed grounding methods*` where the therapist hasn't written the text yet |

- **`approved` is False on every row.** Nothing can be served until a therapist approves rows (CLI `--approve-eligible` or per-row review). This is deliberate (Gate 2).

### Bugs found by running on the real data (and fixed)
1. **Wrong crisis labelling:** "Initiate crisis protocol" lines come *after* the conversation they describe; attaching them to the next one wrongly held unrelated topics (Weed, Gaming…). Fixed: markers belong to the preceding conversation.
2. **Scenario headings glued onto replies** (~100 rows, e.g. a reply ending in "38. User is upset due to her grandparents") — would have been spoken to a real user word for word. Fixed with heading detection + a catch-all hold for any reply with a non-sequential numbered line.
3. **Embedding timeout:** the runtime client's 3s timeout (right for live turns) is too short for 64-text offline batches; ingestion now passes 120s. Runtime default untouched.
4. **Stale rows:** a row's identity is a hash of its text, so a parser fix would leave the old corrupted row behind. The loader now prunes stale rows, scoped to the files parsed in that run.

### Retrieval sanity check (5 hand-written test messages, eligible rows only)
| Message | Best match | Similarity |
|---|---|---|
| "worry about everything, can't switch my mind off" | the GAD conversation | **0.80** (good) |
| "moved to a new city … feel so alone" | the homesickness conversation | 0.66 (good) |
| "quit smoking but keep relapsing" | nicotine conversations | 0.64 (good) |
| "fighting with partner about money" | generic relationship / gaming-money | 0.54–0.56 (weak) |
| "my teenage son won't talk to me" | an autism-signs conversation | **0.50 (wrong)** |

Query time ~30–75ms including the DB round trip, on a sequential scan (no rows are approved yet, so the partial HNSW index isn't in play; it will be once rows are approved — remember the runtime query must repeat the index's `WHERE approved AND match_eligible` predicate to use it).

**What this proves:** the pipeline works and is fast, and similarity clearly separates good from bad matches — but a score of 0.5 still returns *something*. This is exactly why Step 7 (therapist-labelled calibration) must set `T_strong` before any verbatim serving, and why the strong band must be conservative.

### Notes for Steps 2–3 (from what the data showed)
- Mid-conversation replies ("What do you miss most?") only make sense in context. Use `is_opening` pairs for the strong band; allow mid-conversation pairs only when `prior_context` also agrees.
- `emotion` and `layer` are intentionally NULL (the emotion taxonomies are still unreconciled, [15](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #23); `tier` is set only where the source states it (~10% of rows).
- 1,011 eligible rows have no author (files at the top level of the drop don't say who wrote them) — ask the client.

### Still to build (unchanged from §2)
Step 2 retrieval function · Step 3 orchestrator branch · Step 4 enforcing guardrail · Step 5 reply variety · Step 6 gap queue · Step 7 calibration. Gate 1 and Gate 2 are not yet measured end to end; only the retrieval query time and the match quality above have been spot-checked.


### Update 2026-10-09
All match-eligible rows were approved on instruction. Client drop #2 added more therapist dialogues (Best Conversations flagged `is_preferred`, AI Companion chats) — now 6,440 rows, 5,230 approved. See [33_CLIENT_DROP_2_ADDITIONS.md](33_CLIENT_DROP_2_ADDITIONS.md). The ~1,000 rows without an author stay NULL until the client says who wrote those files.


---

## 8. Implementation status — Steps 2–4 (matching live in `run_turn`), 2026-10-09

### What was built
| Piece | Where |
|---|---|
| Matching: one query on the turn's EXISTING embedding, banded strong / partial / none; clarifying-question lookup | [curated_match.py](../../backend/app/pipeline/curated_match.py) |
| Orchestrator wiring (background lookup, strong/partial/clarify branches) | [orchestrator.py](../../backend/app/pipeline/orchestrator.py) |
| Enforcing rewording check `check_rephrase_faithful` (instant, no model call) | [guardrail.py](../../backend/app/pipeline/guardrail.py) |
| Small "reword only, add nothing" prompt | [prompt_builder.py](../../backend/app/pipeline/prompt_builder.py) `build_rephrase_prompt` |
| Config (all provisional) + `clarifications_asked` state | `config.py`, `state.py`, `.env.example` |
| 5 unit tests | [test_curated_and_welcome.py](../../backend/tests/unit/test_curated_and_welcome.py) |

### The live flow now
safety interlock first (unchanged; it can cancel the match) → therapist match →
- **strong** (similarity ≥ 0.85; ≥ 0.90 if the reply came from mid-conversation): the therapist's reply as written, **no LLM**, `served_from=therapist_verbatim`
- **partial** (≥ 0.62): `CURATED_PARTIAL_MODE=rephrase` (default) — the LLM lightly rewords it with a small prompt, the output is buffered and checked, and if it drifts the therapist's original is served (`therapist_adapted` / `therapist_verbatim_fallback`); `verbatim` mode serves the original with no LLM (`therapist_partial_verbatim`)
- **none**, and nothing else grounds the turn, and the message is ≥ 4 words, and fewer than `CURATED_CLARIFY_LIMIT` (1) clarifying questions in a row: a **therapist-written generic clarifying question** (`therapist_clarify`) — only the generic categories of the clarification bank and only real questions (the bank's other categories are situation-specific and read as non-sequiturs when picked by nearest-neighbour)
- otherwise: the existing LLM path, unchanged.
Soft-zone "possible concern" turns keep their doctor-written follow-up and skip the match. Every therapist-served audit row records `therapist_turn:<id>` in `retrieved_chunk_ids` and the similarity in `latency_ms`.

### Gate 1 (latency) — measured on the real pipeline
- **No new embedding call.** The lookup reuses the turn's embedding.
- The lookup starts as a **background task right after the embedding** (own DB session) and overlaps triage / tier scoring / the interlock. Measured wait for it when needed: **~0.001–0.002 ms** — it was always already finished. Net added latency ≈ 0.
- Strong match total turn time, real providers: **446 ms** and **934 ms** (almost all of it the embedding call; the first call in a process is slow). Partial/adapted: **631–831 ms** total — i.e. the rewording LLM call is cheap (small prompt, one or two sentences).
- Caveat: tiny sample, one machine, warm DB. A proper p95 measurement under load is still owed (doc 31 Phase 8).

### Gate 2 (accuracy) — what was actually observed (6 live turns + 3)
| Message | Result |
|---|---|
| "moved to a new city for college … feel so alone" | partial 0.66 → `therapist_adapted`: *"It sounds like you feel lonely since moving to a new place for college. How can I help you?"* (a light reword; guard passed) |
| "quit smoking but keep relapsing" | partial 0.64 → adapted |
| "laid off yesterday … feel like a failure" | partial 0.75 → adapted |
| exact sentence from a therapist conversation | strong 1.00 → therapist's reply verbatim |
| "I just don't really know how to put this into words" | no match (0.39) → therapist clarifying question |
| "my teenage son won't talk to me anymore" | no match (the old wrong 0.50 hit is now correctly below threshold) → existing LLM path |
| "I want to end my life" | interlock, red-flag script (unchanged; the match never ran) |

### Things seen that were NOT caused by this work (flagged, not fixed)
1. **Interlock false positive:** "I worry about everything: my health, my job, my family, and I can't seem to switch it off" triggered red flag **RF-007** and was answered with a "let me connect you with someone" script. This is the existing interlock (0.44 threshold, deliberately permissive — [08](08_SAFETY_INTERLOCK_AND_TRIAGE.md)); it is exactly the message the therapists wrote a normal reply for. Worth a look.
2. **LLM answered an English message in Hinglish** ("Yeh sun kar lag raha hai…") on the no-match path. Existing prompt/LLM behaviour.

### Not built, and why
- **Step 5 (reply variety)** — small, not started.
- **Step 6 (gap queue)** — deliberately NOT built: it would store raw user messages from a mental-health app in a new table, a privacy decision ([12](12_SECURITY_COMPLIANCE_DPDP.md)) that needs an owner. Today the audit log records only *which* path served a turn and the match similarity, never the user's text. Decide what may be stored (e.g. only after consent / only a hashed or redacted form) before building it.
- **Step 7 (calibration)** — all thresholds are provisional starting points from spot checks. The therapist-labelled set (~100–200 messages) is still needed, and the AI-Companion casual chats should be in it. Until then `CURATED_STRONG_SIMILARITY` is intentionally high so "serve as written" is rare.
- **Client decisions still open:** partial = reword or verbatim (`CURATED_PARTIAL_MODE`)? clarifying question before any LLM reply (`CURATED_CLARIFY_LIMIT`)?
- Kill switch: `CURATED_MATCH_ENABLED=false` restores the previous behaviour exactly.


### Update 2026-10-09 (later) — partial match now gives the LLM ALL the close examples
Decision from the team: on a partial match the LLM must be used, and it should get every appropriate close therapist example, not one reply. `find_curated_match` now returns the best match plus other close ones (similarity ≥ the partial threshold, duplicates dropped, up to `CURATED_MAX_EXAMPLES`=3). `build_rephrase_prompt` shows them as "when someone said X, the therapist replied Y" (best first) and asks for ONE reply using only the ideas, wording and questions in them. The faithfulness check runs against all shown replies together; if it fails, the single best reply is served as written. Audit rows list every therapist turn shown. Re-tested live on 3 messages: all `therapist_adapted`, replies stayed faithful. The rewording call adds roughly 0.2–0.9 s of LLM time on top of the embedding (small sample, noisy) — if latency matters more than adaptation, `CURATED_PARTIAL_MODE=verbatim` skips it.

### Suggestions recorded (not yet done)
- **Thresholds:** keep 0.85 / 0.62 until a therapist-labelled set (~150 messages) exists; then pick strong where ≥95% of labelled replies fit and partial where ≥80% do; also consider requiring a gap between the best and second-best match. A small script that reads the labelled sheet and prints the best cutoffs can be built.
- ~~RF-007 false alarm~~ **Done 2026-10-09 at the product owner's instruction — see below. Clinician review still recommended.**
- **Hinglish reply to English:** Phase 1 is English-only ([13](13_LANGUAGE_PHASING.md)); the prompt currently invites Hinglish when the user's text looks Romanised. Default the prompt to English unless the user clearly writes Hindi/Hinglish.
- **Test sessions** from this build's live tests remain in the dev DB (sessions with `mode='text'`, no user, created 2026-10-09) — delete them.


### Done 2026-10-09 — RF-007 ("exaggerated startle / hyperarousal") now uses the gentle path
- [interlock.py](../../backend/app/safety/interlock.py): `RF-007` added to `SOFT_ZONE_ELIGIBLE_FLAGS` (0.44–0.55 similarity → gentle follow-up, not the crisis script; ≥ 0.55 still hard-escalates) and to a new `NON_DANGER_SOFT_ZONE_FLAGS`. Suicide/self-harm flags are untouched; a unit test ([test_interlock_soft_zone.py](../../backend/tests/unit/test_interlock_soft_zone.py)) fails if one is ever added to the soft zone.
- [orchestrator.py](../../backend/app/pipeline/orchestrator.py): for RF-007's soft zone the therapist match is kept (the therapists' own reply is the better answer); RF-028 still skips it and keeps its doctor-written follow-up.
- Evidence (real embeddings): ordinary worry/tension scored 0.26–0.44 against RF-007; the flag's own example phrases 0.50–0.69.
- Live result: "I worry about everything…" → the therapists' own reply (`therapist_verbatim`, similarity 0.99) instead of the crisis script. A full startle disclosure (pen dropped / heart pounding, 0.69) still gets the script. "I want to end my life" unchanged (script).
- **Known trade-off (needs a clinician):** a shorter startle-style message ("my colleague touched my arm and I screamed…") landed in the gentle zone and got a normal LLM reply, not the script. That is what the change intends, but a clinician should confirm that is acceptable for RF-007.
- Not fixed: "I'm always on edge at work lately and I can't relax" still hits the script — it matched a different flag (RF-013, 0.46), not RF-007.


### Done 2026-10-09 — language handling (Hindi / Hinglish / mixed)
**Problem (confirmed live):** the therapist library is English-only. A Hindi or Hinglish message matched it at only 0.14–0.21, so the new clarifying step answered Hindi speakers with an English question (and an English message earlier got a Hinglish reply from the LLM). Switching between languages "confused" it.
**Fix:** [language_hint.py](../../backend/app/pipeline/language_hint.py) — an instant, no-network check (Devanagari characters or common Hinglish words → not English; ambiguous English words like "main"/"to" are excluded from the word list). A message with any Hindi in it **skips the English therapist match and clarifying step** and goes to the LLM, and every LLM prompt now carries an explicit language line ("English only" / "reply in the same mix and script"), replacing the model's guesswork. English messages are unchanged (therapist match, instant).
**Live result:** English → the therapists' reply (English); Devanagari, Romanised Hinglish and mixed messages → a Hindi reply from the LLM; an English message now gets an English reply (the earlier Hinglish bug is gone). 45 unit tests pass.
**Known limits:** (1) Hindi/Hinglish users get the LLM path, not the therapist library — that needs a Hindi library (or translate-then-match, ~+1 s) — doc 13's later phase; (2) a Romanised-Hinglish message currently gets a Devanagari reply, ignoring the "same script" line; (3) the heuristic can miss Hinglish that uses none of the listed words; (4) **the safety gap in [15 #29](15_OPEN_QUESTIONS_AND_BLOCKERS.md) — Hindi/Hinglish crisis messages are not caught by the interlock — is the most important open issue.** Also: stale entries in the exact-response cache from earlier test runs (an old wrong-language reply to an English message) were cleared from the dev Redis.


### Update 2026-10-09 — language handling superseded by translation
The earlier approach (Hindi/Hinglish messages skip the English library and go to the LLM) is replaced by the Sarvam translation layer in [34](34_HINDI_HINGLISH_TRANSLATION_LAYER.md): Hindi/Hinglish users now go through the same safety check and therapist match as English users, with replies translated into their language.


### Fix 2026-10-13 — the therapist search was not using its HNSW index
`find_curated_match` filtered with `.is_(True)`, which SQLAlchemy renders as `approved IS true`; Postgres cannot prove that implies the partial index's `WHERE approved AND match_eligible`, so the planner silently did a sequential scan (found via `EXPLAIN`). Harmless at ~5k rows (tens of ms) but it would have degraded as the library grows and contradicted the Gate-1 claim. Fixed by using the bare boolean columns (comment in `curated_match.py`); verified the real compiled SQL now plans an `Index Scan using ix_kb_therapist_turns_embedding_hnsw`. Rule: after touching that query, `EXPLAIN` it. See [35](35_DEVELOPER_GUIDE_HOW_THE_RESPONSE_SYSTEM_WORKS.md) §4.
