# Bucket 2 — Search And Match Or Recommend

Embedded and searched live, on every real conversation turn. Two different jobs live in this one
folder — don't confuse them:

- **Matching** (figuring out what the user means): `Kb Phase I(A1.csv`, `Kb Phase I(A2.csv`,
  `Kb Phase I(7.csv`, the emotion files, `List of Scenarios - Tanisha.docx`, `Anxiety
  Situations.docx`, and all the `Layer *` question banks + `Questions*.docx` files. Nothing here
  is shown to the user directly — it's used to detect what's going on.
- **Recommending** (real content handed back to the user): `dbt-skills-workbook.docx` (+ its PDF),
  `brain-dump-worksheets.pdf`, `SELF-HELP CONVERSATIONS.docx`. These ARE meant to reach the user.

Full reasoning for every file here, including exactly which is which: [`../../understanding/19_DATA_USAGE_MAP.md`](../../understanding/19_DATA_USAGE_MAP.md) §Bucket 2a/2b.

Note: `Career Field & Stream Lookup.csv` isn't a client-original file — it's the real, deduplicated
data extracted from `Career Conversation Sets 1.docx` (which claimed 500 conversations but was 1
template repeated 500 times). Pair it with the canonical template in Bucket 1.

⚠ `List of Scenarios - Tanisha.docx` contains a "Fetishes" section pending a governance decision —
see the top-level `README.md` in this folder and
[`15_OPEN_QUESTIONS_AND_BLOCKERS.md`](../../understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md) #26 before using it.

⚠ `Kb Phase I(7.csv`'s `bot_script` column is a **special case**: once a row is matched, its
script is fetched word-for-word, never paraphrased by the AI — see
[`08_SAFETY_INTERLOCK_AND_TRIAGE.md`](../../understanding/08_SAFETY_INTERLOCK_AND_TRIAGE.md) §4.
