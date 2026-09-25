# 13 — Language Approach: English First, Hindi by Design

## 1. Phase 1: English only — a deliberate risk-reduction choice

This isn't because Hindi is an afterthought — it's a deliberate choice to prove conversation, triage, and the safety interlock work correctly in one language before adding a second. Every stored record and logged row carries a `language` field from day one specifically so Phase 2 doesn't require a schema migration — adding Hindi later is additive, not a rebuild.

**Concrete implementation rules for Phase 1**:
- Every stored chunk and every logged row carries a `language` field, set to `en` everywhere.
- Do not hardcode English-only assumptions into retrieval or prompt-assembly logic.
- Don't skip the field because it's unused today.

## 2. Phase 2: adding Hindi — the plan, already decided

- The KB is translated **once, offline** using Sarvam Translate — never live/per-query, since that adds cost and latency to every single turn.
- Both language versions are embedded into the **same shared vector index** — this is why the embedding model (Sarvam) was chosen even for the English-only Phase 1: switching embedding models later means a full re-embed of the whole KB plus re-validation, since both language versions of a chunk need to live in the same vector space to be comparable.
- The crisis/interlock vocabulary for Hindi/Hinglish is **hand-authored with the clinical team, never machine-translated** — for the same reason the English red-flag vocabulary in [08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) is hand-authored, not model-generated: crisis-detection language is too safety-critical to risk translation drift.
- **The runtime pipeline itself doesn't change.** The same models already handle both languages — the LLM simply replies in whatever language the user just used, independent of which language the retrieved chunk happened to be stored in. Don't build a separate "reply language" configuration; let the model's own instruction-following handle it.
- A dedicated Hindi test pass runs through the same pre-launch validation gate ([07_INGESTION_PIPELINE.md](07_INGESTION_PIPELINE.md) §2, step 6-8) before Hindi goes live.
- No change to the runtime pipeline, the abstraction layer, or any app UI — per `Mindfully_Yours_Phase1_English_Architecture.pdf`'s explicit Phase 2 panel: *"This is why Phase 1 is built with a language field from day one — adding Hindi later is additive, not a rebuild."*

## 3. ⚠ An open decision the source PDFs disagree on

The three architecture PDFs present Hindi/Hinglish query handling differently — this needs to be resolved explicitly, not assumed:

- **`Phase1_Final.pdf` and `Phase1.pdf`** frame this as **two valid options still open for the technology review**:
  - **Option A — Bilingual KB (marked recommended ✓)**: KB translated to Hindi once, offline; query embedded exactly as spoken, no translation step; one-time fixed cost; no extra latency hop.
  - **Option B — English-only KB**: KB stays English-only, simpler to set up; every Hindi/Hinglish query translated to English before retrieval; recurring cost that grows with every Hindi turn; +1 network hop on every voice turn.
  - Shared note: *"Either way, the LLM always replies in the user's own language — that part doesn't change. Option A costs less and stays faster at scale; Option B is a simpler fallback if bilingual ingestion isn't ready at launch."*
- **`Phase1_English_Architecture.pdf`** presents this as **already settled** — a single "Phase 2 (Later): Adding Hindi" roadmap panel (explicitly labeled "not built in Phase 1, shown here for context") that commits to what is functionally Option A (bilingual KB, offline translation), with no live/per-query translation option mentioned at all.

**Recommendation**: build toward Option A (bilingual KB) as the design target, since it's both the markdown files' consistent recommendation and the lower-cost/lower-latency path — but confirm explicitly with the client which architecture document is canonical before treating Option B as fully ruled out. See [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md).

## 4. A wording inconsistency found in the source PDFs, worth knowing about

`Phase1_Final.pdf` and `Phase1.pdf`'s runtime step 10 ("Hosted LLM call") both literally say *"Replies in Hindi and English both"* — despite both documents being titled "Phase 1: English only." This reads as a copy-paste leftover from a bilingual template. `Phase1_English_Architecture.pdf` corrects this to *"Replies in English — same model handles Hindi later,"* which is consistent with the actual Phase 1 scope. **Treat the corrected wording as accurate; the other two documents' wording is very likely a documentation bug, not a hidden Phase 1 bilingual requirement** — nothing else anywhere in the source material suggests Phase 1 ships Hindi.

## 5. Latency, once Hindi ships

Per [09_LATENCY_AND_PERFORMANCE.md](09_LATENCY_AND_PERFORMANCE.md) §11: measure latency broken down by language once Hindi is added — don't assume both languages perform identically.

## 6. What NOT to do

- Don't translate live, per-query, as the primary path for any language — slower and costlier than translating the source content once.
- Don't build Hindi support as a bolt-on later if it means a schema migration — the `language` field should already be there from Phase 1.
- Don't build a separate "reply language" configuration — the model's own instruction-following already handles this.
- Don't switch the embedding model between Phase 1 and Phase 2 without accounting for a full KB re-embed + re-validation.

---
*Source material: `documnets/approch/APPROACH.md` §6, `documnets/approch/CLAUDE.md` §5, and the Hindi/Hinglish handling panels in all three Phase 1 architecture PDFs (full extraction, including the cross-document discrepancy noted in §3-4 above).*
