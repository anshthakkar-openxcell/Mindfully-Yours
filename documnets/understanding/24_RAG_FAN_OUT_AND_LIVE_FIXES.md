# 24. The Real RAG Pipeline: What Got Built, and Every Bug Found Along the Way

This documents the single biggest implementation jump in the project so far: taking the
conversation pipeline from "1 knowledge-base table out of 19 actually used" to a real, working,
accuracy-and-latency-conscious retrieval loop — plus **9 real, previously-undiscovered bugs**
found and fixed by actually running the system against live data, not by code review.

Everything below was verified against the live Docker stack (`docker compose up`), not assumed.

## 1. The architecture: "One Embed → Fan Out → Accumulate → Gate"

The design problem going in: the knowledge base has ~6,600 rows of doctor-written content across
19 tables, but only `kb_red_flags` (31 rows) was ever live. The rest — `kb_signals` (285),
`kb_symptoms` (154), `kb_sufficiency_patterns` (195), `kb_routing_rules` (66), `kb_content_chunks`
(5) — were fully embedded and sitting unused, because naively wiring them all in risked blowing the
1.5–2.5s total turn budget (documnets/understanding/09_LATENCY_AND_PERFORMANCE.md) with repeated
embedding calls, and risked accuracy failures by treating single low-confidence matches as fact.

**1. One Embed.** `app/pipeline/orchestrator.py::run_turn` now embeds the user's message exactly
once per turn, right after loading conversation state. That one vector is passed into every check
that needs it (`query_embedding=` parameter added to `check_interlock`, `read_turn`,
`search_self_care_content`) instead of each one re-embedding independently. Measured live: one
embedding call costs ~300-600ms (network-bound, not compute-bound) — reusing it instead of
re-deriving it 3-4 times is what keeps the total budget survivable.

**2. Fan Out.** `app/safety/triage.py::read_turn` (previously a stub returning nothing) now
searches `kb_signals` and `kb_symptoms` with that one embedding, plus `kb_sufficiency_patterns`'
narrow `pattern_name_embedding` for a candidate-pattern guess. These are local Postgres queries —
cheap and fast (single-digit-to-low-double-digit ms) — the cost profile that matters is the
embedding call, not how many tables get searched off the back of it.

**3. Accumulate.** Matched signal/symptom IDs are merged into
`app.pipeline.state.ConversationState.observed_signal_ids` (a field that already existed in the
schema, unused until now) every turn, not overwritten. `app/safety/routing.py::evaluate_routing_rules`
is evaluated against this accumulated set, not just the current turn's matches — a rule needing
evidence from two separate turns can now actually fire once both have been seen.

**4. Gate.** Nothing raw ever reaches the LLM. `orchestrator.py`'s prompt-assembly step only ever
passes one of exactly two kinds of content as `retrieved_guidance`:
   - A confirmed Tier 1 self-care recommendation (`search_self_care_content`, confidence-gated), or
   - Doctor-written `probing_guidance` for the closest candidate pattern — an **instruction for what
     to ask next**, never the pattern's clinical name or diagnosis itself.

This matters because of a finding from live-testing (documented in the "accuracy" discussion this
design is built from): a single ambiguous message can match a signal at ~0.48 similarity to
something as specific as "Prolonged Grief Disorder" — treating that as settled fact would be
actively wrong. Evidence accumulates across turns; only the doctor-written *instruction* for what
to ask is ever surfaced, never a live-generated diagnosis.

## 2. New settings (all in `.env` / `.env.example`, all provisional)

| Setting | Value | What it gates |
|---|---|---|
| `TRIAGE_SIGNAL_THRESHOLD` | 0.45 | `kb_signals`/`kb_symptoms` match confidence |
| `TRIAGE_TOP_K` | 5 | How many candidates triage considers per table |
| `PATTERN_MATCH_THRESHOLD` | 0.30 | `kb_sufficiency_patterns.pattern_name_embedding` match confidence |

**Honest limitation, confirmed live, not hypothetical:** a completely benign message ("I had a
really productive day at work") scored **0.488** similarity to `SIG-228 "Hypomania"` — *higher*
than a genuine stomach-pain message's real match to `SIG-261 "Emotional Pain"` (0.479). There is no
threshold that cleanly separates signal from noise at the individual-signal level from this small a
sample. This is exactly why matched signals accumulate across the whole conversation instead of
being trusted from one turn — see `app/core/config.py`'s comment on `triage_signal_threshold` for
the full numbers.

`RETRIEVAL_CONFIDENCE_THRESHOLD` (0.30) and `REDFLAG_MATCH_THRESHOLD` (0.44) were already
recalibrated in the prior session (see `15_OPEN_QUESTIONS_AND_BLOCKERS.md` #28) — their Python
code-level defaults were also updated to match (were still showing the old guessed 0.75/0.55).

## 3. Every bug found and fixed today, in the order discovered

### Bug 1 — The user's message was never in the prompt sent to the LLM
`app/pipeline/prompt_builder.py`'s `PromptInputs` had no field for the current turn's text at all.
Every reply was generated from persona + a static Clinical Markers checklist only — explaining why
every LLM response looked like a generic opening line regardless of what was actually typed. Fixed
by adding a `user_message` field, placed last in the assembled prompt so it reads as "the specific
thing to respond to now."

### Bug 2 — `routing_rules.py`'s `trigger_condition` was empty for all 66 rules
Real column header: `"Trigger Condition (YOU write — plain English)"` (a genuine em-dash). The
parser looked up the literal string `"Trigger Condition"`, which matches nothing —
`dict.get()` silently returns `None` for a non-matching key. The real doctor-written content (e.g.
*"For Major Depressive Disorder (SIG002-003), no other signal required"*) was sitting in the source
file the whole time, never captured. Same root cause, same fix pattern (find column by prefix, not
a hardcoded literal) as the `red_flags.py` Bot Script bug from the prior session.

### Bug 3 — A completely fabricated "route match" via cross-namespace ID collision
While testing the new routing logic, `PHYS-004` ("Occupational Impairment" — an unrelated physical
symptom) falsely matched `RULE-004` (Premenstrual Dysphoric Disorder), purely because both IDs
contain the digits "004". The initial implementation stripped ID prefixes and compared bare numbers
across `SIG-`, `EM-`, and `PHYS-` namespaces as if they were interchangeable. Fixed by requiring an
explicit `SIG` or `EM` prefix match before comparing numbers at all — `PHYS-` IDs are now correctly
excluded from routing-rule matching entirely (a real, separate future enhancement, not attempted
here, since `RULE-019` was independently confirmed to genuinely reference `PHYS 004` in its own
text — but resolving that safely needs its own dedicated matcher, not a shared number comparison).

### Bug 4 — "EM-codes are confirmed missing" was outdated, not true
`documnets/understanding/04_CONVERSATION_PIPELINE.md` §5 stated every `EM:` reference in the
routing/sufficiency sheets pointed at an undefined code. Checked directly against live data: `EM45`
in `RULE-056`'s trigger condition ("For Life Transitions, EM45 to 54") resolves cleanly to
`kb_symptoms.symptom_id = 'EM-045'` ("Leaving Home"). All of `kb_routing_rules`' Tier 1 rules are
keyed on EM-codes, not SIG-codes — this was the single biggest blocker to Tier 1 (self-care) ever
resolving, and it turned out to already be solvable with data already in the database. Added
`match_symptom_in_trigger_condition` (mirroring the existing SIG matcher) and wired `kb_symptoms`
matches to contribute their own `symptom_id` into the accumulated signal set, not just their
`linked_signal_ids`.

### Bug 5 — Latency self-measurement bug: `cache_check_ms` silently double-counted `embed_ms`
Inserting the new shared-embedding step between the function's start (`t0`) and the pre-existing
`cache_check_ms` calculation (which measured from `t0`) meant the cache-check timing silently
absorbed the embedding call's time too. Fixed with its own dedicated timer.

### Bug 6 — Sarvam LLM adapter: wrong auth header, deprecated model, unparsed SSE stream
Found while wiring the now-added `SARVAM_API_KEY` for real: `app/providers/llm/sarvam.py` sent only
`Authorization: Bearer`, when Sarvam's real API reference specifies `api-subscription-key` as the
native header. The model name `"sarvam-m"` is deprecated per Sarvam's own model list — replaced
with `sarvam-105b-conversations` (their model built for real-time conversational workloads),
now configurable via `SARVAM_LLM_MODEL`, not hardcoded. The streaming response parser yielded raw
SSE lines verbatim — including `data: {...}` JSON blobs and the `data: [DONE]` terminator as if they
were response text — instead of extracting `choices[0].delta.content`. All three fixed and verified
against Sarvam's real API.

### Bug 7 — Sarvam's trailing "usage" SSE chunk crashed on `choices[0]`
A live-only crash: Sarvam sends a final chunk with an empty `choices` array (token-usage stats
only) before `[DONE]`. `choices[0]` raised `IndexError`. Guarded with an empty-list check.

### Bug 8 — `turn_audit_log` writes were silently failing on every single turn
`turn_audit_log.session_id` has a foreign key into `sessions`, but nothing in the AI service itself
ever creates that row (in production, the out-of-scope NestJS backend is meant to). Every audit
write was hitting `ForeignKeyViolationError`, caught and logged (`audit_write_failed`) but never
surfaced — meaning the DPDP-required audit trail had never actually persisted a single row in any
test run. Fixed on the test-harness side only (`frontend/server.py` pre-creates the session row) —
this is a real production risk worth flagging to whoever owns session creation, not something this
codebase should silently paper over.

### Bug 9 — The cache-hit path never logged `triage_tier`
Found while verifying routing worked end-to-end: a cache hit still runs triage + routing (the
non-negotiable rule), but the audit-log write on that path never included the resulting tier,
making it look like routing never ran on a cache hit even though it genuinely had. Fixed.

## 4. Verified working, live, end to end

**Grounded response, using real doctor-written probing guidance** (not LLM improvisation):
> User: *"I recently moved to a totally new city on my own and I feel really isolated, can't seem
> to make any friends here."*
> `matched_signal_ids: {EM-024, PHYS-004, SIG-041, SIG-042, SIG-043, EM-045, EM-052, EM-113}`
> `matched_rule_id: RULE-019`, `triage_tier: 2`
> Response asks about duration, impact on sleep/eating/work, coping mechanisms, and related life
> changes — directly mirroring the real `probing_guidance` content style confirmed in
> `kb_sufficiency_patterns`. Total latency: **1.7s**, inside the 1.5-2.5s budget.

**Safety interlock regression-checked, still correct:**
> *"I have decided to end my life tonight."* → real verbatim RF-019 script, no LLM call, `~0.6s`.

**Safe/positive message regression-checked:**
> *"I had a really nice day today, feeling good."* → no interlock trigger, no false routing match,
> a genuinely contextual (not generic) reply.

## 5. What's still not wired, honestly

- **Self-care recommendation (Tier 1) has real code but hasn't been observed firing yet** — it
  requires a routing match that resolves specifically to `route_to = "Tier 1"`, which needs the
  right combination of matched EM-codes. The mechanism is real and tested in isolation
  (`search_self_care_content` confirmed working in the prior session); it just hasn't come up in
  today's specific test messages. Worth a dedicated test pass.
- **`PHYS-xxx` symptom IDs are not matched against routing rules at all** — confirmed `RULE-019`
  genuinely references `PHYS 004` directly, but resolving this safely needs its own matcher, not a
  shared number-comparison with SIG/EM (see Bug 3). Real, scoped follow-up work.
- **Few-shot examples** (`PromptInputs.few_shot_examples`) are still always empty — the ~20 Bucket-1
  conversation-sample files were never meant to be searched (see doc 19/20), they belong here, and
  this slot has existed unused the whole time. Not touched in this pass.
- **`kb_scenarios`/`kb_layer_content`/`kb_tier_question_bank`** remain unwired — blocked on the
  client's Tier/Layer/emotion-list reconciliation (`15_OPEN_QUESTIONS_AND_BLOCKERS.md` #23), not on
  engineering effort.
- **The range/combination limitation is unchanged** — `match_signal_in_trigger_condition` and the
  new `match_symptom_in_trigger_condition` both only catch literal single-number mentions, not
  ranges like "EM45 to 54" resolving EM46-53 implicitly. Still ~25/285-ish resolution rate, now
  extended to EM-codes with the same ceiling.
