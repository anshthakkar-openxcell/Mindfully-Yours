# 08 — Silent Triage & the Safety Interlock

> This is the highest-priority document in the whole `understanding/` folder to get right. Per [01_PROJECT_OVERVIEW.md](01_PROJECT_OVERVIEW.md) principle #2, the safety interlock is never skipped, never bypassed, never delegated to the LLM. Everything below is either directly client-authored content or a deterministic rule derived from it — none of it is a model's judgment call.

## 1. The two systems, and how they differ

| | Silent Triage | Safety Interlock |
|---|---|---|
| What it does | Reads the conversation for severity signal — which tier (1/2/3) the situation belongs to | Scans raw text for crisis/red-flag language, can force immediate escalation |
| How it decides | Signal accumulation (Clinical Markers) + deterministic rule lookup (routing rules) | Rule/keyword (phrase) matching against the Red Flags list — deterministic, not a model call |
| Runs when | Every turn | **Every single turn, unconditionally** — including cache hits, retries, error paths |
| Can be overridden by | Nothing — it feeds the routing decision | Nothing — it can force Tier 3/SOS regardless of what triage or retrieval would otherwise produce |
| Failure mode | N/A (feeds forward) | **Fails safe, upward** — on timeout, low confidence, or provider outage, defaults to the more cautious path, never the more permissive one |

## 2. Silent Triage — the Clinical Markers Reference Table (verbatim, always in the system prompt, never embedded/searched)

This table lives permanently in the AI's system prompt — it's small (10 categories) and universally relevant every turn, so it's never a retrieval target. **Every field below is extracted verbatim from `Clinical_Markers_Reference_Table (1).pdf`** — a developer should be able to hardcode this directly into a prompt template from this table alone.

| # | Marker | What it means | What the AI looks for | Lower-concern example | Higher-concern example |
|---|---|---|---|---|---|
| 1 | **Speech** | How the user is communicating during the conversation | Whether speech/text is clear and understandable, or unusually fast, very slow, difficult to follow, or difficult to interrupt | "I've been stressed about my exams and I don't know how to manage everything." | *(behavioral description)* "The user sends long, extremely rapid responses, jumps between unrelated topics and is difficult to follow." |
| 2 | **Safety** | Whether the user or someone else may be in immediate danger | Thoughts of suicide/self-harm, plans or intent to harm self/others, recent serious self-harm, or inability to keep themselves safe | "I've been feeling low, but I don't have thoughts of hurting myself." | "I have been thinking about killing myself and I have a plan." |
| 3 | **Functional Impact** | How much the difficulty affects everyday life | Impact on work/college, sleep, eating, relationships, self-care, responsibilities, routines | "I'm anxious, but I'm still attending college and getting my work done." | "I've stopped attending classes, I'm barely sleeping and I can't keep up with anything." |
| 4 | **Reality Testing** | Whether the user can distinguish a thought/feeling from something actually happening | Whether the user can consider other explanations, or is completely certain an unusual belief/experience is objectively real | "Sometimes I feel like everyone is judging me, but I know it could just be my anxiety." | "I know everyone is communicating about me through hidden messages, and there is no possibility that I'm mistaken." |
| 5 | **Emotional State** | What the user feels and how strongly | Intensity of emotion, ability to manage it, sudden/extreme changes, feeling overwhelmed or unable to cope | "I'm upset about the breakup, but I can still manage my day." | "My emotions feel completely out of control and I don't know what I'm going to do." |
| 6 | **Thought Organisation** | How clearly/logically thoughts come across | Whether the user stays on topic and communicates a connected thought, or becomes very hard to follow, disconnected, or scattered | "I'm worried about work because I made a mistake yesterday." | *(behavioral description)* "The user moves rapidly between unrelated ideas and their responses no longer form a clear or understandable sequence." |
| 7 | **Thought Content** | What kinds of thoughts occupy the user's attention | Persistent worry, hopelessness, guilt, self-criticism, suspicious thoughts, unusual beliefs, intrusive thoughts, thoughts of harming self/others | "I keep worrying that I'll fail my presentation." | "There's no point in anything anymore. Everyone would be better off without me." |
| 8 | **Sensory Experiences** | Whether the user reports unusual sensory experiences others don't share | Reports of hearing/seeing/feeling something unusual; frequency; whether the user believes it's actually happening; effect on behavior/safety | "Sometimes when I'm falling asleep, I think I hear someone call my name." | "I regularly hear a voice speaking to me when nobody is there, and I follow what it tells me to do." |
| 9 | **Behavioural Changes** | Whether behavior has noticeably changed from the user's usual pattern | Increased impulsivity, risky behavior, aggression, extreme withdrawal, unusual activity, inability to maintain routines | "I've been staying home more because I've been stressed." | "I've barely slept, I've been spending huge amounts of money and doing things I normally wouldn't do." |
| 10 | **Engagement with AI** | Whether the user can understand, respond to, and participate in the conversation | Whether the user can understand questions, give relevant answers, reflect on their situation, engage meaningfully | *(description)* "User responds appropriately and can discuss their concerns." | *(description)* "User is extremely confused, unable to follow simple questions or unable to participate meaningfully in the conversation." |

**Note on source formatting**: in the original PDF, "Lower concern" is styled green and "Higher concern" red. Three markers (Speech, Thought Organisation, Engagement with AI) give their higher-concern — and for Engagement, both — examples as third-person behavioral descriptions rather than quoted user speech; this distinction is preserved exactly above and should be preserved in the prompt template too (i.e., don't force these into a fake first-person quote).

**Implementation note**: this table feeds Step 1/Step A of the conversation pipeline ([04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md)) — the coarse read of "which kind of thing is happening" (Safety? Functional Impact? Thought Content?) before the finer-grained signal-code matching against `A1`/`A2` takes over.

## 3. The tier system — how severity maps to action

Per `Kb_Phase_I_9.csv` (Signal Sufficiency, confirmed **185 real data rows** across **12 clinical categories** — Mood Disorders, Anxiety and Related Disorders, Personality Disorder and Trait-Based Situational Issues, ADHD and Related Disorders, Gender/Sexual Dysphoria and related patterns, Substance Use, Feeding/Eating Disorders, Stress/Trauma, Somatic, Dissociative, Sleep, Obsessive-Compulsive) and `Kb_Phase_I_C11.csv` (Routing Rules, confirmed **exactly 66 rules**) — full row-level data in [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md).

- **Tier 1** — stays in self-care conversation; this is where genuine semantic RAG search happens (once Phase III/IV content exists).
- **Tier 2** — practitioner suggestion + booking flow.
- **Tier 3** — immediate SOS routing, no further probing, human alerted. Per the client's own data: *"Immediate — do not wait for full picture."*

**⚠ Open discrepancy on the tier model itself**: `Mindfully_Yours_Phase1_English_Architecture.pdf` describes a **4-state branch** — "Tier 1/2 → self-care continues · Tier 3 → practitioner match & booking (on consent) · Crisis → immediate screen + human alert + safe hold" — which treats "Tier 3" (practitioner referral) and "Crisis" (immediate human safety intervention) as two *separate* escalation paths. This conflicts with `Phase1_Final.pdf`/`Phase1.pdf` and all the KB markdown files, which use a **3-tier model** where Tier 3 *is* SOS/crisis (one combined state). **This must be resolved explicitly before building the escalation state machine** — it changes how many distinct routing outcomes the system needs. See [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md).

## 4. The Safety Interlock mechanism — built from Red Flags (`Kb_Phase_I_7.csv`)

- **Exactly 31 rows, confirmed by direct CSV analysis** (`RF-001` through `RF-031`), each with: `Flag ID`, `Trigger Phrase Examples (5+)`, `Clinical Meaning`, `Immediate Action` (e.g. "Tier 3 + SOS flag"), `Bot Script` (exact wording), `Escalation Target` (e.g. "Psychiatrist + crisis review").
- **Both direct and disguised trigger phrases matter equally** — the client explicitly designed this list to catch indirect language, since real users don't always say things plainly.
- **`trigger_phrases` is the one field worth embedding** for this sheet — real varied phrasing is exactly what a semantic-similarity match needs. The confidence threshold for a red-flag match should be **deliberately more permissive/sensitive than a normal RAG match** — a false positive here costs a moment's extra caution; a false negative costs a missed danger signal.
- **`bot_script` is fetched verbatim, never regenerated or paraphrased by the LLM.** The client explicitly wrote these to be used word-for-word. This is the concrete implementation of principle #2 in [01_PROJECT_OVERVIEW.md](01_PROJECT_OVERVIEW.md) — a red-flag response's exact wording is guaranteed correct every time, with zero risk of the LLM softening or rephrasing clinically deliberate language.
- `immediate_action` and `escalation_target` are precomputed fields attached to the matched chunk, never separately searched.

### Verbatim examples (real data, confirmed via direct CSV analysis)

- **RF-001** (aggressive behaviour / irritability / violence risk) — trigger phrases include *"he overtook me on the road, so i followed him to beat him up"*, *"they tried to remove me from the project, so made sure they all failed"*, *"she insulted me. so i stalked her to scare her."* → Action: `Tier 3 + SOS flag` → Bot Script: *"It sounds like things have been really intense lately — feeling that level of frustration or anger can be exhausting. This is something a therapist can really help with. Would you like me to connect you with one?"* → Escalation: `Psychiatrist + crisis review`.
- **RF-018** (passive suicidal ideation) — trigger phrases: *"I wish I hadn't woken up"*, *"Everyone would be better off without me"*, *"I don't feel like being here any more"*, *"If a car ever hits me and I die, I will be okay with it"*, *"I want to be dead / I hope I die."* → Bot Script: *"Thank you for trusting me with this. Feeling like you don't want to be here anymore is serious, and you deserve real support. Please reach out to a therapist or a crisis line — I can help you find one right now."*
- **RF-020** (psychotic feature) — trigger includes command-hallucination-adjacent religious/guilt content → **has a Bot Script but an empty Escalation Target** — a real data gap, not a formatting artifact.

### ⚠ Critical data gap found in the real sheet

**Four flags — RF-028, RF-029, RF-030, RF-031 — have a completely empty Bot Script cell.** These are the last four rows: *Suspected violence/unsafe environment*, *History of violence*, *Suspected rape*, *Sexual molestation* — some of the most sensitive categories in the entire Red Flags sheet, and they currently have **no scripted verbatim response** for the bot to use if triggered. **This is a hard blocker on launch, not a nice-to-have, and is the single most important open item in the whole knowledge base** — per principle #2, the interlock must never let the LLM freelance a response to a disclosure this sensitive. **Until the clinical team supplies verbatim scripts for these four flags, application code must treat a matched flag with an empty `bot_script` as a hard alert routed directly to a human, never as a silent LLM-generated fallback** — the one place in this whole system where "the AI will just phrase something reasonable" is not an acceptable substitute. Flagged as the top-priority item in [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md).

**Other real data-quality issues in this sheet** (relevant to how the interlock is implemented, not just documentation hygiene):
- Trigger-phrase count per flag is wildly inconsistent (RF-017 has 21 examples; RF-011/RF-012/RF-019/RF-020 effectively have only 1) — driven by formatting differences (one-phrase-per-line vs. quote-mark-separated vs. a single narrative paragraph), not a real content gap. A parser must handle all three formats.
- Full row-level samples, exact counts, and every other data-quality finding: see [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) §Red Flags.

### The `rag simple flow.pdf` mental model (useful as a plain-English explanation for onboarding a new developer)

> "That matched sign is checked against the rulebook and the red-flag list. If it matches a red flag, the AI skips everything else and immediately uses the exact safety script — no guessing, no delay." — for a red flag or unclear situation, the AI uses the exact pre-written script, word for word; for everything else, it writes a natural, warm reply guided by the matched information, not by memorizing a script.

## 5. The Fallback & Safety Net — the third response type (`Kb_Phase_I_17.csv`)

This is a case the original conversation flow design missed and had to be added explicitly: **what happens when there's *some* signal but not enough to route confidently, and it's staying that way** (vague, contradictory, or disengaging) — this is distinct from both "keep probing" (still resolvable) and "enough, route now."

**⚠ Correction to the design docs' own description, now confirmed twice** (first by direct CSV analysis, then independently by a re-verification pass against `KNOWLEDGE_BASE_CONTENT.md` v2): the design markdown originally described this sheet as having three sections (A/B/C). **It actually has four scenario sections, plus an entirely separate second table appended below with a different first-column label — together accounting for roughly 70% more content than first documented:**
- **Section A — Insufficient signal scenarios** (3 rows): vague disclosure, high topic diversity, low model confidence. Real trigger example: *"15+ turns; user provides short, non-specific responses; no identifiable Signals or Rules; confidence below threshold."*
- **Section B — Contradictory signal scenarios** (4 rows): stated wellbeing contradicts emotional content, ambiguous safety situations, mixed practical/mental-health concerns.
- **Section C — User disengagement scenarios** (4 rows): one-word answers, mid-disclosure abandonment, repeated session restarts without progress.
- **Section D — Special population scenarios, adults 20-45** (4 rows) — **missed entirely in the first pass of documentation.** Covers: new parent/perinatal presentation, bereavement, burnout/chronic workplace stress, and identity or life-transition distress.
- **A second, separate 84-row disorder-specific fallback matrix** (header: `Disorder / Scenario | Trigger Condition | Fallback Action | Bot Script | Escalation Path | Clinical Reasoning`), organized into 15 disorder groups (Anxiety, Mood, Trauma & Stressor-Related, OCD & Related, Eating Disorders, Psychotic Disorders, Substance Use, Personality Disorders, Neurodevelopmental, Gender Dysphoria, Identity & Reality Dissociation, Insomnia, Somatic Symptom Disorder, Gambling/Behavioural Addictions, General Concerns) — a **distinct table from Sections A-D, not part of their structure**, keyed by disorder rather than conversation shape.
- **Total: 99 real data rows** (15 scenario rows across A-D + 84 disorder-matrix rows) — close to the ~100 estimate in the design docs, but only once both tables are counted; treating this as "one 3-section table" (as the design markdown originally did) would silently miss the disorder matrix and all of Section D.

Each row: `Scenario Type`/`Disorder-Scenario`, `Trigger Condition`, `Fallback Action`, `Bot Script`, `Escalation Path`, `Clinical Reasoning`. **Same verbatim-fetch principle as Red Flags** — `bot_script` is used close to verbatim, not loosely paraphrased.

**Critical implementation distinction**: `trigger_condition` here is **not something a user says** — it's a description of the conversation's own shape (a turn count, a response-length pattern, a confidence score). This must be evaluated as **code against the conversation's running state**, not embedded or semantically searched. This is the sheet most likely to be built wrong if treated like the other KB sheets.

### Data-quality issues found (real, from direct analysis — beyond the design docs' description)

- **A real individual's name (e.g. "Shreya") is hardcoded into three separate rows' Escalation Path** — not just one, as first identified — including phrasing like *"Flag for [name] with full signal breakdown"* and *"priority Tier 2 referral"*. Every other row in the sheet correctly routes to a *role* (e.g. "Tier 2 clinician," "on-shift crisis team"), not a named individual. This is both a data-hygiene problem and a minor privacy exposure if it reaches production documentation as-is — it must be scrubbed and replaced with role-based routing before this table becomes a permanent implementation reference. Flagged in [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md).
- Several bot scripts contain uncorrected grammar/typos (e.g. "who help you understand they confusing aspects of your life", "Ill be right here" missing an apostrophe) that would ship verbatim per the sheet's own "use verbatim" instruction unless corrected with the clinical team first.
- Full row-level samples and every other data-quality finding: see [05_KNOWLEDGE_BASE_DEEP_DIVE.md](05_KNOWLEDGE_BASE_DEEP_DIVE.md) §Fallback & Safety Net.

## 6. Why the interlock is fast by construction, not by rushing it

- Rule/keyword-based specifically because that's **both safer and faster** than a model call — deterministic pattern matching is milliseconds; an LLM call is hundreds of milliseconds at best.
- Never "speed it up" by making it less thorough — if it's slow, the fix is a better-indexed rule engine, not a shorter rule list.
- Triage should be lightweight signal extraction, not a heavy model inference step. If it ever becomes a latency bottleneck, that's a sign it's been implemented as something heavier than it needs to be.

## 7. What NOT to do

- Don't let the LLM decide *whether* something is safe to say — that's the interlock's job, decided before the LLM is even called.
- Don't skip triage/interlock on any code path, including error handling, retries, or cache hits.
- Don't paraphrase Red Flag or Fallback bot scripts through the LLM — use them close to verbatim.
- Don't build the interlock's phrase-matching only on direct language — the disguised/indirect examples exist specifically because real users don't always say things plainly.
- Don't treat a retrieved passage as ground truth without confidence scoring — low confidence means fallback, not a best-effort guess.

---
*Source material: `Clinical_Markers_Reference_Table (1).pdf` (full, verbatim extraction), `documnets/approch/CLAUDE.md` §2, `documnets/flow/RAG/KNOWLEDGE_BASE_CONTENT.md` §§1,3c,3d, `documnets/flow/RAG/rag simple flow.pdf`, and the three Phase 1 architecture PDFs' tier/crisis callouts. Row-level Red Flag / Fallback CSV data cross-referenced in [05_KNOWLEDGE_BASE_DEEP_DIVE.md].*
