# 27. Client Question Prep Sheet — Knowledge Base Only

## How to use this document

This covers **only questions about the knowledge base itself** — the ~50-55 clinical/conversation
files the client's team wrote and provided (spreadsheets + Word documents), across both drops.
Nothing about architecture, vendors, payments, or project logistics is included here — those are a
separate conversation, not a knowledge-base question.

For each item: the logic in plain terms, which file it's about, and the exact question to ask.
Item numbers match [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) for
cross-reference.

## Quick-scan summary

| # | Topic | Status |
|---|---|---|
| 1 | 4 red flags with no safety script | **Ask** — highest priority |
| 2 | "EM codes undefined" | ✅ Resolved — skip |
| 3 | Missing self-help content | ✅ Resolved — skip |
| 4 | Routing rules use shorthand we can't fully read | **Ask** |
| 5 | One routing rule is incomplete | **Ask** |
| 6 | Three rows say "check----------" instead of a real answer | **Ask** |
| 11 | Is "Guardrail Questions" a separate missing file | **Ask** |
| 12 | Are sample conversations a script or a style guide | **Ask** |
| 13 | A real name where a role should be | **Ask** |
| 14 | Small typos in word-for-word scripts | **Ask** |
| 15 | Found more structure than first catalogued | **Ask** (light confirmation) |
| 18 | Two versions of a sheet disagree on row count | **Ask** |
| 23 | Emotion lists / Layer vs. Tier vs. Severity / scenario lists | **Ask** — 8 questions |
| 24 | Some files stop partway through | **Ask** |
| 25 | Different writers use different seriousness labels | **Ask** |
| 26 | Sensitive content needs a special safety decision | **Ask** — clinical + legal |
| 27 | 3 files still locked | **Ask** |

---

## Tier 1 — The most important items

### #1 — Four safety scripts are completely missing
**Logic:** Four of your danger-phrase entries (violence, history of violence, suspected rape,
sexual molestation) have everything filled in — what triggers them, how urgent they are, who to
escalate to — except the one thing that matters most: what the AI should actually say.
**File:** `Kb Phase I(7.csv` (Red Flags sheet), rows 38-41
**Ask:** *"Rows 38-41 (RF-028 through RF-031) have everything filled in except the actual word-for-word
thing the AI should say. Can you write the verbatim script for these 4, the same way it's done for
the other 27 rows?"*

### #2 — "EM codes are undefined" — ✅ resolved, skip
Checked against the wrong file originally. The real example phrases were there all along, in a
different sheet than expected.

### #3 — Missing self-help content — ✅ resolved, skip
Already sent in the September data drop.

### #4 — Routing rules use shorthand the system can only partly read
**Logic:** Some of your rules say things like *"any of signals 1-17, except 2 and 3."* The system
currently only understands a rule if it names one signal plainly — it can't yet work out ranges or
"all except these." Right now, 41 of your 66 rules are being skipped rather than guessed at.
**File:** `Kb Phase I(C11.csv` (Routing Rules)
**Ask:** *"Can someone rewrite the 41 rules that use ranges/exclusions by spelling out every signal
number instead, or should we build a smarter reader for the shorthand as-is?"*

### #5 — One rule is missing its instructions
**Logic:** One rule says *what* triggers it, but not where it should route to, how urgent it is, or
why. It's switched off until this is filled in.
**File:** `Kb Phase I(C11.csv`, row 31 (Rule-025)
**Ask:** *"Row 31 only has the trigger condition filled in — can you fill in where it routes to, its
priority, and why?"*

### #6 — Three rows literally say "check" instead of a real answer
**Logic:** Instead of a real seriousness level (1, 2, or 3), three rows just have placeholder text
that was never finished.
**File:** `Kb Phase I(9.csv` (Signal Sufficiency), rows 23-25
**Ask:** *"Rows 23-25 have 'check----------' instead of a real Tier number — can you confirm the
correct tier for these three patterns: 'Recurrent Mood Episode Patterns,' 'patterns of major
depressive episodes,' and 'presence of harm to self/others and manic episode'?"*

---

## Knowledge-base structure & completeness questions

### #11 — Is "Guardrail Questions" a real, separate file we're missing?
**Logic:** Your own file list mentions a document by this name as its own thing — we never received
a file with that exact name. It might already be inside a file we do have, under a different name.
**File:** Your `Knowledge_Base_Directory` file list, possibly overlapping with the Fallback sheet
**Ask:** *"Is 'Guardrail Questions/Conversations' the same as the Fallback & Safety Net sheet, or is
there a separate file we're missing?"*

### #12 — Are the sample conversations a script, or just a style example?
**Logic:** We need to know if your example conversations should be followed word-for-word, or if
they're just there to teach the AI's general tone.
**File:** `Convo_Samples.pdf`
**Ask:** *"Are the example conversations meant to be used word-for-word, or just to teach tone and
personality?"*

### #13 — A real person's name is hardcoded where a job role should be
**Logic:** Three rows tell the system to send a case to a specific person by name, instead of a
role like every other row. Risky if that person ever leaves the team.
**File:** `Kb_Phase_I_17.csv` (Fallback & Safety Net)
**Ask:** *"Three rows route cases to a person by name — can these be changed to a role instead?"*

### #14 — Small typos in scripts meant to be used exactly as written
**Logic:** A few reply scripts have small spelling mistakes. Since they're meant to be repeated
exactly, we'd rather your team correct them than we alter your clinical wording ourselves.
**File:** `Convo_Samples.pdf`
**Ask:** *"A few word-for-word scripts have small typos — can your team send corrected versions?"*

### #15 — We found more structure than first catalogued
**Logic:** We originally thought this sheet had 3 sections; it actually has a 4th plus a whole
separate 15-category table. We've already accounted for all of it — just want it confirmed as
complete.
**File:** `Kb_Phase_I_17.csv`
**Ask:** *"We found a 4th section plus a 15-category table in the Fallback sheet — can you confirm
this is the complete structure?"*

### #18 — Two versions of the same sheet disagree on row count
**Logic:** We have two exports of your severity-threshold sheet, and they disagree — 185 rows vs.
195. We built against the larger, newer-looking one.
**File:** `Kb_Phase_I_9.csv` vs. `Mindfully_Yours_Merged_Signal_Profile (2).xlsx`
**Ask:** *"Which version of the Signal Sufficiency sheet is correct — 185 rows or 195?"*

---

## The big reconciliation (from the September data drop)

### #23 — Emotion lists, Layer vs. Tier vs. Severity, and scenario lists
**Logic:** The new files introduce ideas that don't cleanly match your original system: a "how deep
is this conversation" scale (Layers I-IV) that's separate from "how serious is this" (Tiers 1-3);
a third severity scale (Mild/Moderate/Severe/Crisis) that doesn't obviously map to either; three
different emotion word-lists that don't fully agree; and two different category lists for sorting
what a conversation is about.

**Ask, exactly as already drafted for the clinical team:**

*About the emotion lists:*
1. We found three different lists of "emotions" across your documents — one with 19 items, one
   with 9 items, and one with 28 items. Is the 28-item list your intended final list?
2. If none of these is final, could someone review all three and send back one confirmed list?
3. Are any emotion names meant to mean the same thing under a different label (e.g. "Tensed" and
   "Anxiety")? If so, which name should we keep?

*About "Layers" vs. "Tiers" vs. "Severity":*
4. Can you confirm Layer (how deep the conversation has gone) and Tier (how serious it is) are two
   completely separate ideas, not meant to combine into one scale?
5. Is "Mild/Moderate/Severe/Crisis" meant to replace Tier 1/2/3, sit alongside it, or was it an
   earlier draft that Tier 1/2/3 already replaced?
6. Some of your documents treat "Tier 3" and "Crisis" as the same outcome, while one treats them as
   separate. Which is correct — should there be 3 severity outcomes total, or 4?

*About the category/scenario lists:*
7. Should the 30+-item category list and the ~22-item category list be merged into one? If they
   disagree, which should we follow?
8. One document has a section called "Scenarios That Were Left" with 10 more categories in a
   different style — merge into the main list, or keep separate?

### #24 — Some files stop partway through
**Logic:** A handful of conversation files are incomplete — missing scenarios, cutting off
mid-sentence, or listing topics that were never actually written.
**File:** `Trauma Related Conversations.docx`, `Conversations - Depression.docx`,
`Conversations Combination (Bipolar and Psychosis).docx`,
`Conversation Combinations- Life Transitions.docx`, `Conversations around Parenting.docx`
**Ask:** *"A few files look unfinished — can these be completed, or were they left incomplete on
purpose for now?"*

### #25 — Different writers use different seriousness labels
**Logic:** Some of your team tags conversations with Tier 1/2/3; others use made-up labels or none
at all — the seriousness scale isn't applied consistently yet across the team.
**File:** Tanisha's scripts (tiered) vs. Ankita's scripts (Nicotine cessation, Parenting — not tiered)
**Ask:** *"Can the team agree on using the same tiering system across all scripts going forward?"*

### #26 — One section needs a special safety decision, not a normal-topic decision
**Logic:** One section covers a very sensitive clinical topic — carefully written, not describing
actual abuse — but serious enough that it shouldn't be treated like an ordinary topic. It needs its
own explicit rule from both clinical *and* legal, before it's ever used live.
**File:** `List of Scenarios - Tanisha.docx`, "Fetishes" section
**Ask:** *"Can your clinical and legal team confirm exactly how the AI should handle this section
(e.g., always hand off to a human) before we activate it?"*

### #27 — 3 files still locked
**Logic:** Three files use a different password than the other 43 in the same folder.
**File:** `Anam/Conversation Combinations- sleep.docx`,
`Anam/Conversations Combinations- anxiety 3rd person.docx`, `Anam/Miscellaneous Conversations.docx`
**Ask:** *"Can you get us the correct password for Anam's 3 remaining files, or ask her directly?"*
