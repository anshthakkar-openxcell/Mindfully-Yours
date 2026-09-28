# The Real Useful Knowledge

This folder physically sorts **every real, AI-facing piece of knowledge this project has received**
into the 3 usage buckets we've been using throughout `documnets/understanding/`. It exists so
someone building this system can open one folder and immediately know *what a file is for*,
without having to re-derive it.

**These are copies, made on purpose** — not a fourth accidental duplicate. The originals stay
exactly where they were (`documnets/knowledgebase/`, `documnets/knowledgebase/convo data/`,
`documnets/approch/`); this folder is a curated, re-sorted reading/working copy for implementation,
organized by *purpose* instead of by *which team member or client delivery it arrived in*.

**The full reasoning for every single placement below — file by file, why it's in that bucket, and
exactly how it gets used at runtime — already exists and is not repeated here:**
[`documnets/understanding/19_DATA_USAGE_MAP.md`](../understanding/19_DATA_USAGE_MAP.md) (also available as
a styled PDF in that same folder). Read that file if you need the "why," not just the "where."

## The one-question test behind all 3 buckets

> Is this something a person might actually **say** (→ Bucket 1 or 2), a real **thing to hand
> back** to them (→ Bucket 2), or a **number/rule** the code just checks (→ Bucket 3)?

## The 3 buckets

| Folder | In plain words | Never forget |
|---|---|---|
| **1. Teach The AI How To Talk (Style Only)** | Loaded once, shapes tone/persona. The AI never searches these live. | If you're tempted to "search" one of these files at runtime, that's the wrong bucket for it. |
| **2. Search And Match Or Recommend (Real Content)** | Embedded and searched on every real turn — either to figure out what the user means, or to find a real exercise/answer to give them. | Two different jobs live here (matching vs. recommending) — see 19_DATA_USAGE_MAP.md §2a/2b for which files do which. |
| **3. Become Code Logic (Rules, Thresholds, Decisions)** | Never embedded, never searched. Gets read once by a developer and turned into actual `if/else` code. | If someone tries to "RAG search" one of these files, that's a sign the design has gone wrong somewhere. |

## What's deliberately NOT in any bucket, and why

- **`Career Conversation Sets 1.docx`** — not included anywhere. It's not real content; it's one conversation template copy-pasted ~500 times with a career name swapped. See [18_NEW_CONVO_DATA_CATALOG.md](../understanding/18_NEW_CONVO_DATA_CATALOG.md).
- **3 still-locked Anam files** (`Conversation Combinations- sleep.docx`, `Conversations Combinations- anxiety 3rd person.docx`, `Miscellaneous Conversations.docx`) — not included because they're still password-protected. See [15_OPEN_QUESTIONS_AND_BLOCKERS.md](../understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md) #27.
- **Internal planning/meta documents** (`Knowledge_Base_Directory(Sheet1).csv`, `chunking .docx`, `CHUNKING_EMBEDDING_STRATEGY.md`, `CONVERSATION_REASONING_FLOW.md`, the master `Kb Phase I.xlsx` workbook, the merged-profile `.xlsx` files) — these are either internal build documentation that never reaches the AI, or the same content already present here via its individual CSV export. Not duplicated into these buckets on purpose.
- **⚠ Sensitive content flagged for governance, not exclusion**: `List of Scenarios - Tanisha.docx` (Bucket 2) and `22-8_Offline Work Week 2.docx` (Bucket 1) both contain a "Fetishes"/paraphilic-disorder section (including Pedophilic and Sexual Sadism Disorder content, handled carefully as non-offending help-seeking material). These files are *included* because the rest of their content is usable, but **that specific section must not be wired into anything live until the clinical + legal team makes an explicit decision** — see [15_OPEN_QUESTIONS_AND_BLOCKERS.md](../understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md) #26.

## Keeping this folder honest over time

If a new file arrives or a decision changes which bucket something belongs in, update **three
places together**, not just one: the source file's entry in
[19_DATA_USAGE_MAP.md](../understanding/19_DATA_USAGE_MAP.md), this README's exclusion list if relevant, and
the actual copy sitting in whichever bucket folder here. Don't let this folder quietly drift out of
sync with the reasoning document it's built from.
