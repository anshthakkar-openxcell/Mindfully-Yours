# Mindfully-Yours

AI-led mental and emotional-wellness companion and triage platform — RAG-based conversational AI, silent clinical triage, and an independent, deterministic safety interlock.

## Repository layout

- **`documnets/`** — the full project understanding: client-provided architecture PDFs, the clinical knowledge base (signals, routing rules, red flags, fallback logic), and a synthesized, implementation-ready reference set in `documnets/understanding/` (**start at `documnets/understanding/00_INDEX.md`**).
- **`backend/`** — the Python/FastAPI AI service (RAG pipeline, silent triage, safety interlock, KB ingestion). See `backend/README.md` for setup. This is the current build scope — see `documnets/understanding/14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md` for exactly what is and isn't in scope.

## Where to start

1. Read `documnets/understanding/00_INDEX.md` for the full picture.
2. Read `documnets/understanding/01_PROJECT_OVERVIEW.md` and `08_SAFETY_INTERLOCK_AND_TRIAGE.md` — the non-negotiable safety principles every implementation decision is checked against.
3. Set up the AI service per `backend/README.md`.
