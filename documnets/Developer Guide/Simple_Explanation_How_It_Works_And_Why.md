# How the reply system works, and why this is the best approach

## The goal

The product is valuable because of the **therapists' experience**. So when a user writes something, the reply should come from the therapists' own conversations whenever one of them fits. The AI language model (the LLM) is not the author. It only helps with wording when the match is close but not exact, and it answers on its own only when nothing in the library fits.

## How it works, step by step

1. **The user sends a message.** It is typed, or spoken and turned into text.

2. **We turn the message into a "meaning vector".** This is a long list of numbers that captures what the message means, not which words it uses. Two messages that mean the same thing get similar numbers even if the words differ. We do this once per message and reuse it for every search below.

3. **The safety check runs first, always.** The vector is compared with the danger patterns your clinicians wrote (the red flags). If one matches, the user gets the approved script for that flag, word for word, and the process stops. The LLM is never involved. If the safety check itself fails, the user gets a safe "let me connect you with someone" instead of silence.

4. **At the same time, we search the therapist conversations.** Each stored therapist conversation (what the person said, and what the therapist replied) also has a meaning vector. The database finds the closest one and gives it a score from 0 to 1, where 1 means identical meaning. The text and the vector live in the same PostgreSQL database, so one query returns the nearest match and its reply together. This search runs in the background while the safety check runs, so it adds almost no waiting time.

5. **The score decides what happens.**
   - **0.85 or higher (very close):** send the therapist's reply exactly as written. No LLM at all. This is the fastest and safest path.
   - **0.62 to 0.85 (fairly close):** the therapist's idea is right but the wording needs to fit this person. We show the LLM up to 3 close therapist examples and tell it to write one reply using only their ideas and wording, adding no advice, numbers or links. We then check its answer. If it drifts from the therapists' text, we send the therapist's original reply instead. The user never sees a reword that failed the check.
   - **Below 0.62 (not close):** we ask a short therapist-written question such as "Can you tell me a little more?" (once). If nothing else can guide the reply, the LLM writes a short, careful answer, using therapist self-care advice when we have some for that situation, and suggesting a real professional when it is unsure or things sound serious.

6. **The reply is delivered** as text or as speech. The conversation memory is updated, and one log row records which of the paths above produced the reply and which therapist conversation it came from.

**Other languages.** A message in Hindi or Hinglish is translated to English first, so the safety check and the search work on it. Fixed replies come back from a table that was translated in advance, so they are instant. When the LLM writes the reply, it writes directly in the user's language.

**How the library grows.** Therapists write conversations. We load them, automatically hold back anything unsafe or unfinished, and approve the rest. They are used immediately. There is no retraining and no new release.

## Why this is the best approach

1. **It keeps the product's promise.** Therapist expertise is what makes the app different. Replies come from therapist text first, so users get the team's wording, not a generic AI answer.

2. **It is safer for a mental-health app.** An LLM can invent advice that sounds right and is not. Therapist text cannot. So we only let the LLM touch clinical content in a narrow, checked way, and never at all in a crisis.

3. **The LLM does only what it is good at.** Rewording a few given examples is a small, reliable job. "Be a therapist" is a large, risky one. Giving it the real therapist examples also sets the tone far better than a written description of the tone.

4. **Every reply can be explained and fixed.** Each reply is logged with its source and the exact therapist row. If one is wrong, we unapprove that one row and it stops immediately.

5. **It gets faster and cheaper as the library grows.** Every very-close match skips the LLM entirely.

6. **It improves without engineers.** Every question nothing matched is a gap the therapists can fill, and each new conversation helps the next user.

7. **Failures are contained.** Safety is independent of everything else. A reword that fails the check falls back to the original. If the LLM is down, the therapist's reply still goes out.

8. **One database is enough.** The tables and the vector search are the same PostgreSQL, so there is no second system to run, secure or keep in sync.

**Why not the alternatives:**
- *Let the LLM write everything:* it can invent advice, cannot show where a reply came from, and costs time and money every message.
- *Always retrieve, then let the LLM write:* better, but the LLM can still drift from a perfect therapist reply. We keep this only as the last resort.
- *Fine-tune a model on the conversations:* expensive, cannot say which conversation produced a reply, cannot forget a bad one, and needs retraining to improve.
- *Keyword or intent rules:* they miss indirect wording, which is exactly what the red flags depend on.
- *A separate vector database:* adds a system to run with no benefit at this size.

## What it does not do perfectly yet

- **The 0.85 and 0.62 cut-offs are provisional.** They come from spot checks. They need to be set with a sample of messages that therapists mark as "fits" or "does not fit". This matters most, because a wrong "very close" match is worse than an LLM reply.
- **It matches on one message at a time.** A reply that only makes sense in the middle of a conversation can match badly. Matching with context is the planned fix.
- **It depends on how much the therapists have written.** A small library means more "not close" results.
- **Word-for-word replies can feel repetitive** in a long chat.
- **"Approved" means included, not clinically reviewed.** The library also contains some casual companion-style chats that could match a distressed user if the cut-offs are loose.
