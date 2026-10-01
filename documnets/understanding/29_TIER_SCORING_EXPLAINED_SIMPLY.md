% Understanding the Tier & Scoring System
% Mindfully Yours — Explained in Simple Terms, With Real Examples
% 2026-09-30

# What Problem Are We Solving?

Before this system existed, the bot decided "is this a big deal or not" **fresh on every single message**, with no memory of anything said earlier in the conversation.

That's not how a real, caring listener works. A good listener doesn't panic at one dramatic sentence, and doesn't ignore a pattern just because no single message was alarming on its own. They build understanding **across the whole conversation** — noticing when something keeps coming up, when it's been going on a while, and when it's actually affecting someone's life.

The Tier & Scoring system is our attempt to give the bot that same kind of memory and judgment.

<!--DIAGRAM_BEFORE_AFTER-->

# The Core Idea: A Running Score

Every conversation carries an invisible number from **0 to 100**, sitting quietly in the background. It moves up or down a little after every message — it is never decided all at once from a single sentence.

Think of it like a **fuel gauge for concern**: it fills up gradually as real evidence builds, and it can drain back down if the conversation turns out to be lighter than it first seemed.

This number is what decides the **Tier — and it can only ever land on Tier 1 or Tier 2, never Tier 3:**

| Score range | Tier | What it means |
|---|---|---|
| 0 – 39 | **Tier 1** | Ordinary conversation — self-care chat continues |
| 40 – 100 | **Tier 2** | Worth real attention — the bot listens more carefully, and once genuinely confident, suggests real professional help |

**Tier 3 does not appear in this table on purpose.** Tier 3 means one thing only — a genuine crisis (active self-harm intent, and similar) — and it is handled by a completely separate, always-on safety check, never by this running score. No matter how high this number climbs, it cannot produce a Tier 3 response. Why this matters, and a real mistake we caught and fixed because of it, is covered later in this document.

The 40-point cutoff is our best starting guess, not something a clinician has signed off on yet — more on that at the end.

# What Actually Moves the Score

Three things move the number, and only three:

## 1. New, genuine signs of concern

The doctors who built this system already gave us a long list of "signs" — specific things a person might say that point to a real concern, each with its own **severity rating** (mild, moderate, severe) that the doctors themselves assigned. A few real examples from that list:

| What the doctor calls it | Category | Severity | What it sounds like |
|---|---|---|---|
| Anhedonia | Mood | Moderate | "Nothing feels enjoyable anymore" |
| Hopelessness | Mood | Moderate | "What's even the point" |
| Excessive daytime sleepiness | Physical | Mild | "I can sleep 12 hours and still feel exhausted" |

Every time a message contains something that matches one of these signs, we check its severity and add points — a mild sign adds a few points, a severe one adds a lot more. The exact point values are a starting guess (see the last section), but the *idea* — worse things add more — is straightforward.

## 2. Saying the same thing three different ways doesn't count three times

If someone mentions the same underlying worry in three different messages — "I feel low," then later "I just feel so empty," then later "nothing matters anymore" — that's really **one** concern repeated, not three separate ones. The system only rewards **genuinely new, different** concerns showing up. Three *different* real worries (say, sleep trouble **and** hopelessness **and** pulling away from friends) count for much more than the same one restated three times.

## 3. Two key questions, once they're actually answered

There are two questions any real counsellor would want answered early on:

- **"How long has this been going on?"** — a bad day is very different from a bad month.
- **"Is this actually affecting your day-to-day life?"** — sleep, work, relationships, eating.

Once the person has genuinely told us the answer to either of these (not guessed — actually said it), that's worth a real jump in the score. This is the difference between "one heavy sentence" and "an established, real pattern."

## And the score can go back down, too

If a few messages pass with nothing new and nothing concerning, the score quietly eases back down instead of staying stuck high from one earlier heavy message. A conversation that had a rough patch but then settles down isn't treated as permanently serious.

<!--DIAGRAM_SCOREBOARD-->

# A Real Worked Example

Here's an actual test conversation we ran, showing exactly how the number moved, message by message:

| Turn | What was said | Score after | Tier |
|---|---|---|---|
| 1 | "I've been feeling a bit stressed about work lately" | 35 | 1 |
| 2 | "It's been going on for a few weeks now, I keep procrastinating" | 60 | 2 |
| 3 | "It's affecting my performance at work, I missed a deadline" | 95 | 2 |
| 4 | "I also feel really unmotivated to do anything after work" | 100 | 2 |
| 5 | "I've stopped hanging out with friends, I just don't feel like it" | 100 | 2 |

Notice the score reaches a full 100 out of 100 by turn 4 — and the Tier still correctly stays at **2**, never 3. This is a real, ongoing concern worth a professional's attention, but it is not a crisis, and the system now never confuses the two, regardless of how high the number gets.

Notice what happened: turn 1 alone only reached Tier 1 — a single stressed-sounding sentence isn't treated as an emergency. It took **turn 2 confirming "a few weeks"** and **turn 3 confirming it's hurting their work** before the score genuinely climbed into serious territory. That's the system doing exactly what it's meant to do — building a real picture over the conversation, not reacting to one sentence.

We also tested what happens when the conversation turns ordinary again:

| Turn | What was said | Score after |
|---|---|---|
| 6 | (continuing, nothing new) | 95 |
| 7 | "the weather has been nice this week" | 90 |
| 8 | "i went for a walk earlier" | 85 |

The score eased back down on its own once the conversation stopped adding anything new — exactly as intended.

# The Most Important Rule: A High Score Is Not Permission To Push Toward Booking

This is the single most important design decision in the whole system, and it came directly out of a concern you raised: **hitting a high score should never mean the bot immediately tries to redirect someone toward booking a consultation.**

A high score just means: *pay closer attention, ask the right questions, keep listening.* Redirecting someone toward booking an appointment is a much bigger action than sending one more reply — so it needs its own, separate, stricter confirmation before it happens.

## The Confidence Gate

Before the bot will ever gently suggest booking a consultation, **all of these have to be true at once:**

1. The score is genuinely in Tier 2 (not just one spike) — remember, Tier 2 is as high as the score can ever go.
2. The person has actually told us **how long** this has been going on.
3. The person has actually told us it's **affecting their daily life**.
4. **Multiple distinct** concerns have shown up across the conversation — not the same one worry repeated.

Only once **all four** are true does the bot say anything like a suggestion to book. Here's the real reply our test produced, once — and only once — the gate actually cleared:

> *"It might help to talk with a mental health professional who can support you through this in a safe, understanding space. Would you like help finding someone to speak with, or help with how to go about booking an appointment?"*

And here's what happens **before** the gate clears — the bot still responds warmly, but gently keeps gathering the missing piece instead of pushing toward booking:

> *"It sounds like you've been carrying this for a little while now, and that can feel really heavy. When something lingers for weeks, it often starts to feel bigger than just 'not getting things done.'"* — followed by a gentle, natural question about how it's affecting daily life, never a suggestion to book.

<!--DIAGRAM_GATE-->

# Danger Messages Never Wait For Any of This

This is worth saying clearly and separately: **the score system has nothing to do with how the bot handles real danger** (suicidal thoughts, self-harm, and similar). That is handled by a completely separate, always-on safety check that fires **instantly**, on every single message, regardless of what the running score currently says.

A person's very first message could be the most serious thing they say in the whole conversation, and the safety response still fires immediately — it never waits for "enough evidence" to build up. The scoring system described in this document is only for the slower, gentler picture of "how serious is this pattern turning out to be" for everything **short of** that — it is never a substitute for instant danger detection, and it never delays it.

# A Bug We Caught While Testing — Being Transparent

The first time we tested this live, something went wrong: a single message accidentally matched **nine different signs at once** (a known noisiness issue in how matching works — one sentence can sometimes brush up against many signs in the list simultaneously). Because we were adding up points per sign with no limit, one message shot the score straight to 100 instantly — completely defeating the point of "build up gradually."

We caught this immediately during testing, and fixed it by putting a **ceiling on how much any single message can move the score**, no matter how many things it happens to match. After the fix, we re-ran the same test and confirmed the score genuinely climbs step by step across a conversation, the way it's supposed to (see the worked example above, which is the *post-fix* result).

We're telling you about this not because it's flattering, but because it's exactly the kind of thing that needs to be caught before this goes live — and it was.

# A Second, More Important Mistake — Caught by Reading a Real Example

The first working version of this system *did* let the score climb into a bracket literally called "Tier 3" at 70 and above — the worked example earlier in this document originally showed exactly that, with the sustained work-stress conversation landing on "Tier 3" once it hit a high score.

That is a real mistake, not a cosmetic one, and it was caught by reading that exact example against real-world judgment: **an ordinary, if genuinely concerning, conversation about work stress and withdrawing from friends is not a crisis — and it must never be labeled the same thing as one, no matter how high the number climbs.** "Tier 3" has to mean exactly one thing, always: an actual self-harm or crisis disclosure, handled by the separate, instant safety check described above.

**Fixed:** the score-based system can now only ever produce Tier 1 or Tier 2 — the code has no path to a 3 at all anymore. Tier 3 exists only as the name of the crisis safety check, completely outside this scoring system. Re-tested afterward: the same work-stress conversation now correctly reaches a full 100/100 score while staying at Tier 2 the whole way (see the corrected worked example above), and a genuinely dangerous message in a separate test still triggered the real crisis response instantly — completely unrelated to what the running score happened to be at the time.

# From "Counting Keywords" to "Really Understanding the Conversation" — Now Built

The very first version of this system checked for "how long" and "is it affecting daily life" using a simple keyword search — does the message contain a phrase like *"for weeks"* or *"affecting my work"*. That worked for the exact examples we first tested, but it was genuinely fragile: it would miss someone who phrases it differently, and it had no sense of context.

Following the direction you gave — that the system should try to **understand how the person is actually responding**, not just match fixed phrases — this has now been rebuilt, not just planned:

- Instead of a keyword search, the system now **asks the AI directly**, with a small, separate, cheap question (not the main reply): *"has the user actually told us how long this has been going on? Has the user told us it's affecting their life? Point to the exact part that shows it."*
- Because it has to point to the actual evidence, this stays checkable — it's not just an unexplained AI opinion, it's a grounded read of what was really said, with the receipts.
- **Tested with phrasing the old keyword version would have completely missed**: *"honestly this has been my reality for around a month now"* correctly registered as confirming duration, and *"it's really starting to get in the way of how i do at my job"* correctly registered as confirming impact — neither contains any of the old fixed phrases, and both were still caught correctly.
- This extra step only runs on turns where it's still actually needed — once both duration and impact are confirmed, the system stops asking, so there's no ongoing cost for the rest of the conversation. Measured in testing: roughly a quarter-second added only on the turns that still need it, nothing extra afterward.
- If this check ever fails or comes back unclear, it simply treats that turn as "not yet confirmed" rather than guessing — worst case, it asks again next turn, it never wrongly assumes something was said that wasn't.

Importantly: **this upgrade only touches the slower-building score system.** The instant danger-detection safety check described earlier stays exactly as rule-based and unconditional as it is today — that boundary does not move, no matter how "smart" the rest of the system gets.

**Still an honest limitation:** this only reads the current message, not the full conversation history further back — so it can't yet catch something the person confirmed several messages ago and never repeated. Recognising a fully **resolved past struggle** ("I used to feel that way, but I've been doing much better") as different from an active one is also not yet part of this check. Both are natural next steps once more conversation history is wired into the system generally.

# What's Still Not Finished — Being Upfront

Two honest gaps remain, and what it takes to close each one:

**1. The self-care exercises this system is meant to suggest at Tier 1 and 2 aren't wired in yet.**
This needs real content from your side — a list like "for low motivation, suggest this exercise; for anxiety, suggest this breathing technique." Once that content exists in the same format as everything else already shared, it plugs directly into the search system already built for this — no new engineering required, just the real content to search through.

**2. All the actual numbers — how many points each severity level is worth, exactly where the Tier 2 line falls — are our best engineering starting guess, not something a clinician has reviewed yet.**
Getting these right needs a real calibration exercise: run a batch of real (or realistic sample) conversations through the system, separately ask a clinician what tier they'd have called each one, and adjust the numbers wherever the two disagree — repeated until the system's answers reliably match real clinical judgment.

# One-Page Recap

- A hidden score (0–100) moves gradually with every message — never decided from one sentence.
- It goes up for genuinely new, distinct concerns, weighted by real doctor-assigned severity.
- It goes up more once "how long" and "how it's affecting them" are actually confirmed by the person.
- It eases back down on quiet, ordinary turns.
- The score decides the **Tier — but only ever Tier 1 or Tier 2**, never Tier 3. A high Tier 2 only means "listen more carefully," never "push toward booking."
- Booking is only ever suggested once a separate, stricter **confidence gate** clears — multiple real concerns, both key questions answered, not just one strong sentence.
- **Tier 3 means crisis, full stop** — it belongs only to the separate, instant safety check, and the score has no way to reach it. This was a real mistake in the first version, caught and fixed.
- Real danger messages are handled completely separately, instantly, and never wait for any of this.
- "How long" and "how it's affecting them" are now genuinely read and confirmed by the AI, not just keyword-matched — built and tested, not just planned.
- Two honest gaps remain open, clearly listed above, with a clear path to closing each one.
