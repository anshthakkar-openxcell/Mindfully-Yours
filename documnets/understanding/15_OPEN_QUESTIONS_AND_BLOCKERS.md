# 15 — Open Questions, Blockers & Discrepancies (consolidated)

> Every item below was found either explicitly stated in the source material, or discovered by directly parsing the real files during this documentation effort. Ranked roughly by how much it blocks implementation. **Nothing here should be silently resolved by engineering judgment — each needs either client input or an explicit internal decision before the affected feature ships.**
>
> **Update**: items #1, #13, and #15 have since been independently re-confirmed against an updated pass of `KNOWLEDGE_BASE_CONTENT.md` (v2), which corroborates this folder's original direct-CSV findings and adds detail this folder didn't originally have (the specific 3-row count on the hardcoded-name issue, and the exact scenarios inside Section D). Both this file and [08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) have been updated accordingly — treat those two items as settled facts about the data now, not open discoveries.

## Tier 1 — Hard blockers (safety-critical or structurally required)

### 1. Four Red Flags have no bot script at all — RF-028, RF-029, RF-030, RF-031
**Confirmed on a second, independent verification pass — this is the single most important open item in the whole knowledge base.** Covering *Suspected violence/unsafe environment*, *History of violence*, *Suspected rape*, *Sexual molestation* — some of the most severe categories in the whole KB. Per [01_PROJECT_OVERVIEW.md](01_PROJECT_OVERVIEW.md) principle #2, the LLM must never freelance a safety-critical response. **This cannot ship as-is.** Action: get verbatim bot scripts from the clinical team for these 4 flags before any red-flag pathway goes live. **Until then, application code must treat a matched flag with an empty `bot_script` as a hard alert routed directly to a human, never a silent LLM-generated fallback** — the one place in this whole system where "the AI will just phrase something reasonable" is not an acceptable substitute. See [08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) §4.

### 2. `EM` signal codes are confirmed undefined as a proper legend
Every `EM:` reference throughout `Kb_Phase_I_9` (Sufficiency) and `Kb_Phase_I_C11` (Routing Rules) points at a code with no `A1`-style legend (ID + clinical concept + 5-10 example phrasings). The 133 `EM-` rows that *do* exist, in `A2`, are something different — free-text category labels (e.g. "Motivation issue," "Usually triggers by death"), not a matchable phrase legend. **Action needed from the client**: an `EM` legend structured the same way `A1` is (ID, concept, example phrasings), or confirmation that the existing `A2` EM rows are meant to serve this purpose as-is (in which case the embedding-based signal pre-filter in [04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md) Step A needs a different matching strategy for EM references than for SIG references, since there's no phrase to embed). Referenced throughout [05](05_KNOWLEDGE_BASE_DEEP_DIVE.md), [06](06_SIGNAL_ENRICHMENT_PIPELINE.md), [08](08_SAFETY_INTERLOCK_AND_TRIAGE.md).

### 3. Phase III/IV content — RESOLVED (largely), as of the Sept 2026 "convo data" drop
**Update**: the client has since provided a 46-file drop of clinical-team working documents (`documnets/knowledgebase/convo data/`) that substantially fulfills this gap — see [18_NEW_CONVO_DATA_CATALOG.md](18_NEW_CONVO_DATA_CATALOG.md) for the full catalog. Phase IV (self-help tools) is now well-covered (a finished DBT workbook, a brain-dump worksheet, and a broad self-help conversation/toolkit library). Phase II (framework/conversation samples/emotion content) is extensively covered. Phase III (clinical guidance/psycho-education) is partially covered, with some files having real content gaps (see items #23-24 below). [04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md) Step F's Tier 1 recommendation can now be built against real content, not just synthetic placeholders — though the new taxonomy-reconciliation items below (#22) should be resolved first for a clean data model.

### 4. Rule-matching between `A1` and `C11` is only 25/285 complete
The numeric regex join only catches direct single-number mentions; most of the 66 routing rules reference ranges/combinations/exclusions in free text ("SIG 001-017 minus SIG002-003") that a simple matcher can't expand. **Needs a real range/combination parser, or the client's direct input**, before the enrichment output in [06_SIGNAL_ENRICHMENT_PIPELINE.md](06_SIGNAL_ENRICHMENT_PIPELINE.md) can be treated as complete.

### 5. `Rule-025` is incomplete in the source data
Trigger condition exists ("For Factitious Disorder, SIG 080, 271-277") but `Route To`, `Priority`, `Override Reason`, and `Trajectory Factor` are all blank. Exclude from the rules engine until the client fills this in. See [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) §4.

### 6. Two Signal Sufficiency rows have a literal `check----------` placeholder instead of a real Tier
"Recurrent Mood Episode Patterns" and "patterns of major depressive episodes." Exclude from pattern-matching until resolved. See [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) §6.

## Tier 2 — Architectural decisions needed before building the affected feature

### 7. 3-tier vs. 4-state crisis model — the architecture PDFs disagree with each other
`Phase1_Final.pdf` and `Phase1.pdf` use a **3-tier model** where Tier 3 *is* SOS/crisis (one combined state). `Phase1_English_Architecture.pdf` describes a **4-state branch**: "Tier 1/2 → self-care continues · Tier 3 → practitioner match & booking (on consent) · Crisis → immediate screen + human alert + safe hold" — treating Tier 3 (practitioner referral) and Crisis (immediate human intervention) as two *separate* escalation paths. **This changes how many distinct routing outcomes the escalation state machine needs.** Must be confirmed with the client before finalizing the `sessions.assigned_tier` schema design in [11_DATA_MODEL_AND_STORAGE.md](11_DATA_MODEL_AND_STORAGE.md) §4. See [08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) §3.

### 8. Avatar vendor: three different answers across the source material
`Phase1.pdf` (earlier draft) → **Spatius.ai**, no cost gate. `Phase1_Final.pdf` and `Phase1_English_Architecture.pdf` (later) → **HeyGen**, with an explicit opt-in + cost/plan gate. `APPROACH.md`'s own narrative preference → **2-D character (Rive/Live2D)**, specifically to avoid a realistic-avatar render fee. **Resolve explicitly at the technology review** — this materially affects both cost (per-render fees) and the adapter interface shape in [03_TECH_STACK.md](03_TECH_STACK.md) §3.

### 9. STT vendor: dual (Deepgram/Sarvam) vs. single (Deepgram only)
`Phase1_Final.pdf` and `Phase1.pdf` list "Deepgram/Sarvam" as a joint STT option; `Phase1_English_Architecture.pdf` (the more internally-consistent, later-looking variant) lists Deepgram only. Confirm before hardcoding a single-STT-vendor assumption into the provider abstraction layer.

### 10. Hindi query-handling: still an open decision (Option A/B) in two PDFs, already settled in the third
See [13_LANGUAGE_PHASING.md](13_LANGUAGE_PHASING.md) §3 for full detail. Recommendation is Option A (bilingual KB, offline translation) since it's the lower-cost/lower-latency path and what the "settled" document already commits to — but confirm which architecture document is canonical.

### 11. Guardrail Questions — is it a distinct KB component, or already folded into Fallback & Safety Net?
`Knowledge_Base_Directory` lists "Guardrail questions/Conversations" as a separate Phase I deliverable, but no standalone file with that exact name was received — its content may already be inside `Kb_Phase_I_17` (Fallback & Safety Net). **Worth a direct confirmation rather than assuming** — per `KNOWLEDGE_BASE_CONTENT.md` v2 §5.

### 12. Whether `Convo_Samples.pdf` is a close script or a loose style guide
Affects how tightly [04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md) Step E's tone examples should be followed, and how [17_PERSONA_AND_CONVERSATION_STYLE.md](17_PERSONA_AND_CONVERSATION_STYLE.md) should be used in prompt engineering. Still open per the client conversation record in `END_TO_END_RAG_APPROACH.md` §6.

## Tier 3 — Data hygiene items (should be fixed before this content ships to production, low risk to structural design)

### 13. `Kb_Phase_I_17.csv` has a real person's name (e.g. "Shreya") hardcoded into **three** escalation paths — confirmed on re-verification, not just one
Phrasing includes *"Flag for [name] with full signal breakdown"* and *"priority Tier 2 referral."* Every other row in the sheet routes to a role (e.g. "Tier 2 clinician," "on-shift crisis team"), not a named individual. Both a data-hygiene problem and a minor privacy exposure if it reaches production documentation as-is — scrub and replace with role-based routing before this table becomes a permanent implementation reference. See [08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) §5.

### 14. Multiple uncorrected typos/grammar errors in client-authored bot scripts, meant to be used verbatim
E.g. "who help you understand they confusing aspects of your life," "Ill be right here" (missing apostrophe), "Would to be comfortable" in `Convo_Samples.pdf`. Since these scripts are meant to ship close-to-verbatim (per [08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md)), flag them to the clinical team for correction rather than silently fixing them in code.

### 15. `Kb_Phase_I_17.csv`'s actual structure has 4 sections + a separate 84-row disorder matrix, not the 3 sections the design markdown originally described — now confirmed on re-verification, ~70% more content than first documented
The design markdown's first pass described Sections A/B/C only. The real file also has **Section D — Special population scenarios, adults 20-45** (new parent/perinatal presentation, bereavement, burnout/chronic workplace stress, identity or life-transition distress) and an entirely separate disorder-specific fallback matrix (15 groups, 84 rows, its own `Disorder / Scenario` header) appended below — a distinct table, not part of A-D's structure. Design docs have been updated to reflect this ([08_SAFETY_INTERLOCK_AND_TRIAGE.md](08_SAFETY_INTERLOCK_AND_TRIAGE.md) §5, [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) §7); implementation should account for both tables when ingesting this sheet.

### 16. ID casing/format inconsistencies across the KB, requiring normalization at ingestion
- `C11`'s Rule IDs: `RULE-001`..`RULE-014` uppercase, then silently `Rule-015` onward title-case.
- `A1`'s last signal: `Sig-285` lowercase, inconsistent with `SIG-` elsewhere.
- `A2`'s `PHSY-018`..`021` — a transposed-letter typo of `PHYS-`.
- SIG/EM/PHYS reference formatting varies across at least 5 styles in free text (`SIG: 001`, `SIG 001-017`, `SIG002-003`, `SIG-168`, unpadded `SIG: 1`).
- Red Flag values in `A1`: mixed `Yes/yes/No/no`/blank casing.
All of this needs aggressive normalization in the ingestion parser — see [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) §0 for the full list.

### 17. Encoding: raw KB CSVs are Windows-1252 (cp1252), not UTF-8
Reading as UTF-8 corrupts special characters (em-dashes, apostrophes). Any ingestion script must decode explicitly with `encoding='cp1252'`.

### 18. Discrepancy in Signal Sufficiency row count: 185 (raw CSV) vs. 195 (merged workbook)
The raw client export has 185 populated data rows; the authoritative merged workbook (`Mindfully_Yours_Merged_Signal_Profile (2).xlsx`) independently reports 195 rows in its "Signal Sufficiency (full)" sheet. Treat 195 as more current, but confirm with the client which is authoritative before finalizing row counts in any documentation or test fixtures.

### 19. "Replies in Hindi and English both" wording bug in two of the three architecture PDFs
`Phase1_Final.pdf` and `Phase1.pdf`'s runtime step 10 literally says this despite being titled "English only." Almost certainly a copy-paste leftover — `Phase1_English_Architecture.pdf` corrects it to "Replies in English." Treat as a documentation bug, not a hidden requirement, but worth a one-line confirmation with the source's author.

## Tier 4 — Scope/vendor items with no further detail given anywhere in the source material

### 20. Razorpay (payments) and Onfido (identity/KYC) — named once, with zero elaboration
Both appear only in the architecture PDFs' "Provider adapters" line. What exactly is being paid for (subscriptions? practitioner session fees?) and whose identity Onfido verifies (practitioners onboarding? user age/identity checks?) is not specified anywhere else in the source material. Needs a direct scoping conversation before building payment/KYC flows.

### 21. No formal roles matrix, screens, wireframes, or timeline/milestone document exists in any source file
The three architecture PDFs are single-page infographic diagrams of the AI processing architecture — none contain UI mockups, a staffing plan, or dated deliverables. Roles (end user, practitioner, clinical team, OpenXcell engineering, admin, client's on-shift crisis team) are only implied inside the diagram text. [14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md](14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md) reconstructs a feature/role breakdown from what's implied, but it is inference, not a client-approved spec — validate before treating it as final.

### 22. `⚠ Needs KB structure guideline` — flagged directly on the architecture diagram itself
The "Extract & normalize" step of the KB Ingestion Pipeline (section ② of the architecture PDFs) carries this exact warning icon/label in the source diagram — meaning the exact structural-parsing rules per document type are acknowledged as incomplete by the diagram's own author, not just by this analysis. Nail this down before automating ingestion step 1.

## Tier 5 — New items from the September 2026 "convo data" drop (see [18_NEW_CONVO_DATA_CATALOG.md](18_NEW_CONVO_DATA_CATALOG.md) for full detail)

### 23. Three separate axes need reconciling before the data model is finalized: Tier vs. Layer vs. Severity, and three unreconciled emotion lists
The new drop introduces a **Layer I-IV** conversational-depth model (separate from the existing **Tier 1/2/3** severity model) and a **Mild/Moderate/Severe/Crisis** severity scale used in `Pathway For AI In Different Situations - Tanisha.docx` that doesn't map 1:1 to Tier 1/2/3. It also introduces a **22-item flat scenario-category list** that doesn't match the ~9-category tree in `List of Scenarios - Tanisha.docx`, and **three independently-authored emotion taxonomies** (19 labels, 9 labels, and a 28-label list — confirmed, via direct extraction, to be independently shared by both `Layer II Question Bank.docx` and `Layer III.docx`) with only partial overlap. **None of this should be modeled as a final canonical field in the database until a client/clinical-team session reconciles all of it into one vocabulary** — the tables in [21_NEW_CONTENT_INGESTION_PLAN.md](21_NEW_CONTENT_INGESTION_PLAN.md) are deliberately built to hold all sources tagged separately (e.g. `kb_emotion_phrases.source_list`, `.canonical_emotion_group` left `NULL`) specifically so this reconciliation is a reviewed update, not a rebuild. See [18_NEW_CONVO_DATA_CATALOG.md](18_NEW_CONVO_DATA_CATALOG.md) §2-3.

**Plain-language questions to put to the client's clinical team to resolve this** (deliberately non-technical — for the team to answer, not a developer):

*About the emotion lists:*
1. We found three different lists of "emotions" across your documents — one with 19 items, one with 9 items, and one with 28 items (used consistently in two of your question-bank documents). Is the 28-item list your intended final list? Or is there a different, official list we should be using instead?
2. If none of these three is final, could someone review all the emotions across these documents and send back one confirmed list to build against?
3. Are any of the emotion names meant to mean the same thing under a different label (for example, is "Tensed" the same as "Anxiety"? Is "Concerned" the same as "Worry"?) If so, which name should we keep?

*About "Layers" vs. "Tiers" vs. "Severity":*
4. Your materials describe conversations moving through "Layers" (I through IV) as they go deeper, and separately use a "Tier" system (1, 2, 3) for how serious a situation is. Can you confirm these are two completely separate ideas — Layer meaning how deep the conversation has gone, Tier meaning how serious the situation is — and not meant to be combined into one single scale?
5. One document introduces a third scale — "Mild / Moderate / Severe / Crisis" — for describing severity. Is this meant to replace the Tier 1/2/3 system, sit alongside it, or is it an earlier draft that Tier 1/2/3 already superseded? If it sits alongside Tier 1/2/3, does "Crisis" always mean the same thing as "Tier 3," or something different?
6. Related to the above: some of your documents treat "Tier 3" and "Crisis/SOS" as the exact same outcome, while one document treats them as two separate, distinct outcomes. Which is correct — should there be 3 severity outcomes total, or 4?

*About the category/scenario lists:*
7. We found a large list of 30+ life-situation categories in one document (things like "Relationship Issues," "Career Issues," etc.), and a different, shorter list of about 22 categories in another document meant for sorting what a conversation is about. Should these be merged into one list? If they disagree on a category name or grouping, which one should we follow?
8. One of your documents has a section literally titled "Scenarios That Were Left," containing 10 more categories that use a different naming style than the rest of the document. Was this meant to be merged into the main list, or kept as its own separate group?

### 24. Real content gaps inside the new drop, per file
Several files in the new drop are incomplete, not just informally organized — flag these to the clinical team rather than treating them as finished: `Shreya/Trauma Related Conversations.docx` (only one scenario, cuts off mid-sentence — notable since this is exactly where item #1's 4 missing red-flag scripts also live), `Conversations - Depression.docx` (degrades into an unfinished bare symptom list halfway through), `Conversations Combination ( Bipolar and Psychosis).docx` (2 bipolar topics and 7 psychosis topics, including paranoia, listed in the table of contents but never written), `Conversation Combinations- Life Transitions.docx` (scenarios #13 and #17 missing entirely), and `Ankita/Conversations around Parenting.docx` (mislabeled "Infancy" section header, cuts off mid-conversation, implies further unset sections).

~~`Career Conversation Sets 1.docx` (nominally "500 conversations," actually 1 template repeated 500 times)~~ — **RESOLVED, not just flagged.** Deduplicated into its real parts: `documnets/The Real Useful Knowledge/1. Teach The AI How To Talk/Career Indecision - Canonical Template (deduplicated).md` (the one real template) and `.../2. Search And Match Or Recommend/Career Field & Stream Lookup.csv` (the 500 genuine career/field/stream rows). Confirmed via full-file extraction: exactly 1 template, 0 header/dialogue mismatches across all 500 entries.

### 25. Tier-labeling is applied inconsistently across clinical-team contributors
Tanisha's conversation scripts explicitly tag high-severity conversations "Tier 1/2/3." Ankita's scripts (Nicotine cessation, Parenting) use no tiering system at all, or a bespoke ad-hoc label ("(Chronic risk)") instead. This means the tiering taxonomy was not yet standardized across the team at time of authoring — needs harmonization before any of this content is used to calibrate the tier-routing system.

### 26. Sensitive paraphilic-disorder content needs an explicit governance decision
`List of Scenarios - Tanisha.docx`'s "Fetishes" section and a Week 2 conversation-script file cover all 8 DSM-5-TR paraphilic disorders, including Pedophilic Disorder and Sexual Sadism Disorder (framed carefully as non-offending, help-seeking content — never depicting actual abuse). This is the most legally/clinically sensitive material in the project. **Needs its own explicit escalation/handling decision from the clinical and legal team** — likely a mandatory-human-review or hard-escalation pathway distinct from the ordinary red-flag system — before any of it reaches a live retrieval index. Do not fold this silently into the general scenario taxonomy.

### 27. Three files in the new drop remain password-locked
`Anam/Conversation Combinations- sleep.docx`, `Anam/Conversations Combinations- anxiety 3rd person.docx`, and `Anam/Miscellaneous Conversations.docx` did not decrypt with the password used successfully on the other 43 files — Anam may have used a different individual password. Ask her directly, or check for a second password, before these 3 can be reviewed.

---
*This is a living document. As each item above is resolved (client answers, a decision is made, or new source material arrives), update the relevant primary document (05-13, 17) and remove or mark resolved here — don't let this list and the rest of the folder drift out of sync.*
