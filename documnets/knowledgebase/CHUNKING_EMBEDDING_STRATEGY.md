# Mindfully Yours — Chunking & Embedding Strategy (All 6 KB Sheets)

Companion reference to `APPROACH.md`, `CLAUDE.md`, `LATENCY.md`, `INGESTION.md`, `LIVEKIT.md`, `DATA_PROTECTION_SECURITY.md`, `KNOWLEDGE_BASE_CONTENT.md`, `CONVERSATION_REASONING_FLOW.md`, `END_TO_END_RAG_APPROACH.md`, and `SIGNAL_ENRICHMENT_APPROACH.md`. This file answers one specific, practical question: **for every real sheet in the knowledge base, what gets embedded, what doesn't, and why** — so a coding agent can implement this without guessing.

---

## 1. The one rule that decides everything in this file

**Ask: is this something a user actually says, or something the system measures?**

- If it's **phrasing** — real words a person might use — it belongs in the vector database, embedded for semantic search.
- If it's a **measurable condition** — a signal count, a turn count, a confidence score, a fixed threshold — it's a rule to check in code, and embedding it would be solving the wrong kind of problem entirely.

Every decision below comes from applying this one question to real data, not from a general RAG textbook rule.

**In simple terms**: if a person could actually say it out loud, search for it by meaning. If it's a number the system is counting (how many turns, how confident it is), just check that number directly — don't try to "search" for it.

---

## 2. The two merged files — quick recap, then the new sheets

### Merged Signal Profile (A1 + C11) and Merged PhysEmotional Profile (A2 + A1)

Already covered in depth in `SIGNAL_ENRICHMENT_APPROACH.md`. Summary for this file's purposes:

- **Embed**: `phrasings` (A1) and `how_described` (A2) — real example phrasings, genuine semantic-search content.
- **Don't embed, attach as precomputed fields on the same chunk**: severity, red-flag status, matched routing rules, linked signal concepts. These arrive already resolved, so retrieval never needs a second lookup.
- **One chunk per row** — the client's own structure already does the chunking; no further splitting needed.

**In simple terms**: each signal or symptom becomes one complete "card" — the AI searches by how something is *said*, and gets back everything else (how serious, is it dangerous, what rule applies) already attached to that same card.

---

## 3. Signal Sufficiency (195 rows) — mostly rules, one narrow embedding case

### What NOT to embed
`minimum_signals`, `must_have_signals` — exact lookup criteria, checked directly once a pattern is identified. Searching for these would be slower and less reliable than reading them off a table.

### What to fetch by ID, never search for
`when_to_keep_probing` (the exact next-question guidance) and `graceful_exit_trigger` — once the system knows which of the 195 patterns applies, these are retrieved directly, not searched.

### The one narrow case worth embedding
`pattern_name` (e.g., "Persistent Loneliness," "situational low mood") — **only** for the moment early in a conversation when the system doesn't yet know which pattern applies. Embedding the 195 pattern names lets a rough semantic match narrow down the likely candidates before the exact Minimum/Must-Have signal check takes over.

**In simple terms**: think of the 195 patterns as folder names in a filing cabinet. You don't need to "search" the folder's contents by meaning — but the very first time, finding the *right folder* to open can use a quick meaning-based guess, narrowed down before you check its exact rules.

**Known gap, carried over from `KNOWLEDGE_BASE_CONTENT.md`**: 2 of these 195 rows have `"check----------"` instead of a real tier — exclude these from the pattern-name embedding set until the client fills them in, since embedding a placeholder as if it were real content would let the system match against something that isn't actually defined yet.

---

## 4. Red Flags (31 rows) — the trigger phrases are the one genuinely rich embedding case

**This sheet works exactly like `A1`'s signal phrasings, for the same reason.**

### Embed this
`trigger_phrases` — real examples, deliberately written to include indirect and disguised language, not just obvious statements. This is a genuine "does this match, by meaning, something dangerous" search problem — exactly what embeddings are for.

### Never regenerate, always fetch verbatim
`bot_script` — the client explicitly wrote these to be used word-for-word, not as guidance for the LLM to phrase in its own words. Fetched by the matched `flag_id`, immediately, the instant a match crosses whatever confidence threshold is set for safety-critical matching (this threshold should be deliberately more permissive/sensitive than a normal RAG match — a false positive here costs a moment's extra caution; a false negative costs a missed danger signal).

### Don't embed
`immediate_action`, `escalation_target` — precomputed fields, attached to the same chunk as the matched trigger phrase, not separately searched.

**In simple terms**: this sheet is trained to notice danger even when someone doesn't say it plainly — so the actual words matter and get searched by meaning. But once a match is found, the AI doesn't write its own response — it uses the exact safety script the client already wrote, every time, no exceptions.

---

## 5. Fallback & Safety Net (100 rows) — almost none of this gets embedded

**This is the sheet most likely to be built wrong if treated like the other four.** Look at a real trigger condition from the actual data:

> *"15+ turns; user provides short, non-specific responses; no identifiable Signals or Rules; confidence below threshold"*

**This is not something a user says.** It's a description of the conversation's own shape — a turn count, a response-length pattern, a confidence score. There is no phrase here to search for by meaning.

### Don't embed the triggers at all
`trigger_condition` — evaluate this as code, checking the conversation's actual running state (turn count, recent response length, current confidence score) against these thresholds. This is closer to how the safety interlock works than to how retrieval works.

### Fetch verbatim once triggered
`bot_script`, `escalation_path` — same principle as Red Flags: once a fallback scenario is confirmed by checking the conversation state, use the client's exact wording, don't paraphrase.

**In simple terms**: this sheet isn't listening for anything the person says — it's watching the shape of the conversation itself: is it dragging on too long without progress, are the answers getting shorter, is the AI's own confidence dropping. None of that is a "phrase" to search for — it's numbers the system is already tracking, checked directly.

---

## 6. The complete picture — one table, all six sheets

| Sheet | Embed (semantic search) | Rule/lookup (code, not search) | Fetch verbatim (never paraphrase) |
|---|---|---|---|
| Merged Signal Profile (A1+C11) | `phrasings` | severity, red_flag, matched_rules | — |
| Merged PhysEmotional Profile (A2+A1) | `how_described` | severity fields, linked red-flag status | — |
| Signal Sufficiency | `pattern_name` (narrow use only) | min/must-have signals, thresholds | `when_to_keep_probing` guidance (fetched by ID) |
| Red Flags | `trigger_phrases` | — | `bot_script` |
| Fallback & Safety Net | *(nothing)* | `trigger_condition` (turn count, confidence, etc.) | `bot_script` |

**The pattern across the whole table**: embedding shrinks as you move from "individual signs a person expresses" toward "properties of the conversation as a whole." The most embeddable content is the most human and specific; the least embeddable content is the most systemic and numeric.

---

## 7. Why this is the efficient approach, not just the correct one

- **Fewer embeddings, not more.** Most of the KB's content is precise, structured logic — embedding all of it "to be safe" would bloat the vector index with content that's never actually searched, slowing down every real query for no benefit.
- **Fast paths stay fast.** Rule and lookup checks (Sufficiency thresholds, Fallback conditions) are simple comparisons against already-known values — this is exactly the kind of operation that should never touch the LLM or a vector search, consistent with `LATENCY.md`'s core principle of keeping the critical path lean.
- **Safety-critical content never depends on model generation.** Red Flag and Fallback bot scripts are fetched, not generated, which means their exact wording is guaranteed correct every time — no risk of the LLM softening or rephrasing language the clinical team deliberately chose.

---

*Companion file to `APPROACH.md`, `CLAUDE.md`, `LATENCY.md`, `INGESTION.md`, `LIVEKIT.md`, `DATA_PROTECTION_SECURITY.md`, `KNOWLEDGE_BASE_CONTENT.md`, `CONVERSATION_REASONING_FLOW.md`, `END_TO_END_RAG_APPROACH.md`, and `SIGNAL_ENRICHMENT_APPROACH.md`. Reflects the real content of all six client KB sheets, verified against `Kb_Phase_I.xlsx`. Update this file if the EM-code legend arrives, or if the Sufficiency sheet's two placeholder rows are resolved.*
