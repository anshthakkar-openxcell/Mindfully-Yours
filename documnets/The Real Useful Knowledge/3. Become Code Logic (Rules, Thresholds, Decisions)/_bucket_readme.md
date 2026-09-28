# Bucket 3 — Become Code Logic

Never embedded, never searched. A developer reads these once and turns them into actual `if/else`
code, lookup tables, and decision trees. If you find yourself building a vector index over one of
these files, that's a sign something has gone wrong — these are precise, deterministic rules, and
searching them would make the system slower AND less reliable than just reading them directly.

- `Kb Phase I(C11.csv` — Routing Rules. Evaluate strictly in `priority` column order (1→2→3),
  **never** by `rule_id` — these genuinely diverge in the real data.
- `Kb Phase I(9.csv` — Signal Sufficiency thresholds (minimum/must-have signals per tier).
- `Kb Phase I(17.csv` — Fallback & Safety Net conditions (turn count, confidence score — checked
  against conversation state, not text).
- `Pathway For AI In Different Situations - Tanisha.docx` — the master 15-step decision flow.
  This becomes the actual control flow of the conversation orchestrator.
- `Mindfully_Yours_AI_Latency_Filler_Phrases.pdf` — filler-phrase lookup table, selected by
  situation type, not by meaning-based search.
- `Parenting_Child Related.docx` — mainly valuable for its Guardrail table (concern → referral
  urgency), a ready-made escalation-rule structure.

Full reasoning for every file here: [`../../understanding/19_DATA_USAGE_MAP.md`](../../understanding/19_DATA_USAGE_MAP.md) §Bucket 3.
