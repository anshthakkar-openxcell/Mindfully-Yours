# 28. Tier Scoring — Approach and Implementation

## Status: implemented (2026-09-30), point values still pending clinical review

This documents the approach for how Tier (1/2/3) is decided as a conversation progresses, replacing
a single-message "does this qualify" check with a running score. **Now implemented** in
`app/pipeline/tier_scoring.py`, wired into `app/pipeline/orchestrator.py`, and live-tested end to
end (see "What's been built and tested" below). The exact point values, brackets, and heuristics are
still explicitly provisional -- a starting point for the clinical team to review, not a validated
model.

## The core idea

Track a **running score per conversation, 0-100**, that moves a little with every message, instead
of deciding Tier fresh on each message in isolation. The Tier is whichever bracket the current score
falls into — a level the conversation has climbed to, not a one-shot verdict.

`app/pipeline/state.py`'s `ConversationState` already has an unused `confidence_score: float` field
sitting ready for exactly this purpose, and `duration_established` / `impact_established` boolean
flags that were clearly built for this too.

## What moves the score, each message

**1. Severity of what just matched.** Every signal in `kb_signals` already has a severity weight
(1/2/3). A mild signal adds a few points; a severe one adds a lot more.

**2. New concern vs. repeat of the same one.** The same worry mentioned three different ways
shouldn't triple-count. Three genuinely *different* signals (sleep problems + hopelessness +
withdrawal) should count for more than the same signal repeated three times.

**3. Have the two key clinical questions been answered?** Duration ("how long has this been going
on") and impact ("is it affecting daily life") are the two flags already sitting in
`ConversationState`, unused. Once both are known, that's worth a real score jump — genuine clinical
confidence, not just more conversation turns.

## CORRECTED 2026-09-30: there is no score-based Tier 3 — the bracket only has two rungs

**This is the single most important correction to this whole design, caught by direct feedback after
reading a real worked example.** The original version of this doc (and the first implementation) had
a three-row bracket where a score of 70+ was labeled "Tier 3." That is wrong, and it stayed wrong
until this correction: **Tier 3 must mean one thing only — a genuine crisis/SOS situation** (active
self-harm intent, "I don't want to live," and similar), handled *exclusively* by the safety interlock
(`app.safety.interlock`), checked independently on every single message, regardless of this score.

An ordinary conversation — even a real, worth-attention one, like someone describing weeks of work
stress that's started affecting their job — must **never** be able to climb its way into the same
label as an actual self-harm disclosure, no matter how high the running score gets. Those are
fundamentally different situations and sharing a name (or a score-based path to that name) is a real
design bug, not a cosmetic one. Confirmed in testing: the sustained-work-stress example below reaches
a full 100/100 score and correctly stays at **Tier 2** — never Tier 3.

The corrected bracket has only two rungs:

| Score | Tier | Meaning |
|---|---|---|
| 0-39 | 1 | Self-care conversation continues |
| 40-100 | 2 | Worth real attention — ask more, and once genuinely confident, suggest a practitioner |

**Tier 3 does not appear in this table at all.** It is not a score bracket — it is the name of the
safety interlock's own, completely separate, always-on crisis path. `tier_from_score()` in
`app/pipeline/tier_scoring.py` can only ever return 1 or 2; there is no code path in the scoring
system that produces a 3.

This cutoff is a placeholder for discussion, the same way every other threshold in this
project (`REDFLAG_MATCH_THRESHOLD`, `RETRIEVAL_CONFIDENCE_THRESHOLD`, `TRIAGE_SIGNAL_THRESHOLD`) has
been an explicitly-flagged starting guess pending real validation data — see
[15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #28.

## Score and "redirect to booking" are two different decisions, not one

**Clarified 2026-09-30.** Hitting Tier 2 (the highest the score can ever reach — see the correction
above) is not, by itself, permission to push the user toward booking a consultation. The score is a fast-moving read of "how concerning does this
look so far" — it can jump to a high number off one strong message. Redirecting someone to book an
appointment is a much bigger, more consequential action than sending one more reply, so it needs its
own, separate confirmation, not an automatic reaction to a number crossing a line.

**The default behavior at every tier, including 2 and 3, is to keep the conversation going**: ask the
right follow-up question for what's been said, and suggest a relevant self-help exercise (real
content for this is still to come — see below) — the same way the system already behaves today. A
high score changes *how carefully* the bot listens and *what it asks next*, not that it should
immediately try to hand the person off.

**The redirect to booking only fires once the conversation has built real confidence**, not just
once the score crosses 70. Concretely, that means the corroborating evidence already designed
elsewhere in this doc has actually shown up over multiple turns — genuinely distinct signals (not the
same worry restated), and ideally both `duration_established` and `impact_established` from
`ConversationState` actually answered by the user, not assumed. A single striking sentence can move
the score fast, but shouldn't by itself flip the "confident enough to redirect" switch — that switch
needs the pattern to hold up across the conversation, which naturally takes a few more exchanges of
listening and asking.

This mirrors exactly the two-step split already agreed for the red-flag interlock (see
[15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #28's follow-up on avoiding a
premature crisis redirect): give the immediate, warm response and relevant guidance right away, but
gate the heavier "hand this off to a human / book something" action behind a short confirmation
window, not the very first data point.

**Self-help exercise content — still needed, not yet built.** What exercise to suggest at Tier 1/2,
matched to which signal/pattern, needs real content — this section is a placeholder until that's
provided and wired in as retrievable guidance (the same `search_self_care_content` / probing-guidance
path already used for Tier 1 today).

## What stays completely separate from the score

**The red-flag safety interlock never waits for score to build up, and the score can never reach it
either.** A genuine danger phrase is an immediate Tier 3/crisis response, checked independently,
every turn, regardless of what the running score currently says — and, per the correction above, the
score has no path INTO Tier 3 even if it wanted to; it caps out at Tier 2. The score system is for
the slower, accumulating picture of "how serious is this pattern turning out to be" for everything
short of a genuine crisis — not a substitute for instant danger detection, and not a second route to
the same label.

## The score can go down, not just up

**Implemented as a simple decay, not yet the richer version originally imagined.** Any turn that
contributes no new signal and establishes nothing new eases the score down by
`TIER_SCORE_DECAY_PER_QUIET_TURN` (default 5) rather than leaving it stuck at a high point from one
earlier message — live-tested: two neutral turns in a row brought a score down from 100 → 95 → 90 →
85 cleanly. `kb_sufficiency_patterns.graceful_exit_trigger` (a real "the user is showing genuine
improvement" signal per pattern) is NOT wired in yet — the current decay is purely "nothing new
happened," not "things are actually getting better." Wiring in `graceful_exit_trigger` properly is a
follow-up, not done today.

## Known risk this design must account for: topic similarity isn't danger

Live-tested (2026-09-29): ordinary relationship language ("I want to leave my partner") scores close
to real red-flag phrases purely because of shared vocabulary ("partner"), not real danger content —
see [15_OPEN_QUESTIONS_AND_BLOCKERS.md](15_OPEN_QUESTIONS_AND_BLOCKERS.md) #28's false-positive
example. The same risk applies to signal-based scoring here: a score built purely from embedding
similarity will inherit the same "topic overlap looks like meaning overlap" problem. This is a
direct argument for why the score should require **multiple distinct corroborating signals**
before moving far, rather than letting one ambiguous match swing it — exactly the "accumulate,
don't assert" principle already built into how signals feed into `ConversationState`.

(That specific interlock-level false positive has since been mitigated with a narrow, flag-specific
fix, not a general solution to this risk — see the same doc's item #28 follow-up entries for the
soft-zone fix and the related suicide/self-harm false-negative finding it surfaced. The risk
described above still applies in full to any *future* embedding-based scoring, including this one.)

## What's been built and tested (2026-09-30)

`app/pipeline/tier_scoring.py`: `update_score()` mutates `ConversationState.confidence_score` each
turn using `kb_signals.severity` / `kb_symptoms.max_linked_severity` for newly-observed signals
(`SEVERITY_POINTS = {1: 8, 2: 15, 3: 25}`, illustrative only); `tier_from_score()` maps the score to
Tier 1 or 2 via `TIER2_SCORE_MIN` (40, tunable via env) -- **capped at 2, can never return 3** (see
the correction above); `should_redirect_to_booking()` is the separate confidence gate described above
(tier >= 2 AND both duration/impact established AND `REDIRECT_MIN_DISTINCT_SIGNALS` distinct signals
observed, default 3). Wired into `app/pipeline/orchestrator.py` right after triage (runs every turn,
same as triage, regardless of cache hits) and into `turn_audit_log` (`confidence_score`, `score_tier`,
`redirect_ready` columns, migration `f97bfc5c8578`).

**Bug #1, found and fixed during first live test**: the very first test message matched 9 signals at
once (triage's already-documented per-message noise -- see `TRIAGE_SIGNAL_THRESHOLD`'s comment) and
summed straight to a maxed-out 100/100 score on turn one, defeating the entire point of a score that
accumulates gradually. Fixed with `TIER_SCORE_MAX_GAIN_PER_TURN` (default 25) -- a hard ceiling on
how many points any single turn can contribute, regardless of how many signals it matched.

**Bug #2, a real design bug, found after reading a worked example against real-world judgment**: the
first working version DID let the score reach a bracket labeled "Tier 3" at 70+. Live-tested example:
a 5-turn conversation about sustained work stress (procrastination, a missed deadline, low motivation,
withdrawing from friends) legitimately climbed to 95-100 and was being labeled "Tier 3" -- the exact
same label as an actual self-harm disclosure. That is wrong regardless of the number: an ordinary,
if worth-attention, conversation must never share a label with a genuine crisis. Fixed by removing
the score-based Tier 3 bracket entirely -- see the correction section above. Re-tested after the fix:
the identical 5-turn conversation now correctly climbs to a full 100/100 score while staying at
**Tier 2** throughout; a separate real crisis message ("i want to kill myself") in a fresh session
still correctly produces an immediate Tier-3-equivalent response via the safety interlock, entirely
independent of the score (its `confidence_score` was 0 at the time -- the two systems don't interact).

**Live-tested end to end after both fixes**, the same 5-turn work-stress conversation: score climbed
35 → 60 → 95 → 100 → 100, tier stayed 1 → 2 → 2 → 2 → 2, and `redirect_ready` correctly stayed `False`
until turn 3, once BOTH duration and impact had actually been confirmed and enough distinct signals
had accumulated -- not on turn 1's single message alone. The resulting reply on a redirect-ready
turn: *"It might help to talk with a mental health professional who can support you through this in a
safe, understanding space. Would you like help finding someone to speak with, or help with how to go
about booking an appointment?"* -- gentle, not alarming, and only appeared once the gate actually
cleared. A regression check confirmed the red-flag interlock (crisis escalation, RF-028 soft zone)
behaves identically to before this change -- this module runs alongside it, never gates it, and now
can never be mistaken for it either.

## Upgraded 2026-09-30: duration/impact detection now reads the message, not keyword-matches it

The original v1 checked `duration_established` / `impact_established` with a hardcoded keyword list
(`DURATION_CUES` / `IMPACT_CUES`) -- flagged at the time as a rough placeholder, since
`kb_sufficiency_patterns.confidence_rule` describes these as free-text clinical judgment calls
("pattern persists beyond normal mood fluctuations", "causing gradual impairment"), which a fixed
phrase list can't really assess.

**Replaced** with a small, cheap LLM classification call (`_detect_duration_and_impact_llm()` in
`app/pipeline/tier_scoring.py`) -- NOT the main conversation reply, a separate short one asking the
model to answer two yes/no questions about the current message and quote the exact phrase that
justifies each answer, so it stays checkable rather than an unexplained opinion. Only called on
turns where at least one of the two flags is still unconfirmed -- once both are established, the
call is skipped entirely, so the added cost naturally drops to zero later in a conversation.

**Live-tested against phrasing the old keyword list would have missed entirely**: *"honestly this
has been my reality for around a month now"* (no literal "for weeks/months/a while" match) correctly
set `duration_established`, and *"it's really starting to get in the way of how i do at my job"* (no
literal "affecting my" match) correctly set `impact_established` -- both parsed cleanly with no
errors. Measured cost: roughly 200-370ms added only on the turns where the check actually still
needs to run (confirmed via a new `tier_score_ms` latency field), and effectively 0ms once both
flags are already confirmed for the rest of the conversation.

Fails closed on error (network failure, unparseable response): both flags are treated as "not yet
established" for that turn rather than guessed -- worst case is asking again next turn, never
wrongly marking something confirmed that was never actually said.

Still not solved: this reads only the CURRENT message, not the fuller conversation history (recent
multi-turn context isn't wired into the pipeline yet -- see `prompt_builder.py`'s own TODO on this),
so it still can't catch something confirmed several turns ago and never repeated. And it's still an
LLM judgment call, not a clinically validated instrument -- same posture as everything else here.
- Live testing also surfaced that a couple of existing red flags (RF-006 "Emotional Numbing", RF-010
  "excessive daytime sleepiness") fired on fairly ordinary distress language ("can't sleep anymore",
  "don't enjoy anything") during this same test session -- noted here as a possible future review
  item (same noisy-matching class of issue as RF-025's fix in item #28's earlier follow-up), but not
  investigated or fixed as part of this task.
- Self-help exercise content is still not supplied -- Tier 1/2 guidance still only uses whatever
  `search_self_care_content` / probing guidance already returns; nothing new was added here for
  exercises specifically.
- `SEVERITY_POINTS`, the tier brackets, and `REDIRECT_MIN_DISTINCT_SIGNALS` are all still exactly
  the kind of small-sample, engineering-chosen starting point that needs real clinical-team review,
  same posture as every other threshold in this project.
