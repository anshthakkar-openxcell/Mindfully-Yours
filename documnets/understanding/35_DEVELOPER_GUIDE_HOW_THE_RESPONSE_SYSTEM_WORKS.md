# 35. Developer guide — how a reply is produced, and why this is the right approach

**Audience:** developers working on the AI service. **Not** for the client — the client-facing material is the PDF in `documnets/Client Presentation/AI Response Flow/`.
**Purpose:** after reading this you should be able to (1) explain the whole response system to someone else, (2) find the code for any step, (3) debug "why did it say that?", (4) add content or change behaviour safely, and (5) defend the design choices — and know where it is still weak.
**Status of facts:** everything below was checked against the code and the live dev system on 2026-10-13. Where something is a guess or provisional, it says so.

---

## 0. The idea in ten lines

1. The product's whole point is **the therapists' expertise**. So a reply should come from **their conversations**, not from an LLM's general knowledge, whenever their library has something that fits.
2. A user message is turned into a **meaning vector** (embedding) once. Everything that "searches" uses that same vector.
3. **Safety runs first and can override everything.** A red-flag match → the clinically approved script, word for word. The LLM is never involved.
4. Otherwise we **search the therapist conversations by meaning**. The closeness of the best match picks the path:
   **strong** → send the therapist's reply as written (no LLM) · **partial** → the LLM rewords a few close therapist examples, *checked* so it can't add content · **none** → a therapist-written clarifying question, then (only then) the LLM, grounded in therapist self-care material.
5. The LLM is therefore a **phraser and a last resort**, never the author of clinical content on a matched case.
6. One PostgreSQL database holds both the text and the vectors (pgvector). Redis holds short-lived conversation memory.
7. Everything is **logged with its source** (`served_from`), so we can measure how much of the product's output is really "therapist-made".
8. Non-English users go through the same pipeline by **translating in** (so safety and search work) and **localising out** (pre-translated fixed replies → instant).
9. Every threshold is a **config knob**, currently *provisional* — the main piece of remaining engineering is calibrating them with therapist-labelled data.
10. The library improves by **adding approved rows** — no model training, no deploy.

---

## 1. Why we are building it this way (the product constraint)

The client's requirement (from their email): *if a conversation in the Knowledge Base is similar to the user's issue, the response is curated from that, not from the LLM — otherwise what is unique about the app?*

That is a **product** requirement that happens to also be the right **engineering** answer for a mental-health app:

| Concern | Pure-LLM reply | Therapist-first reply |
|---|---|---|
| Clinical correctness | Whatever the model "knows"; can hallucinate advice | Words a therapist wrote and a team approved |
| Consistency | Differs run to run | Same situation → same expert wording |
| Auditability | "The model said so" | `served_from` + the exact therapist turn id |
| Fixing a bad reply | Prompt-tweak and hope | Edit/unapprove one row; instant |
| Latency & cost | LLM call every turn | Strong match = no LLM call at all |
| Improvement path | Wait for a better model | Add conversations; library grows |

The LLM is still useful — for *phrasing* when the match is only partial, and for *coverage* when nothing matches — but it is deliberately demoted from "author" to "assistant".

---

## 2. The building blocks

```
 user (text or voice) ──► NestJS backend / LiveKit ──► AI SERVICE (FastAPI, this repo: backend/)
                                                          │
            ┌─────────────────────────────────────────────┼───────────────────────────────┐
            ▼                                             ▼                               ▼
   PostgreSQL + pgvector                              Redis                       outside AI (adapters)
   (the "RDS" and the "vector DB"                     • session state (6 h TTL)   • OpenAI  text-embedding-3-small
    are the SAME database)                            • exact-reply cache (24 h)  • Sarvam  LLM / STT / TTS / translate
   • KB tables (text + vector columns)
   • therapist conversations
   • audit log, translations
```

**RDS vs vector DB — the question the client asked.** There is one PostgreSQL. Ordinary columns hold text/rules/scripts; a `vector(1024)` column on the same row holds the meaning vector; an **HNSW index** makes "nearest vectors" fast. A single SQL query returns the nearest rows *and* their text — so there is no second system to keep in sync. `documnets/understanding/30_QDRANT_VS_PGVECTOR_COMPARISON.md` has the full trade-off; at our size (~14k searchable rows) pgvector is the right call.

**Embeddings.** OpenAI `text-embedding-3-small` called with `dimensions=1024` (so existing columns didn't need re-migration). Similarity everywhere = `1 − cosine_distance`. Typical values: paraphrases 0.65–0.85, same sentence 1.0, unrelated ≤ 0.5.

### Tables that matter for replies

| Table | Role | Searched by vector? |
|---|---|---|
| `kb_red_flags` | Danger patterns + the **approved verbatim script** | yes (`trigger_embedding`) |
| `kb_signals`, `kb_symptoms`, `kb_sufficiency_patterns` | Triage: what is being said, which pattern is closest | yes |
| `kb_routing_rules` | When signals mean Tier 1/2/3 (read by code, in `priority` order) | no |
| **`kb_therapist_turns`** | **(user said → therapist replied) pairs — the heart of the system** | yes (`context_embedding`) |
| `kb_clarification_phrases` | Therapist "tell me more" questions (generic categories only) | yes |
| `kb_content_chunks` | Self-care tools/strategies (Tier 1 grounding for the LLM) | yes |
| `kb_welcome_responses` | Opening messages | no (random pick) |
| `kb_translations` | Pre-translated fixed replies (per language style) | no (hash lookup) |
| `turn_audit_log` | One row per turn: source, ids, timings | no |
| `kb_layer_content`, `kb_scenarios`, `kb_emotion_phrases`, `kb_tier_question_bank`, … | Ingested question banks — **stored, not yet used in replies** | yes (not queried live) |

`kb_therapist_turns` columns you need to know: `user_text` (embedded), `reply_text`, `prior_context` (not embedded), `is_opening`, `is_preferred`, `match_eligible`, `hold_reason`, `approved`, `content_hash` (unique → idempotent re-ingestion), `context_embedding`. **A row can be served only if `approved AND match_eligible`** (and it has a vector).

---

## 3. One turn, step by step

Entry: `app/pipeline/orchestrator.py::run_turn`. It is an async **generator** that yields reply chunks. Both the text endpoint (`POST /api/v1/conversation/turn`) and the voice agent (`app/realtime/livekit_llm.py`) call exactly this function — there is no second copy of the logic.

```
 1  load session state            Redis  (recent turns, running severity score, candidate pattern, clarifications_asked)
 2  language check                detect_language_style(text): en / hi / hinglish (instant heuristic)
    └ if not English → Sarvam translate → English ("text_en")          [+~0.7 s, non-English turns only]
 3  embed text_en once            OpenAI.  If this FAILS → fail-safe message ("let me connect you…"), audit, STOP.
 4  start therapist lookup        asyncio background task, OWN db session   ← overlaps steps 5–8, costs ~0 wall time
 5  exact-reply cache lookup      Redis (semantic cache is a stub: returns None)
 6  triage                        vector search kb_signals / kb_symptoms / kb_sufficiency_patterns → matched signal ids
 7  update running tier score     points per NEW signal; may make one small LLM call (duration/impact) on early turns
 8  SAFETY INTERLOCK              vector search kb_red_flags.  Failure → fail-safe message, STOP.
    ├─ triggered → cancel therapist task → verbatim script (localised) → save state, audit → STOP
    └─ not triggered ↓
 9  routing rules                 deterministic lookup (kb_routing_rules) on accumulated signals → tier
10  await therapist lookup        (already finished; waits ~0 ms).  Skipped if a soft-zone concern, except RF-007.
    ├─ STRONG                     → send reply as written (localised) → STOP                       served_from=therapist_verbatim
    ├─ PARTIAL + mode=verbatim    → same, served_from=therapist_partial_verbatim
11  exact-cache hit?              → send cached reply → STOP
12  PARTIAL + mode=rephrase       → small prompt, LLM rewords, BUFFER, faithfulness check →
                                    pass: send reworded   (therapist_adapted)
                                    fail/LLM error: send the therapist's original (therapist_verbatim_fallback) → STOP
13  choose "guidance" for the LLM (priority order):
      soft-zone concern follow-up question  >  tier-redirect (booking nudge)  >  Tier-1 self-care search
      >  therapist probing guidance for the candidate pattern;  + "evidence-gathering" nudge if score_tier ≥ 2
14  no match, no guidance, not soft concern, < limit clarifications, ≥ 4 words
                                  → nearest GENERIC therapist clarifying question → STOP          served_from=therapist_clarify
15  LLM answers                   build_prompt(persona + language line + clinical-markers checklist + running summary (not populated yet) + last ≤6 turns
                                  + grounding + user message) → stream → guardrail (log-only today)   served_from=rag_retrieval / tier_*
16  record                        Redis state, exact cache (LLM replies only, not if interrupted), audit row
```

### Why this order (these are invariants — don't reorder casually)

* **Safety before everything that writes a reply.** Triage and the interlock run on *every* turn, even cache hits. The interlock can cancel the therapist lookup (step 8).
* **One embedding per turn.** An embedding call is the single slowest thing we do (0.3–1.3 s typical, occasionally 2–3 s). Every search reuses it. Adding a second sequential embedding call would blow the 1.5–2.5 s budget.
* **The therapist lookup is a background task with its own DB session.** An `AsyncSession` cannot run two queries at once, so sharing the request session would serialize it behind triage. As a separate task it finishes while triage/interlock run; measured wait when we need it: ~0 ms.
* **Strong matches return before the cache check; partial-rephrase comes after it.** A therapist reply beats a cached LLM reply; a cached reply beats re-running the LLM.
* **LLM failures never cost the user a reply** on the partial path — we fall back to the therapist's original.
* **Interrupted turns (voice barge-in)** still save state and audit (`*_interrupted` suffix) and are never cached.

### The same turn, measured (real run, 2026-10-13, `scripts/try_turn.py`)

| Message | Source | embed | triage | interlock | therapist wait | LLM | total |
|---|---|---|---|---|---|---|---|
| exact therapist sentence | `therapist_verbatim` (sim 1.00) | 2776 ms* | 68 | 12 | 0 | — | 3.1 s* |
| "moved to a new city… feel so alone" | `therapist_adapted` (sim 0.66, 3 examples) | 444 | 9 | 5 | 0 | **164** | **0.79 s** |

\*first call after idle: OpenAI latency spike. **Takeaway: the embedding call is ~all the time; triage/interlock are single/double-digit ms, the therapist lookup is hidden, and rewording a short reply costs ~160 ms.**

---

## 4. Matching in depth

Code: `app/pipeline/curated_match.py`.

```python
distance = KBTherapistTurn.context_embedding.cosine_distance(query_embedding)
SELECT … FROM kb_therapist_turns
WHERE approved AND match_eligible AND context_embedding IS NOT NULL AND language = :lang
ORDER BY distance LIMIT CURATED_TOP_K(5)
```

1. Take the 5 nearest rows. Score = `similarity (+0.02 if is_preferred)`. The "preferred" bonus (Best Conversations file) is only a **tie-breaker** — it can't rescue a bad match.
2. Band the **best** row by *true* similarity (bonus excluded):
   * `strong`  ≥ **0.85** (≥ **0.90** if the row is mid-conversation, i.e. `is_opening = false`)
   * `partial` ≥ **0.62**
   * `none` otherwise → treated as "no match"
3. For a partial/strong result also collect up to **3 distinct** replies with similarity ≥ 0.62 (`examples`) — the LLM sees them all.

**Why the mid-conversation margin:** a reply taken from the middle of a conversation ("What do you miss most?") is only meaningful in context. Requiring +0.05 makes verbatim reuse of such rows rarer. (A proper fix — context-aware matching — is in §12.)

**Why only `approved AND match_eligible` rows, and why the exact SQL form matters:** the HNSW index is *partial* (`WHERE approved AND match_eligible AND context_embedding IS NOT NULL`). Postgres uses it only if it can prove the query implies that predicate. **Writing `.is_(True)` renders `approved IS true`, which Postgres can't prove → silent sequential scan.** We hit exactly this on 2026-10-13 and fixed it (bare boolean columns, with a comment in the code). Rule: *after touching this query, `EXPLAIN` it and look for `Index Scan using ix_kb_therapist_turns_embedding_hnsw`.*

**What the numbers look like (spot checks, not a validated set):**

| User message | Best match | Sim | Verdict |
|---|---|---|---|
| "worry about everything… can't switch it off" | the GAD conversation | 0.80 | strong-ish ✔ |
| "moved to a new city for college… feel so alone" | homesickness conversation | 0.66 | partial ✔ |
| "quit smoking but keep relapsing" | nicotine conversations | 0.64 | partial ✔ |
| "my partner and I fight about money" | a loosely related row | 0.54–0.56 | none ✔ (below 0.62) |
| "my teenage son won't talk to me" | an autism-signs conversation | 0.50 | none ✔ (this was a *wrong* match; the threshold correctly rejects it) |

The gap between "right topic, different words" (0.64–0.66) and "wrong topic" (≤0.56) is real but **narrow** — which is exactly why the cut-offs must be calibrated on data (§11) and why "strong" is set high.

---

## 5. The partial path (LLM rewords, can't invent)

Code: `build_rephrase_prompt` (prompt_builder.py), the block in `run_turn`, `check_rephrase_faithful` (guardrail.py).

**What the LLM is shown** (small prompt — no clinical-markers table, so it's fast):
```
<persona> + "reply in the user's language" line
<last ≤6 turns>
Real examples from our therapist team, closest first:
1. When someone said: "…"  the therapist replied: "…"
2. …  (up to 3, distinct replies)
Write ONE reply … using ONLY the ideas, wording and questions that already appear in the therapist replies above …
Do NOT add advice, suggestions, questions, facts, numbers or links that are not in those replies.
IMPORTANT -- language of your reply: <instruction>      ← repeated last; the model copies the examples' language otherwise
The user just said: <original user text>
```
**Why show several examples:** the model gets the *pattern* of how the team handles this kind of situation (tone, the kind of question they ask) rather than one sentence to paraphrase — and the guard checks against all of them together, so it may combine.

**The guard (`check_rephrase_faithful`) is deliberately instant (no second model call — Gate 1):** non-empty; no digits/URLs the therapist didn't write; length ≤ 1.6× the combined therapist text (floor of 40 chars); and ≥ 60 % of the reworded text's content words appear in the therapist text. **The output is buffered** (it's 1–2 sentences) *before* the user sees any of it. If the check fails → the therapist's original reply is sent. A failed rewording is never shown.

**Honest limits of the guard:** it catches drift, padding, added numbers/links — it does **not** prove semantic equivalence (a reword could subtly shift meaning using the same words). For non-English turns the LLM writes directly in the user's language, so the word-overlap test is skipped (only empty/number/link checks apply). Acceptable today; revisit with a judge-model or NLI check if rewording quality becomes a concern.

`CURATED_PARTIAL_MODE=verbatim` skips the LLM entirely for partial matches (fastest, zero drift). Default is `rephrase` per the product decision that the LLM should be used for partial matches.

---

## 6. The no-match path

1. **Guidance selection (step 13)** decides what grounds the LLM, in priority order:
   * *soft-zone concern* (a doctor-written follow-up question to weave in);
   * *tier redirect* (score_tier ≥ 2 **and** `should_redirect_to_booking`: several distinct signals + duration + impact established → gentle "would you like help finding a professional");
   * *Tier-1 self-care*: `search_self_care_content` over `kb_content_chunks` (the DBT/self-help tools and the 125 therapist-written situation strategies) at `RETRIEVAL_CONFIDENCE_THRESHOLD` 0.30 — note this is permissive and only the top chunk is used;
   * *probing guidance* for the persistent `candidate_pattern_id` (fetched by id, never searched);
   * plus an "evidence-gathering" nudge (ask about duration/impact) when the score is Tier-2-ish but not yet redirect-ready.
2. **Clarifying question (step 14):** only if nothing grounded the reply. Nearest question from `kb_clarification_phrases`, **restricted to the generic categories** (`General Fallback Responses`, `General Clarification Responses`, `When AI Needs More Context`) and real questions (`ends with ?`, no drafting note). Reason: the bank's other categories are situation-specific ("Have you noticed changes in your appetite?") and read as non-sequiturs when picked by nearest-neighbour. Limit `CURATED_CLARIFY_LIMIT` (=1) in a row, reset whenever a therapist reply is served; skipped for messages under 4 words ("hi").
3. **LLM (step 15):** full `build_prompt`. It always carries the persona, the language line, the Clinical Markers checklist (what to *quietly notice*; the LLM never decides safety), the last ≤ 6 turns, and the one piece of grounding above. Streaming is preserved.

**What the output guardrail does today:** `check_grounding` is a placeholder — it only *logs* "substantive response with no grounding". It does not block. (Tightening this is on the roadmap.)

---

## 6a. Safety — the part that must never regress

Code: `app/safety/interlock.py`, `app/pipeline/orchestrator.py` (steps 8 + early returns).

* Matching is **embedding-based** (to catch disguised/indirect language) but the **response is a fetched verbatim script** — the LLM is never in the loop.
* Thresholds: general `REDFLAG_MATCH_THRESHOLD` 0.44 (deliberately permissive: a false positive costs a moment's caution, a false negative a missed danger signal); suicide flags `RF-018/019` are checked among the **top-15** at the lower **0.36** (`CRITICAL_SELF_HARM_FLAGS`) because explicit disclosures scored only ~0.39 against them.
* **Soft zone:** for an explicit allowlist (`SOFT_ZONE_ELIGIBLE_FLAGS` = RF-028, RF-007) a match between 0.44 and 0.55 gets a gentle follow-up instead of a crisis script; ≥ 0.55 still hard-escalates. RF-007 ("exaggerated startle/hyperarousal") was added on 2026-10-09 because ordinary worry language scored 0.39–0.44 against it while its real examples scored 0.50–0.69. **A unit test fails if a suicide/self-harm flag is ever added to the soft zone.** `NON_DANGER_SOFT_ZONE_FLAGS` (RF-007 only) lets the therapist match still run on those turns.
* **Fail-safe, always upward:** embedding failure or interlock failure → "I want to make sure you get the right support — let me connect you with someone." (localised). Never a silent continue.
* RF-028–031 have **no** approved script → `requires_human_alert` hard path (never LLM).
* **Rule for every change in this repo:** nothing may be placed before step 8 that can write a reply, and nothing may skip steps 6–8 (cache hits included).

---

## 7. Where the data comes from (ingestion)

Commands (all idempotent; run from `backend/`):
```
python -m app.ingestion.cli ingest              --kb-dir …   --label …      # the 6 Phase-I clinical sheets
python -m app.ingestion.cli ingest-convo-data   --convo-dir … --career-csv … --label …
python -m app.ingestion.cli ingest-therapist-turns --convo-dir "<…>/decrypted/<folder>" [--approve-eligible] [--dry-run] [--no-embed]
python -m app.ingestion.cli ingest-client-drop-2   --drop-dir "documnets/new uploaded documents/decrypted"
python -m app.ingestion.cli translate-kb [--kinds …] [--styles hi,hinglish] [--concurrency 6]
```
**Therapist conversations** (`app/ingestion/parsers/therapist_turns.py`):
* Reads every `.docx` under the folder; a line starting `User:/Client:/Parent:/Female:` is the user side, `AI:/AI Companion:/Al:/A:` the AI side (all real variants found in the source). Consecutive lines by one speaker merge into one turn.
* **Conversation boundaries** = any non-dialogue line. A bullet/`List` line right after an AI turn continues that turn (tip lists) — **except** numbered lines that look like the *next scenario's heading* (`38. User is upset…`), which would otherwise be spoken to a user verbatim. `Initiate crisis/matching protocol` lines are **outcomes of the conversation before them**, not headers of the next.
* Each (user turn → AI turn) pair becomes a row; `prior_context` keeps up to 2 earlier exchanges for display/review.
* **Quality gates** — a row is stored but `match_eligible=false` (never embedded, never searchable) when:

| `hold_reason` | Why |
|---|---|
| `crisis_or_tier3_handled_by_interlock` | Tier 3 / crisis conversation — the red-flag path owns those, verbatim |
| `governance_hold_paraphilic_content_#26` | Content on hold pending a clinical + legal decision |
| `reply_has_placeholder` / `reply_has_drafting_note` | `[technique]`, `(name of city)`, `*Detailed grounding methods*` — text the therapist hasn't finished |
| `reply_may_contain_stray_heading` | numbered lines that aren't a clean 1,2,3… list (catch-all for leaked headings) |
| `user_message_too_short_to_match` | < 4 words ("yes", "thanks") would match anything |

* `content_hash = sha256(norm(user_text) || norm(reply_text))` makes re-ingestion an **upsert**; a parser fix that changes a reply's text creates a *new* row, so the loader **prunes stale rows from the files it just re-parsed** (scoped by `source_file`).
* `approved` defaults to **false**; `--approve-eligible` (or an `UPDATE`) approves eligible rows. `approved` is never reset by a re-run unless the flag is passed.
* Embedded text is `user_text` only. Mid-conversation context is stored but **not** embedded (see §12).

**Self-care strategies** from the Situational Routing sheet are loaded into `kb_content_chunks` (embedded as `"<situation>. <strategy>"` — the user's message describes the *situation*, so that's what must match).

### Runbook — add or fix therapist content
```
1. Put the .docx in the source folder (User:/AI: lines; one blank-line-or-heading between conversations).
2. ingest-therapist-turns --dry-run          # look at the held-reason counts; unexpected holds = parser/format issue
3. ingest-therapist-turns [--approve-eligible]
4. translate-kb --kinds therapist_reply       # (rate-limited by Sarvam; resumable) so non-English replies are instant
5. scripts/try_turn.py "<a message the new content should answer>"   # confirm served_from + similarity
6. A bad row?   update kb_therapist_turns set approved=false where id = <id>;     (instant, no deploy)
```

---

## 8. Languages (Hindi / Hinglish / mixed)

Code: `language_hint.py`, `providers/translation.py`, `pipeline/localize.py`, the top of `run_turn`. Full detail: doc 34.

* **Why a translation layer:** the red flags, signals, and therapist library are English-only; a Hindi crisis message scored ~0.2 against them (missed). So non-English text is translated **in** (Sarvam `mayura:v1`, mode `modern-colloquial`, source `hi-IN`, ~0.7 s) and the whole pipeline runs on the English text.
* **Out:** fixed replies (therapist reply, clarifying question, red-flag script, welcome, fixed messages) come from `kb_translations` — **pre-translated offline** (live translation is 0.7–1.5 s, too slow per turn); a miss translates live and stores it. LLM-written replies are written **directly** in the user's language (no extra call, streaming kept).
* `detect_language_style` is an **instant heuristic** (Devanagari characters or ≥2 distinctive Romanised-Hindi words). Ambiguous English words ("main", "to") are excluded on purpose.
* **Limits:** idioms can be softened by translation (one suicidal idiom was translated too weakly and not escalated → a clinician-approved keyword safety net is still recommended); machine-translated crisis scripts are `reviewed=false`; Sarvam is rate-limited (~100 calls/min on the current key) — a production-capacity question, not just a bulk-job one.

---

## 9. Why this is the best approach (and what we compared it to)

| Alternative | Why not (for this product) | When to reconsider |
|---|---|---|
| **LLM writes everything**, prompt-stuffed with the KB | Can't guarantee therapist wording; hallucination risk on clinical content; no per-reply provenance; slow/expensive every turn; violates the stated product promise | never as the primary path |
| **Classic RAG** (always retrieve, always let the LLM write) | Better, but the LLM still *authors* the reply — it can drift from or contradict the therapist text even when a perfect match exists | useful as our *fallback* (it is: step 13+15) |
| **Fine-tune an LLM on the therapist conversations** | Expensive, opaque, can't point to *which* conversation produced a reply, can't unlearn a bad row, and risks leaking/blending real conversations; needs re-training to improve | if we ever have orders of magnitude more data and need generative fluency |
| **Intent classifier / decision tree** | Needs a fixed taxonomy; therapists write free-form conversations; brittle on unseen phrasing | for the deterministic parts only (routing rules — which we already do in code) |
| **Keyword search** | Misses paraphrase and indirect language ("I just feel so tired of everyone") — exactly the language the red-flag list was designed to catch | never as primary |
| **Separate vector DB (Qdrant)** | A second system to run, secure and keep in sync; no benefit at ~14k vectors | if volume reaches millions or vector latency becomes the bottleneck |

**Why the *banded* design specifically (strong / partial / none):** the three failure modes are different and need different handling.
* *Very close match* → the highest-quality, lowest-risk, fastest answer is the therapist's own text. Don't touch it.
* *Close but not identical* → the therapist's meaning is right but the wording needs to fit this person. This is what an LLM is genuinely good at — **if constrained**. So we constrain it (examples-only prompt + a guard + a fallback to the original).
* *Nothing close* → the honest answer is "I don't have an expert answer yet": ask, don't guess; only then use the LLM, grounded where possible, and let the unmatched case become a to-do for the therapists.

**What this does for the AI's quality, concretely**
1. **The LLM gets a narrow job** ("reword these"), which small/cheap models do reliably, instead of a broad one ("be a therapist").
2. **Grounding in real expert language** sets tone and content far better than a persona paragraph.
3. **Errors are contained**: safety is independent; a bad reword falls back to the original; an LLM outage still serves the therapist reply.
4. **Every reply is explainable** (`served_from`, `therapist_turn:<id>`), which is what makes clinical review and DPDP-style audit possible.
5. **A built-in improvement loop:** every "none" is a gap the therapists can fill; every added row helps immediately.
6. **Latency/cost fall as the library grows:** more strong matches = fewer LLM calls.

**Honest weaknesses of the approach** (don't oversell it to yourself)
* Matching is by **one message's embedding** — blunt for context-dependent replies (§12).
* **Coverage-bound:** a thin library means many "none"s. Quality of the product tracks the library.
* **Thresholds are uncalibrated** — the biggest single risk. Strong set high on purpose.
* A "strong" verbatim reply can feel **repetitive** over a long chat (no variation layer yet).
* `approved` means "included", **not** "clinically reviewed". The conversations include casual AI-companion chats that could be matched to a distressed user if thresholds are loose.
* The LLM-written path still has only a **log-only** output check.

---

## 10. Observability — answering "why did it say that?"

Every turn writes one `turn_audit_log` row. Useful columns: `served_from`, `retrieved_chunk_ids` (`therapist_turn:<id>` for therapist-served turns, all shown examples for partial), `latency_ms` (JSON: `translate_in_ms, embed_ms, triage_ms, tier_score_ms, interlock_ms, curated_wait_ms, curated_similarity, clarify_similarity, llm_ms, total_ms`), `matched_signal_ids`, `score_tier`, `interlock_flag_id`.

`served_from` values: `interlock`, `interlock_failure_safe_path`, `interlock_possible_concern`, `therapist_verbatim`, `therapist_partial_verbatim`, `therapist_adapted`, `therapist_verbatim_fallback`, `therapist_clarify`, `exact_cache`, `rag_retrieval`, `tier_redirect_ready`, `tier_gathering_evidence` (+ `_interrupted` variants).

```sql
-- how much of our output is therapist-made?
select served_from, count(*) from turn_audit_log group by 1 order by 2 desc;

-- which therapist reply produced a turn? (take the id from retrieved_chunk_ids)
select conversation_id, scenario, author, source_file, user_text, reply_text
from kb_therapist_turns where id = 258;

-- are held rows really excluded? (should be 0)
select count(*) from kb_therapist_turns where approved and not match_eligible;
```
**Try it live:** `backend/scripts/try_turn.py "message" ["message2" …]` runs the real pipeline and prints source, ids, timings and reply (creates marked dev sessions; cleanup SQL is in the script's docstring).

---

## 11. Calibrating the thresholds (the most valuable next piece of work)

Today `0.85 / 0.62 / +0.05` are educated starting points from spot checks. To make them *evidence-based*:

1. **Build a labelled set** (≈150–200 messages, include the casual-companion style and some Hindi/Hinglish-translated ones): for each message a therapist marks *which library reply fits* — or "none fits". Prefer real/realistic messages, not therapist-written openers (those match themselves at 1.0).
2. **Replay**: for each message, run `find_curated_match`-style retrieval, record the top-1 row and similarity (plus top-2 gap).
3. **Sweep thresholds**: for each candidate `T_strong`, compute *precision* (fraction of served-verbatim replies a therapist judged fitting) and *coverage* (fraction of messages served). Choose the lowest `T_strong` with precision ≥ ~95 %; same idea for `T_partial` at ~80 % "usable as an example".
4. **Also test**: top-1 vs top-2 margin as an extra gate; `is_opening` margin; tier/emotion filters once those fields are tagged.
5. **Write the result into `.env`** (all are env-configurable), record the date and dataset in doc 32, and **re-run whenever the library grows meaningfully**.
6. A small script that reads the labelled CSV and prints the precision/coverage table is a good first deliverable (not built yet).

---

## 12. Known gaps, risks, and the roadmap (in priority order)

| # | Item | Why it matters | Sketch |
|---|---|---|---|
| 1 | **Threshold calibration** (§11) | Verbatim = authoritative; a wrong strong match is worse than an LLM reply | labelled set + sweep |
| 2 | **Context-aware matching** | Mid-conversation replies need context; single-message embedding is blunt | embed `[current message, last-AI-reply + current message]` in **one batched embedding request** (two inputs, ~same latency, no extra round trip); store a second vector per row (`prior_ai_text + user_text`); require both to agree for strong |
| 3 | **Gap list ("nothing matched")** | Closes the loop with the therapists | needs a **privacy decision first** (it stores user text from a mental-health app): store a redacted/hashed form, or only after explicit consent; DPDP review ([12](12_SECURITY_COMPLIANCE_DPDP.md)) |
| 4 | **Stronger output guardrail on the LLM path** | Today log-only | NLI/judge check run **async or in parallel** (don't add a blocking call — Gate 1) |
| 5 | **Reply variety layer** | Verbatim repeats feel robotic | vary only the opening/closing connector, never clinical content |
| 6 | **Hindi/Hinglish crisis-word safety net** | Translation can soften idioms | clinician-approved keyword list checked on the *original* text, before translation |
| 7 | **Embedding timeout → one quick retry** | A 3 s timeout fail-safes with "connect you with someone" on ~1/15 slow turns | retry once (budget permitting) before the fail-safe |
| 8 | **Wire `app/safety/fallback.py`** (the "conversation going nowhere / disengaged" safety net) | Built + unit-tested, **not connected** to `run_turn` | evaluate Section-C rules on `ConversationState` each turn |
| 9 | **Use the stored question banks** (Layer I–IV, emotions, scenarios) | Ingested, not yet used | layer-aware questioning; emotion tagging (needs the taxonomy merge, [15](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #23) |
| 10 | **Semantic cache, session summary, rate limiting** | stubs/TODOs in code | per docs 04/09 |
| 11 | **Reconcile Situational-Routing tier wording with routing rules** ([15](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #25) | Stored, not used for routing | clinician decision first |
| 12 | **Sarvam translation capacity** | ~100 req/min limit caps concurrent non-English users | confirm plan before launch |

---

## 13. Config reference (all in `.env`; defaults in `app/core/config.py`)

| Variable | Default | Effect |
|---|---|---|
| `CURATED_MATCH_ENABLED` | true | **Kill switch**: false restores the pre-therapist-first behaviour exactly |
| `CURATED_STRONG_SIMILARITY` | 0.85 | ≥ → serve therapist reply as written (provisional) |
| `CURATED_PARTIAL_SIMILARITY` | 0.62 | ≥ → partial; also the floor for "shown examples" (provisional) |
| `CURATED_NON_OPENING_MARGIN` | 0.05 | extra similarity needed for strong when the row is mid-conversation |
| `CURATED_PARTIAL_MODE` | rephrase | `rephrase` = LLM rewords; `verbatim` = serve as written (no LLM) |
| `CURATED_MAX_EXAMPLES` | 3 | therapist examples shown to the LLM on partial |
| `CURATED_CLARIFY_LIMIT` | 1 | clarifying questions in a row before the LLM may answer |
| `CURATED_TOP_K` | 5 | candidates fetched per lookup |
| `REDFLAG_MATCH_THRESHOLD` / `_SOFT_ZONE_` / `_CRITICAL_` | 0.44 / 0.55 / 0.36 | safety interlock (see §6a) — **change only with clinician sign-off** |
| `TRIAGE_SIGNAL_THRESHOLD` / `PATTERN_MATCH_THRESHOLD` | 0.45 / 0.30 | triage matching (noisy at single-signal level by design — signals accumulate) |
| `RETRIEVAL_CONFIDENCE_THRESHOLD` | 0.30 | Tier-1 self-care search (permissive; only top chunk used) |
| `TRANSLATION_ENABLED` / `SARVAM_TRANSLATE_MODEL` / `TRANSLATION_TIMEOUT_SECONDS` | true / mayura:v1 / 5.0 | translation layer |

---

## 14. Code map

| Concern | File |
|---|---|
| The turn | `app/pipeline/orchestrator.py` |
| Therapist match + clarifying question | `app/pipeline/curated_match.py` |
| Prompts (normal + rephrase) | `app/pipeline/prompt_builder.py` |
| Rewording guard, grounding check | `app/pipeline/guardrail.py` |
| Safety | `app/safety/interlock.py`, `triage.py`, `routing.py`, `fallback.py` (unwired) |
| Tier scoring | `app/pipeline/tier_scoring.py` (doc 28) |
| Session memory | `app/pipeline/state.py` |
| Language | `language_hint.py`, `localize.py`, `app/providers/translation.py` |
| Welcome | `app/pipeline/welcome.py` (+ `POST /api/v1/conversation/welcome`) |
| Ingestion | `app/ingestion/cli.py`, `app/ingestion/parsers/*` |
| Models | `app/db/models/kb.py`, `kb_convo_content.py`; migrations in `alembic/versions/` |
| Dev tool | `scripts/try_turn.py` |
| Tests (50 unit tests) | `tests/unit/` — parsers, banding, guard, language, translation, soft-zone guard |

**Related docs:** 04 pipeline order · 08 safety · 09 latency · 28 tier scoring · 30 pgvector vs Qdrant · 32 therapist-first approach & status · 33 client drop #2 · 34 translation layer · 15 open questions.

---

## 15. Glossary

**Embedding / meaning vector** – a list of numbers capturing a sentence's meaning; similar meanings → close vectors. **Cosine similarity** – closeness of two vectors (1 = same). **pgvector / HNSW** – Postgres vector type / the index that makes nearest-neighbour search fast. **RAG** – retrieve relevant material, then let the LLM write using it. **Interlock** – the deterministic safety layer. **Triage** – silent reading of signals/severity each turn. **Tier 1/2/3** – self-care / professional support / immediate crisis. **Strong / partial / none** – the three match bands. **Held row** – stored but never searchable (`match_eligible=false`).
