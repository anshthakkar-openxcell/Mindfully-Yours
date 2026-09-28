# 18 — New Client Drop: "MYPL - Mindfully Yours Work" Convo Data (Sept 2026)

> **What this is**: on 2026-09-28 the client provided a large, informally-organized folder of clinical-team working documents at `documnets/knowledgebase/convo data/MYPL - Mindfully Yours Work/` — 46 files (mostly `.docx`, a few `.pdf`, one `.zip`) authored by four named clinical team members (Anam, Ankita, Shreya, Tanisha). **This is, in large part, the Phase II/III/IV content previously marked "not yet received"** in [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #3 — see §8 below for exactly what that blocker's status is now.
>
> **Encryption note**: 43 of the 46 original files were password-protected (Word "Encrypt with Password", not just view-restricted). The client supplied the password directly; a deduplicated, decrypted, readable copy of everything usable now lives at `documnets/knowledgebase/convo data/decrypted/` (44 files — 2 confirmed exact/near-exact duplicates and 1 redundant zip were excluded, see §7). **3 files could not be decrypted with the supplied password** and remain untouched in the original folder — see §9. The password itself is not stored in this repo; it lives wherever the team keeps credentials.
>
> This document is a catalog and a build recommendation, not a replacement for reading the source files directly for exact wording before anything ships to production.

## 1. The single biggest structural discovery: a "Layer" system, separate from "Tier"

Every prior document in this project used **Tier 1/2/3** to mean *severity/routing* (self-care / practitioner / crisis). This new content reveals a **second, orthogonal axis: Layer I → IV**, meaning *how deep/probing this specific conversational turn is*, independent of how severe the situation is:

| Layer | Purpose | Source files |
|---|---|---|
| **Layer I** | Opening/rapport — generic, emotion-agnostic questions and statements to open a conversation and build trust | `Layer I Questions and Statments.docx`, half of `PHASE II Layer I and IV Questions.docx` |
| **Layer II** | Exploratory — open questions (values, goals, boundaries, patterns) plus 23 emotion-specific probing questions | `Layer II Question Bank.docx` |
| **Layer III** | Insight/self-regulation — awareness-building, naming coping techniques (breathing, grounding, journaling), reflective psycho-education | `Layer III.docx` |
| **Layer IV** | Action/planning — CBT/DBT/ACT-style behavioral experiments, thought records, concrete next steps | other half of `PHASE II Layer I and IV Questions.docx`, `Layer 2 to 3 Transitions.docx`'s sibling transition content |

Each layer file ends with an explicit **"Transition Statements"** section handing off to the next layer (e.g. *"The next step after insight is execution. Would you like the next steps?"*). **Recommendation**: model `Layer` as its own field in the prompt/conversation-state system (see [11_DATA_MODEL_AND_STORAGE.md](11_DATA_MODEL_AND_STORAGE.md)), separate from `Tier`. Do not conflate the two — a Layer-IV, Tier-1 conversation (deep self-help planning for a low-severity issue) is a completely different thing from a Layer-I, Tier-3 conversation (an opening rapport line that immediately reveals a crisis).

## 2. The second biggest discovery: a master AI decision-flow spec

`Pathway For AI In Different Situations - Tanisha.docx` is a complete **15-step decision pathway** (identify concern → categorize → immediate safety check → understand the problem → assess emotion → assess severity → assess supports → assess coping → clarify user's goal → choose intervention → psychoeducation → encourage professional help → small next step → summarize → close), plus **7 explicit design rules** ("never diagnose," "validate before problem-solving," "ask 1-2 focused questions at a time," "reassess risk continuously," name evidence-based modalities as "coping strategies, not therapy," always end with a collaborative next step).

**This is the closest thing to a finished orchestration spec the client has produced** — treat it as required reading for anyone building [04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md)'s prompt-assembly and routing logic. **However, it introduces vocabulary that conflicts with the existing system and must be reconciled, not layered on top blindly**:
- Its severity scale is **Mild / Moderate / Severe / Crisis** (4 buckets) — does NOT map 1:1 to the existing **Tier 1/2/3** system. Is "Crisis" the same as Tier 3? Is there a 4th tier? This is now a formal open question (see §8).
- Its "Categorize the Situation" step uses a **flat 22-item list** (Relationship, Family, Work, Study, Financial, Health, Grief, Anxiety, Depression, Trauma, Loneliness, Self-esteem, Identity, Substance use, Parenting, Daily stress, Life transitions, Neurodevelopmental concerns, Psychotic symptoms, Eating concerns, Sleep, Sexuality, Abuse, Safety concerns, Multiple concerns) that does not exactly match the ~9-category tree in `List of Scenarios - Tanisha.docx` (see §3).
- Its "Assess Emotional State" step uses an **11-item picklist** (Sad, Angry, Scared, Guilty, Ashamed, Hopeless, Lonely, Numb, Overwhelmed, Relieved, Mixed) — a *third* emotion vocabulary, on top of the two below.

## 3. A real problem: three unreconciled emotion taxonomies

| Source | Emotion count | Sample labels |
|---|---|---|
| `PHASE II_ Emotion Associated user expression.docx` | 19 | Anxiety, Confusion, Anger, Frustration, Stress, Helplessness, Guilt, Hopelessness, Shame, Jealousy, Worry, Sadness, Hopeful, Numbness, Disgust, Burnout, Conflicted, Resentment, Panic |
| `List of Emotions - Tanisha.docx` | 9 | Overwhelm, Demotivation, Irritation, Tensed, Curious, Embarrassed, Grief, Loneliness, Concerned |
| `Pathway For AI...` Step 5 picklist | 11 | Sad, Angry, Scared, Guilty, Ashamed, Hopeless, Lonely, Numb, Overwhelmed, Relieved, Mixed emotions |

These were authored independently by different team members and **do not overlap cleanly** (e.g. "Tensed" vs. "Anxiety," "Concerned" vs. "Worry" are conceptually close but not identical; "Curious," "Embarrassed," "Grief," "Loneliness" appear in only one list each). **This must be merged into one canonical emotion taxonomy before building any `emotions` table or EM-code legend** — building against any one of these three lists today risks a rebuild later. Flagged as a new open item (§8).

## 4. Full file catalog, by source folder

### 4a. Core framework / question banks (top-level "MYPL - Mindfully Yours Work")
| File | What it is | Recommendation |
|---|---|---|
| `Layer I Questions and Statments.docx` | 9 sections, ~150 opening/rapport phrases, incl. a "Safety Check" section that mirrors Phase I red-flag concerns | Use as-is; feed into a Layer-I prompt bank |
| `Layer II Question Bank.docx` | 7 generic categories (~140 Qs) + 23-emotion-specific bank (~330 Qs) | Use as-is; **no heading styles** — ingestion can't rely on Word headings here, category names are plain text only |
| `Layer III.docx` | Awareness/self-regulation/skill-introduction banks + 23-emotion reframing bank | Usable, but has **5 unfilled `[technique]`/`[xyz issue]` template placeholders** — must be resolved before use |
| `Questions.docx` | 9 life-situation scenarios (moving out, bereavement, failing exams, chronic illness, financial trouble, LGBTQIA+, friendship, gender/sexuality, caregiving), each with a full Tier 1/2/3 question template **explicitly matching the project's own tier model** | **Highest-value file for tier-routing calibration** — but last 4 of 9 scenarios are noticeably less developed (no open-question sections); several verbatim duplicate rows within tables |
| `Questions For When AI Is Not Sure - Tanisha.docx` | 16-category NLU/clarification fallback bank (~130 items) — cross-cutting, usable at any Layer/Tier | Usable, but **2 items contain literal drafting notes** left in the text (e.g. "(could be followed up with some options)") — strip before use |
| `Question Set - Career.docx` | Career-domain analog to `Questions.docx`, 9 topics, ~370 questions with a "Tier Routing" column | **Column is present but 100% empty in every row** — unfinished; also has real typos and copy-pasted questions that don't fit their new context (e.g. "go to work" phrasing pasted into a college-rejection scenario) |

### 4b. Emotion / scenario / pathway framework (the strategic backbone)
| File | What it is | Recommendation |
|---|---|---|
| `Layer 2 to 3 Transitions.docx` | Small phrasing bank for bridging Layer II→III mid-conversation | Clean, use as-is |
| `PHASE II Layer I and IV Questions.docx` | Layer I opening + Layer IV CBT/DBT/ACT action-planning questions | Clean, use as-is; references companion Layer II/III files directly |
| `PHASE II_ Emotion Associated user expression.docx` | 19-emotion phrase corpus (~700 phrases) — likely the raw material behind an EM-code classifier | See §3 — needs taxonomy reconciliation before becoming a DB table |
| `List of Emotions - Tanisha.docx` | A second, independent 9-emotion phrase corpus | See §3 |
| `List of Scenarios - Tanisha.docx` | **The largest single file** (~23,000 words) — an exhaustive scenario library across 9 main categories (Relationship/Family/Education/Career/Mental Health/Friendship/Gender & Sexuality/**Fetishes**/plus a bolted-on "Scenarios That Were Left" second pass of 10 more sub-categories) | See §6 for the Fetishes/DSM section specifically. The two halves of this document (main categories + "Scenarios That Were Left") were **never merged/deduplicated** by the original authors — contains a literal unfinished placeholder note, *"Please follow the DSM 5 TR for the same,"* in the Schizoid Personality Disorder cluster |
| `Pathway For AI In Different Situations - Tanisha.docx` | The master 15-step decision-flow spec — see §2 | Required reading before building the orchestrator; vocabulary needs reconciliation, not direct adoption |
| `Anxiety Situations.docx` | Pure taxonomy — 35 broad "situation" categories with subtopics, no dialogue | Useful as a category-coverage checklist, not as conversation content |

### 4c. Top-level topic conversation samples
| File | What it is | Recommendation |
|---|---|---|
| `Career and Academic Conversation - Samples.docx` | ~19 conversations, re-covers existing `Convo_Samples.pdf` ground (job loss, career indecision, burnout, workplace friction) | Low new-information value — mostly duplicate coverage with new phrasing |
| `Career Conversation Sets 1.docx` | **Data-quality red flag**: nominally "500 conversations" but is actually **1 template mechanically repeated 500 times** with only the career-field name swapped | **Do not count as 500 real examples.** Useful only as a list of ~500 career-field names, not as conversational variety |
| `Conversation Combinations- Anam.docx` | ~38 conversations: romantic relationships + family issues (domestic violence, parentification) | **Contains genuine crisis content** (2 suicidal-ideation escalations, 1 domestic-violence safety-planning scenario) — high value for crisis-script calibration |
| `Conversation Combinations - Tanisha.docx` | ~75 conversations: "moving out" (50 convos with a Tier 1/2/3 model), friendship, LGBTQIA+ | **Richest crisis content in the whole drop** — ~8 distinct Tier-3 escalations (suicide, homicide-suicide ideation, substance-fueled risk-to-others) each with an explicit "*follow prescribed protocol*" marker |
| `Conversations - Anxiety .docx` | ~30 DSM-style anxiety-disorder conversations (GAD, panic, phobias, PTSD, etc.) with named CBT techniques | Clean, genuinely new ground (clinical/disorder-specific style vs. life-situation narrative style) |
| `Conversations - Depression.docx` | Only 4 full conversations; **the rest of the file degrades into an unfinished bare list of symptom statements with no AI responses** | Treat as incomplete/draft — don't count the symptom-list half as finished content |
| `Miscellaneous Conversations1.docx` | 37 varied one-off scenarios, including 2 explicit guardrail demonstrations (user goes silent; a psychosis flag; a "don't want to exist" flag) | Useful grab-bag; unstructured, some exact-duplicate "variation" pairs |
| `Parenting_Child Related.docx` | **Not conversation samples at all** — a spec document: symptom-statement lists, intake questions, and an explicit Guardrail table mapping concern → referral urgency | Valuable as a ready-made escalation-urgency framework for child-safety concerns; would need to be turned into actual dialogues before use as few-shot material |
| `ED/Eating Disorder - Third Person Reported.docx` | ~24 conversations, uniquely framed as a **concerned third party** (parent/friend) reporting worry, not the affected person speaking directly | **Fills a genuine, previously-flagged content gap** (eating disorders had zero coverage). Cleanest, most systematic crisis-escalation template in the whole drop — nearly every Tier 3 example ends in an explicit "*Initiate crisis protocol*" marker |
| `18-9_Offline Woork Week 6.docx` | 12 friendship-specific conversations (misleadingly named — no actual "week 6 progress" content) | Clean, new ground; recommend renaming for the KB |

### 4d. Tanisha's + Ankita's weekly conversation scripts (`MYPL KB 7th Sept/Tanisha/`, `.../Ankita/`)
These are **not progress logs** — each "Offline Work Week N" file is a full batch of dozens of complete conversation scripts, confirmed by document metadata: each file's creation date matches its filename (weekly cadence), and **every file's `last_modified_by` is "Shreya Aras," dated 2026-09-07** — direct evidence of the team's actual process: individual clinicians draft scripts weekly, then Shreya compiles/edits everything into the "KB 7th Sept" consolidation folder.

| File | Topics | Notes |
|---|---|---|
| Week 1 | Friendship (13), Family (12), LGBTQIA+, ADHD (15) | Explicit Tier 3 tags on high-risk conversations (self-harm, domestic violence) |
| Week 2 | All 10 DSM personality disorders, Finance (13), Paraphilic disorders (incl. Pedophilic Disorder, handled as careful non-offending help-seeking content) | See §6 — sensitive content requiring governance review |
| Week 3 | Daily stressors (10), Autism (7) | Lowest-severity content in the batch — zero Tier/crisis mentions |
| Week 4 | Parasocial relationships (10), Grief (8), **Trauma (36 conversations across 15 categories, every one explicitly Tier-tagged)** | The clearest evidence of the team's tiering methodology; **but** contains unresolved literal placeholders ("name of celebrity," "name of Instagram creator") in every parasocial conversation |
| `Parasocial Relationships Conversations.docx` (standalone) | Same 10 parasocial scenarios as Week 4, near-word-for-word | **Confirmed duplicate of Week 4 content**, differs only in heading formatting — pick one as canonical before ingestion |
| Ankita: Nicotine cessation | ~26 lettered scenarios, uses "Client:" not "User:", and a bespoke "(Chronic risk)" label instead of Tier N | **Inconsistent labeling convention vs. Tanisha's files** — confirms tiering wasn't yet standardized across contributors at time of writing |
| Ankita: Parenting | 13 scenarios, labeled "Infancy" but half the content is toddler/school-age | Incomplete — ends mid-conversation, mislabeled section header, only "section 1" of an implied larger series that wasn't provided |

### 4e. Shreya's disorder-specific scripts (`MYPL KB 7th Sept/Shreya/`)
Confirmed via document metadata: authored by **"Shreya Aras"** — the same name found hardcoded into `Kb_Phase_I_17.csv`'s escalation-routing field (see [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #13). This is a direct authorship match, not a coincidence — Shreya is both a scenario author and the KB compiler.

| File | Topics | Notes |
|---|---|---|
| Addictions and Substance use | Alcohol, smoking/vaping, weed, hard drugs, screen use, porn, gambling, gaming (~25 scenarios) | Crisis handling is "semi-scripted" — a fixed lead-in + grounding-question sequence, but user answers are left blank as placeholders |
| Caregiver concerns | Burnout, aging parents, special-needs children, identity loss (~24 scenarios) | Clean, no crisis moment, highest revision count (222) — most polished file in the set |
| Education Related Concerns | Grades, dropout, exam anxiety, burnout (~25 scenarios) | One crisis reached with a bare "Initiate Crisis Protocol" (no lead-in text) — inconsistent completeness vs. other files |
| Obsessive-Compulsive and Related Disorders | BDD, Hoarding, Trichotillomania, Skin-Picking — **explicitly labeled Tier 1/2/3 throughout** | **Best template for how Tier 1/2/3 mapping should look** — 6 distinct genuine Tier-3 medical crises with a consistent fixed lead-in phrase |
| Shopping Issues | Impulsive/emotional/social-media-triggered shopping (~14 scenarios) | Clean, no crisis content |
| **Trauma Related Conversations** | **Only ONE scenario, and the document cuts off mid-sentence** | **Major content gap**, and it's in exactly the domain (violence/abuse) where the project already has its 4 missing red-flag scripts (RF-028–031). Revision count 15 (vs. 222 for Caregiver) suggests an abandoned early draft. Flag to the clinical team as a priority to complete. |

### 4f. Anam's self-help tools + conversation combinations (`MYPL KB 7th Sept/Anam/`)
This folder is the **single most valuable source for the "Phase IV: self-help tools" gap**, which the project previously had zero content for.

| File | What it is | Recommendation |
|---|---|---|
| `dbt-skills-workbook.docx` / `dbt-skills-workbook-simple.pdf` | A finished, 5-skill DBT workbook (Wise Mind, STOP, TIPP, Opposite Action, PLEASE) | **Ready to use today** — recommend directly to Tier 1 users. (Two docx copies exist; confirmed content-identical, kept one) |
| `brain-dump-worksheets.pdf` — "A Soft Place to Land" | A finished, low-structure emotional-release worksheet | **Ready to use today**, complements the DBT workbook for users not ready for skills-based language |
| `SELF-HELP CONVERSATIONS.docx` | **The broadest single self-help asset in the drop**: 11 conversation transcripts + a 7-section toolkit (Behavioral Activation, Time Management, Mindfulness/Grounding, Self-awareness, "Tools for SOS," Journaling, Tracking Worksheets) including a lightweight safety-plan-style worksheet | **Treat as the canonical Phase IV source document.** (Confirmed superset of the smaller `Self Help Conversation - Anam.docx`, which was excluded from the clean mirror as a redundant subset) |
| `Conversation Combinations- romantic relaitonship + fmaily issues.docx` | ~23 romantic/family roleplay scripts | New ground, clean |
| `Conversation Combinations- Life Transitions.docx` | 20 life-stage transition scenarios (college, new job, parenthood, menopause, retirement) | **2 numbered scenarios (#13, #17) are missing entirely** — real content gap, not a formatting artifact |
| `Conversations Combination ( Bipolar and Psychosis).docx` | Bipolar (20 topics) + Psychosis (10 topics) scripts, including safety-escalation handling | **Significant gaps**: 2 bipolar topics (suicidal ideation, substance use) listed in the table of contents but never written; the psychosis section is missing content for 7 of its listed topics, including paranoia — flag to clinical team, this is sensitive content with real holes |
| `Conversations Combination- chronic illness.docx` | ~14 scenarios: diagnosis, caregiver burnout, grief of an imagined future | Clean, thematically links to the Grief journaling prompts in `SELF-HELP CONVERSATIONS.docx` |

## 5. What this unblocks

Per [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #3, Phase III/IV content was "not yet received" — **this is now substantially resolved**:
- **Phase IV (self-help tools)**: effectively fulfilled by Anam's DBT workbook, brain-dump worksheet, and the `SELF-HELP CONVERSATIONS.docx` toolkit — genuinely ready to wire into [04_CONVERSATION_PIPELINE.md](04_CONVERSATION_PIPELINE.md) Step F (Tier 1 recommendation).
- **Phase II (therapeutic framework/conversation samples/emotion-wise content/list of new-age issues)**: fulfilled by the Layer I-IV files, the emotion corpora, `List of Scenarios`, and the dozens of topic-specific conversation-script files.
- **Phase III (clinical guidance/psycho-education)**: partially fulfilled — Layer III's reflective/psycho-educational statements and the disorder-specific conversation scripts (OCD, Bipolar/Psychosis, Personality Disorders) qualify, though several of these have real content gaps (see §4e, §4f) that should go back to the clinical team before being treated as complete.

## 6. Sensitive content requiring a deliberate governance decision before it goes near a consumer app

`List of Scenarios - Tanisha.docx`'s **"Fetishes"** section and Week 2's **Paraphilic Disorders** conversations cover all 8 DSM-5-TR paraphilic disorders, including **Pedophilic Disorder** and **Sexual Sadism Disorder**. The content itself is carefully framed around a non-offending, help-seeking user (e.g. *"I want help before anything bad ever happens," "Protecting children is extremely important to me"*) and never depicts actual abuse — but this is still the most legally and clinically sensitive material anywhere in the project. **Recommendation**: this needs its own explicit escalation/handling decision from the clinical and legal team — likely a mandatory-human-review or hard-escalation pathway distinct from the ordinary Tier/red-flag system — before any of it is wired into a live retrieval index. Do not silently fold this into the general scenario taxonomy.

## 7. Deduplication performed (mirrors the "no ambiguity/duplication" principle from earlier cleanup)

The clean, decrypted mirror at `documnets/knowledgebase/convo data/decrypted/` **excludes** 3 files from the original 46, each verified (not assumed) to be redundant:
1. `Anam/Conversations + Self Help - Anam/dbt-skills-workbook.docx` — confirmed content-identical to `Anam/dbt-skills-workbook.docx` (differs only in duplicated internal XML shapes from a re-save, zero content difference).
2. `Anam/Self Help Conversation - Anam.docx` — confirmed a strict subset of `Anam/Conversations + Self Help - Anam/SELF-HELP CONVERSATIONS.docx` (every line appears verbatim inside the larger file).
3. `Anam/Conversations + Self Help - Anam.zip` — confirmed to contain the same 8 files already present individually in the sibling extracted folder.

**Not removed, despite being a near-duplicate**: `Tanisha/Parasocial Relationships Conversations.docx` vs. the Parasocial section embedded in `Tanisha/4-9_Offline Work Week 4.docx` — these are genuinely near-identical, but since one is embedded inside a much larger multi-topic file, removing either loses either standalone accessibility or the Week 4 file's completeness. Flagged in §4d for a human decision (which to treat as canonical) rather than silently deleted.

## 8. Updates to the open-questions list

See [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) for the consolidated, numbered version of everything below — this section is a pointer, not a duplicate list.

New items raised by this drop: the Layer-vs-Tier reconciliation, the three-emotion-taxonomy merge, the Severity(Mild/Moderate/Severe/Crisis)-vs-Tier(1/2/3) reconciliation, the 22-item vs. 9-category scenario-taxonomy mismatch, the Fetishes/paraphilic-disorder governance decision, inconsistent Tier-labeling across contributors, and every per-file content gap called out in §4 (Trauma near-empty, Depression half-finished, Bipolar/Psychosis gaps, Life Transitions #13/#17 missing, Career Conversation Sets' fake 500, Career question set's empty Tier-Routing column, Parenting doc being spec-only).

## 9. Still-locked files

Three files in `Anam/` did not decrypt with the password supplied for the rest of the drop:
- `Conversation Combinations- sleep.docx`
- `Conversations Combinations- anxiety 3rd person.docx`
- `Miscellaneous Conversations.docx`

These may have been individually protected with a different password by Anam specifically (the rest of the drop appears to share one team-wide password). **Action needed**: ask Anam directly, or check whether a second password exists, before these 3 can be reviewed.

---
*Source: 6 parallel review passes over the decrypted `documnets/knowledgebase/convo data/` tree, cross-referenced against every existing document in this `understanding/` folder. Update this file (and [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md)) once the 3 locked files are opened, the emotion/severity/scenario taxonomies are reconciled with the clinical team, and the Fetishes-content governance decision is made.*
