# Mindfully Yours — Knowledge Base Ingestion: Approach

Companion reference to `APPROACH.md`, `CLAUDE.md`, and `LATENCY.md`. This file exists because ingestion quality is the ceiling on everything retrieval can ever do — no amount of clever prompting or a smarter LLM downstream can rescue a badly-chunked knowledge base. Every decision below is judged by its effect on retrieval, not on how reasonable it sounds in isolation.

---

## 1. The principle this file is built on

**Retrieval can never be better than what ingestion gave it to work with.** If a chunk is cut mid-idea, if tags are wrong, if the embedding model doesn't understand the domain vocabulary — retrieval is searching through damaged material, permanently, until someone re-ingests it. This is why every ingestion decision in this file is evaluated by one question: *if the real evaluation queries run against this, does the right chunk come back, fast enough?* — not whether the method sounds reasonable on paper.

Ingestion runs offline, once per document (and again on any KB update) — it does not touch the live 1.5–2.5s conversation latency budget. This means **accuracy is worth spending time on here** in a way it isn't in the runtime path. Don't import runtime speed habits into ingestion; the trade-offs are different.

---

## 2. The pipeline, in order

1. **Document intake & structure parsing** — the raw English document is split along its own structural markers (headings, numbered steps, bullet lists) using pure structural parsing, no AI model. Fast, and effective specifically because a well-organized clinical document already reflects how a human expert grouped ideas.
2. **LLM refines chunk boundaries** — any section still too large or ambiguous is sent to **Sarvam-M** with one instruction: mark natural sub-boundaries so each resulting chunk is one complete, self-contained idea. The model marks *where* to split; it never rewrites the source text. A ~10–15% overlap is added between neighboring chunks so a query landing near a boundary doesn't lose adjacent context.
3. **Metadata tagging** — each chunk gets a concern category, a severity band, a `language` field (`en` for Phase 1, ready for a Hindi row later without a schema change), and a stable `chunk_id`. Tags exist so retrieval can pre-filter before running vector search — narrowing to the relevant category first is both faster and more accurate than searching everything untagged.
4. **Generate embeddings** — each chunk is embedded with **Sarvam embeddings**, batched together rather than one call at a time (batching is free efficiency during an offline step).
5. **Store & index** — chunk text, tags, and vector go into Postgres with pgvector, with a real vector index (not a linear scan) so search speed holds up as the knowledge base grows. Metadata columns are indexed too — this is what makes step 3's pre-filtering actually fast.
6. **Retrieval & grounding evaluation** — the seeded evaluation query set runs against the new index. Two numbers are measured **separately**: retrieval hit-rate (did the right chunk even come back) and grounding accuracy (was the final answer actually supported by it). Measuring only the final answer can hide a broken retrieval step behind a plausible-sounding response from the LLM.
7. **Safety & adversarial validation** — crisis-trigger and jailbreak phrasing run against the safety interlock specifically, independent of the retrieval tests. The interlock is rule-based, so this validates its own logic, not anything upstream in the KB.
8. **Validation gate & go-live** — only if every metric clears its threshold does this version get atomically swapped in as the live index, with the previous version kept for rollback. A failure routes back to the clinical team (more content, fixed tags) — it never reaches real users.

---

## 3. Why these specific choices, not alternatives

- **Structure-aware split before LLM refinement, not LLM chunking alone**: the structural pass is nearly free and handles most of the work correctly on its own, since the source content is already organized by a human expert. The LLM is reserved for the harder cases (sections still ambiguous after structural splitting), which keeps the expensive step targeted rather than applied to everything indiscriminately.
- **An LLM for chunk-boundary decisions, not just embedding similarity**: embedding-based semantic chunking (splitting wherever sentence-to-sentence similarity drops) is a legitimate faster alternative, but an LLM genuinely *understands* that "step 3 of a breathing exercise" belongs with "step 4," where a similarity score might not catch that relationship as reliably. Since this step is offline, there's no cost reason not to use the more accurate method.
- **Sarvam embeddings even though Phase 1 is English-only**: switching embedding models later isn't a config change, it's a full re-embed of the entire knowledge base plus re-validation, because both language versions of a chunk need to live in the same vector space to be comparable. Picking Sarvam now — even if a competitor is marginally better at English in isolation — avoids a costly migration when Hindi is added in Phase 2. This decision should be revisited only if Sarvam's English performance is *meaningfully* behind in the pre-launch evaluation, not marginally.
- **Tagging before embedding search, not embedding search alone**: pure vector search across an entire untagged knowledge base is both slower and more error-prone than filtering to the right category first. Tags are a cheap, deterministic narrowing step that vector similarity alone can't replace.
- **Retrieval hit-rate measured separately from grounding accuracy**: this is the single most important testing discipline in this file. A good LLM response can be generated from the wrong chunk and still sound convincing — only a dedicated retrieval-only metric catches that failure before it reaches a user.

---

## 4. What NOT to do

- Don't chunk by a fixed character/token count as the primary method — it's fast but reliably cuts ideas mid-way, which is a real quality problem for clinical content specifically.
- Don't skip the overlap between chunks — a query landing near a boundary will otherwise lose context that was in the adjacent chunk.
- Don't let the LLM used for chunk-boundary refinement rewrite the source text — it marks split points only. Rewriting introduces a translation-like risk of drifting from the clinical team's exact wording.
- Don't treat ingestion as needing the same speed discipline as the runtime pipeline (`LATENCY.md`) — it's an offline step with a different, much looser time budget. Optimizing ingestion for speed at the expense of accuracy is solving the wrong problem.
- Don't measure only final-answer quality in the validation gate — always measure retrieval hit-rate as its own number.
- Don't switch the embedding model without accounting for the full re-embed + re-validation cost across the whole knowledge base, not just the new content.

---

*Companion file to `APPROACH.md`, `CLAUDE.md`, and `LATENCY.md` — derived from the finalized Mindfully Yours architecture (OpenXcell Technolabs Pvt. Ltd. / Mindfully Yours Private Limited). Keep all four files in sync if any decision here changes.*
