# Which architecture PDF should I open?

This folder has **three** architecture PDFs that look like versions of the same document. **They
are not duplicates and none of them should be deleted** — each contains real decisions the other
two don't, and they genuinely disagree with each other in a few places. Read this before opening
any of them, so the disagreement doesn't get mistaken for a rendering issue or a stray file.

| File | What it is | Read it for |
|---|---|---|
| **`Mindfully_Yours_Phase1_Final.pdf`** | The client-facing "final" version | The default starting point — the fullest, most complete 12-section diagram |
| **`Mindfully_Yours_Phase1_English_Architecture.pdf`** | A later, more internally-consistent cleanup pass | The single-STT-vendor decision, the corrected "replies in English" wording, the committed (not open) Hindi Phase-2 roadmap, and a sharper 4-state tier/crisis model |
| **`Mindfully_Yours_Phase1.pdf`** | An earlier draft | The **only** place the earlier avatar vendor (Spatius.ai) and its unconditional (non-cost-gated) rendering approach are documented — since replaced by HeyGen + a cost gate in the other two |

## The exact places they disagree (full detail already written up — don't re-derive this)

- **Avatar vendor**: `Phase1.pdf` → Spatius.ai (no cost gate). `Phase1_Final.pdf` / `English_Architecture.pdf` → HeyGen (cost-gated). See `documnets/understanding/03_TECH_STACK.md` §3 and `documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md` #8.
- **STT vendor**: `Phase1_Final.pdf` / `Phase1.pdf` → Deepgram *and* Sarvam. `English_Architecture.pdf` → Deepgram only. See `15_OPEN_QUESTIONS_AND_BLOCKERS.md` #9.
- **Tier / crisis model**: `Phase1_Final.pdf` / `Phase1.pdf` → 3 tiers (Tier 3 = SOS). `English_Architecture.pdf` → 4 states (Tier 3 and "Crisis" are separate). See `documnets/understanding/08_SAFETY_INTERLOCK_AND_TRIAGE.md` §3 and `15_OPEN_QUESTIONS_AND_BLOCKERS.md` #7.
- **Hindi/Hinglish handling**: `Phase1_Final.pdf` / `Phase1.pdf` present it as an open decision between two options. `English_Architecture.pdf` presents it as already settled. See `documnets/understanding/13_LANGUAGE_PHASING.md` §3.

**None of this is accidental clutter — it's real, unresolved decision history.** The fix for the
ambiguity isn't deleting two of the three files; it's this README, plus the fact that every
disagreement above is already tracked as an explicit open item in
`documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md`, waiting on a single client decision at
the technology review. Once that decision is made, update the four bullets above (and their linked
docs) to say which PDF won, rather than treating this as still open.
