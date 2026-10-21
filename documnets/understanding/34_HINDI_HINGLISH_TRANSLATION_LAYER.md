# 34. Hindi / Hinglish — the translation layer

**Date:** 2026-10-09. **Why:** the therapist library, the red-flag examples and the self-care content are English only, so a Hindi or Hinglish user was (a) not protected by the safety check, (b) not served by the therapist library, and (c) sometimes answered in the wrong language. Decision: use **Sarvam translation** so Hindi/Hinglish users get the same pipeline as everyone else and a reply in their own language, fast and accurate.

## How it works (per turn)
```
user message (Hindi / Hinglish / mixed)
  └─ instant language check (Devanagari or common Hinglish words) ── English? skip everything below
  └─ Sarvam translate → English            (~0.7 s, mayura:v1; the only extra live call)
  └─ the WHOLE pipeline runs on the English text: embedding, safety interlock, triage, tier score,
     therapist match, self-care search
  └─ reply, in the user's language:
       • fixed replies (therapist reply, clarifying question, red-flag script, welcome, fixed messages)
           → looked up in kb_translations, pre-translated offline (a few ms)
       • LLM-written replies (no match / partial match) → the LLM writes directly in the user's language
           (no extra translation call, streaming kept)
```
The original text is kept for the LLM prompt and the conversation record. If input translation fails the turn continues on the original text (as before) and the English-only therapist steps are skipped.

## Why these choices (all measured live, 2026-10-09)
| Question | Finding |
|---|---|
| Which model? | **mayura:v1** (mode `modern-colloquial`). "mujhe marne ka mann kar raha hai, ab aur jeena nahi chahta" → "I feel like dying, now I don't want to live anymore." `sarvam-translate:v1` was faster (~0.6 s) but turned "I got laid off yesterday aur mujhe lag raha hai ki main failure hoon" into "I felt depressed when I lost my job yesterday" — not used. |
| How fast? | ~0.7 s per call; ~1.5 s when an output-script option is set. Too slow for every reply → fixed replies are **pre-translated**. |
| Source language code | Always `hi-IN`: handled Devanagari, Romanised and code-mixed input, ~0.4 s faster than `auto`. |
| Output script | `hi` users get Devanagari (English loanwords stay in Latin, as people write them); `hinglish` users get Roman script. |
| Long messages | Input limit ~1000 chars → split on sentence boundaries and translated in parallel, never truncated (a crisis line at the end must not be lost). |

## What was built
| Piece | Where |
|---|---|
| Translator (persistent client, chunking, Roman/Devanagari output) | [translation.py](../../backend/app/providers/translation.py), `get_translator()` in `factory.py` |
| Language check + explicit language line for every LLM prompt | [language_hint.py](../../backend/app/pipeline/language_hint.py), `prompt_builder.py` |
| `kb_translations` table + instant lookup / live fallback / store | [localize.py](../../backend/app/pipeline/localize.py), model in `kb_convo_content.py`, migration `c9e5a1b2d744` |
| Orchestrator: translate-in up front, localise outputs, language-aware rephrase guard | [orchestrator.py](../../backend/app/pipeline/orchestrator.py), `guardrail.py` |
| Offline pre-translation: `python -m app.ingestion.cli translate-kb` (resumable; priority order: red-flag scripts, fixed messages, clarifying questions, welcome, therapist replies) | `cli.py` |
| Welcome in Hindi/Hinglish: `reply_language` on `POST /api/v1/conversation/welcome` | `welcome.py`, schema, endpoint |
| 11 new unit tests (50 total pass) | `test_translation.py`, `test_language_hint.py` |

## Results (real pipeline)
- **The safety gap in [15 #29](15_OPEN_QUESTIONS_AND_BLOCKERS.md) is mostly closed:** the Devanagari and Romanised "I want to die" messages now trigger the red-flag script, **returned in the user's own language** (Devanagari / Roman). Before: not escalated at all.
- A Hinglish message about moving away → the therapists' own reply, translated into Roman Hinglish; English users unchanged.
- Latency: Hindi crisis turn ≈ **2.0–2.2 s** total with pre-translated scripts (English ≈ 1.3 s); the live-translated first run was 2.8–3.5 s. Most of the variance is the OpenAI embedding call (0.3–1.3 s).

## Known limits (honest)
1. **Translation nuance can soften an idiom.** "kabhi kabhi lagta hai sab khatam kar du apni life" came out as "Sometimes it feels like I should finish everything in my life" and was NOT escalated (the LLM answered with a caring, non-script reply). The English equivalent "sometimes I think about ending it all" is only caught at 0.39. A clinician-approved **Hindi/Hinglish crisis-word safety net** checked in code on the original text is still worth adding next to the translation — [15 #29](15_OPEN_QUESTIONS_AND_BLOCKERS.md) option (a).
2. **Machine-translated crisis scripts are `reviewed = false`** in kb_translations. They are served (better than English for a Hindi speaker), but a clinician/native speaker should review them (`select source_text, translated_text from kb_translations where source_kind='red_flag_script'`).
3. **Pre-translation of the ~5,100 therapist replies** is rate-limited by Sarvam (~100/min) — about 1.5 hours per run for both languages. It runs in the background and is resumable (re-run `translate-kb`); a reply not yet translated is translated live (+0.7–1.5 s) the first time and stored.
4. **Rephrase guard is weaker for Hindi:** when the LLM writes a partial-match reply directly in Hindi from the English examples, word-overlap can't be checked across languages — only empty / numbers-links checks apply.
5. **Language detection is a heuristic** (instant, no API call). Hinglish using none of the listed words is treated as English. Mixed messages count as non-English.
6. A **mixed message may still get an English LLM reply** (observed once) — the instruction is now repeated last in the rephrase prompt; re-check with real users.
7. **Embedding timeouts fail safe:** the embedding call has a 3 s timeout (right for the latency budget); when OpenAI is slow the turn is answered with "let me connect you with someone" (seen in ~1 in 15 test turns). Consider one quick retry before failing safe.
8. Hindi users still don't get the therapists' *Hindi* wording — they get a machine translation of the English reply. A therapist-written Hindi library remains the long-term answer ([13](13_LANGUAGE_PHASING.md)).
9. **Sarvam rate limit (~100 requests/min on the current key; HTTP 429 "rate_limit_exceeded").** Hit during the bulk pre-translation. It matters beyond that job: every Hindi/Hinglish turn makes at least one live call (+1 for any reply not yet pre-translated), so production concurrency is capped by this limit. Confirm the plan/limit with Sarvam before launch; the bulk job and live traffic also share it, so don't run `translate-kb` against a production key during peak hours. Failed items from a rate-limited run are simply picked up by re-running `translate-kb`.

## Status when this was written
Pre-translated: all red-flag/fallback scripts, fixed messages, generic clarifying questions and welcome messages, in both languages. The ~5,160 approved therapist replies were still being translated in the background (Devanagari first, then Roman); progress: `select style, count(*) from kb_translations where source_kind='therapist_reply' group by 1`. Until a reply is translated it is translated live the first time (+0.7–1.5 s) and stored.

