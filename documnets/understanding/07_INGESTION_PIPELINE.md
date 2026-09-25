# 07 — Knowledge Base Ingestion Pipeline (offline, script-driven)

> This runs once per document, and again on any KB update — it never touches the live 1.5–2.5s conversation latency budget. **Accuracy is worth spending time on here in a way it isn't in the runtime path.** Full detail on what actually gets embedded per-sheet lives in [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md); this file is the pipeline mechanics.

## 1. The governing principle

**Retrieval can never be better than what ingestion gave it to work with.** If a chunk is cut mid-idea, if tags are wrong, or if the embedding model doesn't understand the domain vocabulary, retrieval is permanently searching through damaged material until someone re-ingests it. Every ingestion decision is judged by one question: *if the real evaluation queries run against this, does the right chunk come back, fast enough?* — never by whether the method sounds reasonable in isolation.

## 2. The 8-step pipeline, in order

1. **Document intake & structure parsing** — the raw document is split along its own structural markers (headings, numbered steps, bullet lists) using pure structural parsing, **no AI model**. Fast, and effective specifically because a well-organized clinical document already reflects how a human expert grouped ideas.
2. **LLM refines chunk boundaries** — any section still too large or ambiguous after step 1 is sent to **Sarvam-M** with one instruction: mark natural sub-boundaries so each resulting chunk is one complete, self-contained idea. **The model marks *where* to split; it never rewrites the source text.** A ~10-15% overlap is added between neighboring chunks so a query landing near a boundary doesn't lose adjacent context.
3. **Metadata tagging** — each chunk gets a concern category, a severity band, a `language` field (`en` for Phase 1, ready for a Hindi row later with no schema change), and a stable `chunk_id`. Tags let retrieval pre-filter before vector search — narrowing to the relevant category first is both faster and more accurate than searching everything untagged.
4. **Generate embeddings** — each chunk embedded with **Sarvam embeddings**, batched together (batching is free efficiency during an offline step, not a runtime concern).
5. **Store & index** — chunk text, tags, and vector go into Postgres+pgvector with a real vector index (not a linear scan), so search speed holds up as the KB grows. Metadata columns are indexed too, since that's what makes step 3's pre-filtering fast.
6. **Retrieval & grounding evaluation** — the seeded evaluation query set runs against the new index. **Two numbers measured separately**: retrieval hit-rate (did the right chunk even come back) and grounding accuracy (was the final answer actually supported by it). Measuring only the final answer can hide a broken retrieval step behind a plausible-sounding LLM response.
7. **Safety & adversarial validation** — crisis-trigger and jailbreak phrasing run against the safety interlock specifically, independent of the retrieval tests, since the interlock is rule-based and this validates its own logic, not anything upstream in the KB.
8. **Validation gate & go-live** — only if every metric clears its threshold does this version get atomically swapped in as the live index, with the previous version kept for rollback. A failure routes back to the clinical team (more content, fixed tags) — **it never reaches real users.**

This 8-step pipeline matches the architecture PDFs' sections ②③⑤: KB Ingestion Pipeline → Status: Live badge → Pre-Launch Testing & Validation gate. The PDFs additionally flag one open concern directly on the ingestion diagram: **"⚠ Needs KB structure guideline"** on the "Extract & normalize" step — meaning the exact structural-parsing rules per document type are not yet fully specified and should be nailed down before automating step 1. See [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md).

## 3. Why these specific choices, not alternatives

- **Structure-aware split before LLM refinement, not LLM chunking alone**: the structural pass is nearly free and handles most of the work correctly since source content is already organized by a human expert. The LLM is reserved for genuinely ambiguous cases, keeping the expensive step targeted, not applied indiscriminately.
- **An LLM for chunk-boundary decisions, not embedding-similarity chunking**: an LLM genuinely *understands* that "step 3 of a breathing exercise" belongs with "step 4," where a similarity-drop heuristic might not catch that relationship. Since this step is offline, there's no cost reason not to use the more accurate method.
- **Sarvam embeddings even though Phase 1 is English-only**: switching embedding models later isn't a config change — it's a full re-embed of the entire KB plus re-validation, because both language versions of a chunk need to live in the same vector space to be comparable. Picking Sarvam now avoids a costly migration when Hindi is added. Revisit only if Sarvam's English performance is *meaningfully* behind in the pre-launch evaluation, not marginally.
- **Tagging before embedding search**: pure vector search across an entire untagged KB is slower and more error-prone than filtering to the right category first — tags are a cheap, deterministic narrowing step vector similarity alone can't replace.
- **Retrieval hit-rate measured separately from grounding accuracy**: the single most important testing discipline here — a good LLM response can be generated from the wrong chunk and still sound convincing; only a dedicated retrieval-only metric catches that.

## 4. Per-document-type chunking technique (the real, already-decided mapping)

This table is the operational answer to "how do I chunk *this specific file*" — see [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) for the full embed/rule/verbatim breakdown per sheet; this is specifically about *chunk boundaries*.

| Document | Technique | Why |
|---|---|---|
| `Kb_Phase_I_9.csv` (Sufficiency) | **Structure-aware only — one row = one chunk, exactly as given.** No LLM re-chunking. | Client already segmented this perfectly; each row is one complete, self-contained pattern |
| `Kb_Phase_I_A1.csv` (Signal Legend), `A2.csv` (Symptom Map), `C11.csv` (Routing Rules), `Kb_Phase_I_7.csv` (Red Flags), `Kb_Phase_I_17.csv` (Fallback) | **One row = one chunk** (same structural logic as above, confirmed again in `CHUNKING_EMBEDDING_STRATEGY.md`) | All six real KB sheets are pre-segmented, clean, tabular client data |
| `Convo_Samples.pdf` | One full conversation = one chunk, split at existing scenario/page breaks, tagged by scenario category | Splitting mid-conversation destroys what makes this material useful — watching a question sequence unfold |
| Clinical Markers Reference Table | **Not chunked** — used whole, as a single static prompt block | 10 items, always needed together; chunking implies partial/conditional retrieval, the wrong access pattern here |
| Knowledge_Base_Directory | **Not chunked, not ingested at all** | Internal build-planning document, never reaches the AI |
| Filler Phrase Library | **Not chunked** — a lookup table by situation type, not embedded content | Selection is rule-based (match situation + expected gap → category), not a meaning-based search problem |
| Future Phase III/IV content (clinical guidance, self-care library) | **The one case needing LLM-based chunk-boundary refinement** (step 2 above, in full) | Expected to arrive as flowing prose, not a pre-segmented table — natural boundaries won't already exist |

**The one-sentence rule underlying this table**: use the cheap, structure-respecting method whenever the source is already organized into complete units; reserve the LLM-based method for genuinely unstructured prose where boundaries aren't given for free.

## 5. What NOT to do

- Don't chunk by fixed character/token count as the primary method — fast, but reliably cuts ideas mid-way, a real quality problem for clinical content.
- Don't skip the overlap between chunks — a query landing near a boundary will lose context otherwise.
- Don't let the LLM boundary-refinement step rewrite the source text — it marks split points only.
- Don't apply runtime speed discipline to ingestion — it's an offline step with a much looser time budget; optimizing for speed here at the expense of accuracy solves the wrong problem.
- Don't measure only final-answer quality in the validation gate — always measure retrieval hit-rate as its own number.
- Don't switch the embedding model without accounting for the full re-embed + re-validation cost across the *whole* KB, not just new content.

---
*Source material: `documnets/approch/INGESTION.md` (full), `documnets/knowledgebase/CHUNKING_EMBEDDING_STRATEGY.md` §5, and section ②③⑤ of the Phase 1 architecture PDFs.*
