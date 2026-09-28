# Career Indecision — Canonical Template (deduplicated)

> **Where this came from**: `Career Conversation Sets 1.docx` (in `documnets/knowledgebase/convo data/`)
> was not really "500 conversations" — it was this exact template, copy-pasted 500 times with only
> the career name and academic stream swapped each time. See
> [`18_NEW_CONVO_DATA_CATALOG.md`](../../understanding/18_NEW_CONVO_DATA_CATALOG.md) §4c and
> [`15_OPEN_QUESTIONS_AND_BLOCKERS.md`](../../understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md) #24 for
> the original finding. This file is the real, deduplicated content: **one** template, kept once,
> plus the placeholders it needs. The 500 real (career, field, stream) combinations that used to be
> "500 fake conversations" now live as genuine structured data at
> [`../2. Search And Match Or Recommend (Real Content)/Career Field & Stream Lookup.csv`](<../2. Search And Match Or Recommend (Real Content)/Career Field & Stream Lookup.csv>) —
> use the two files together, not this one alone.

## The template, verbatim, with the two things that ever actually changed marked as placeholders

```
User: I don't know what career I want.
AI: Hey, what confusion are you facing regarding your career? What specialisation to take, or what job do you want?
User: Hmmm… I don't know what stream to choose.
AI: Would you like to share what you are currently doing?
User: I have finished my 12th grade, but now I am confused about what I should pursue
AI: Which stream have you chosen in 12th?
User: [STREAM]
AI: Are there any career options you find particularly interesting?
User: I like [CAREER_NAME] interesting
AI: What do you find interesting about it or what draws you towards the career?
User: I like the lifestyle/ money/ profile/ subjects
AI: Have you explored or read about any options in this particular field?
User: Not really. Can you share any career options?
AI: While I wish I could guide you about what careers you could select, I am better equipped to deal with underlying emotions.
User: No, I am not feeling anything in particular.
AI: Okay, feel free to reach out to me if you are feeling overwhelmed or confused about what choice to make. I am here for you
```

- `[STREAM]` — fill from the lookup CSV's `likely_academic_stream` column for whichever career the user names (one of exactly 4 real values: `Commerce`, `Science (PCB)`, `Science (PCM)`, `Science Or Commerce or Arts`).
- `[CAREER_NAME]` — fill from the lookup CSV's `career_name` column.

## Why this belongs in Bucket 1, not Bucket 2

This is a **style/pattern example** — how the AI should open and hold a career-indecision conversation, including its deliberate scope boundary ("I am better equipped to deal with underlying emotions" — the AI declines to give concrete career advice). It is loaded once to shape tone, the same as every other file in this bucket — it is not searched or picked live. The *data* that varies per-user (which career, which stream) is a completely different kind of content and lives in Bucket 2 instead, per [`19_DATA_USAGE_MAP.md`](../../understanding/19_DATA_USAGE_MAP.md)'s Bucket 1 vs. Bucket 2 rule.

## Overlap note

This same "declines specific career advice, offers emotional support instead" pattern already exists in `Convo_Samples.pdf`'s "Need help deciding career" scenario and in `Career and Academic Conversation - Samples.docx`. Treat this file as one more confirming example of an already-established pattern, not a new one — its real, non-redundant value is the 500-row lookup table it's paired with, not the template text itself.
