# 23. Database Tables, Explained Simply

One-page reference: every table in the database, what it stores, why it exists, and when it
actually gets used. Written for a non-technical read — no code, just plain language.

There are **19 tables** in total. They fall into 6 natural groups, by job, not by when they were
built.

## Quick-look summary

| Table | What it's for | Ever vector-searched? |
|---|---|---|
| kb_red_flags | Danger phrases + pre-written safety replies | **Yes — working today** |
| kb_content_chunks | Self-help tools to recommend | **Yes — working today** |
| kb_signals | Fine-grained clinical warning signs | Designed for it, not wired up yet |
| kb_symptoms | Body/emotion symptoms → real cause | Designed for it, not wired up yet |
| kb_sufficiency_patterns | "Do we know enough yet?" thresholds | Designed for it, not wired up yet |
| kb_scenarios | Real-life situation matching | Designed for it, not wired up yet |
| kb_emotion_phrases | Which emotion a message expresses | Designed for it, not wired up yet |
| kb_layer_content | How deep to go in conversation | Designed for it, not wired up yet |
| kb_clarification_phrases | "I'm not sure, let me ask" phrases | Designed for it, not wired up yet |
| kb_career_lookup | Career name → field & stream | Designed for it, not wired up yet |
| kb_tier_question_bank | Real follow-up questions | Designed for it, not wired up yet |
| kb_anxiety_situations | Anxiety topic checklist | No — plain lookup |
| kb_fallback_scenarios | What to do when things go off-script | No — plain lookup |
| kb_routing_rules | "If X, always route to Y" | No — plain lookup |
| kb_guardrail_rules | Parenting-concern urgency | No — plain lookup |
| kb_versions | Tracks knowledge-base updates | No — system bookkeeping |
| prompt_config | The AI's fixed instructions | No — system bookkeeping |
| sessions | One row per conversation | No — system bookkeeping |
| turn_audit_log | One row per message, for audits | No — system bookkeeping |

"Designed for it, not wired up yet" means: the data is loaded and each row already has its
numeric fingerprint saved — the table is ready. What's still missing is the search code on the
other end that would actually query it during a live conversation. Only two tables have that
search code written today.

---

## Group 1 — Safety (checked on every single message, no exceptions)

**kb_red_flags** — 31 rows
- **Stores:** a danger-sign ID, ~5 example phrases of what someone in that danger might say, what
  it clinically means, what to do immediately, and the exact pre-written reply to send.
- **Why:** so the AI never has to improvise when someone's safety is at risk — it just matches and
  reads a pre-approved script, word for word.
- **Used:** every single message, instantly, before anything else in the pipeline runs.

**kb_signals** — 285 rows
- **Stores:** a clinical concept (e.g. "hopelessness"), how severe it typically is (1–3), whether
  it counts as a red flag, and example phrasings.
- **Why:** the AI's early-warning system — a much finer-grained read of "what's going on" than the
  31 red flags alone.
- **Used:** meant to run on every message to build a running picture of the user's state. (Built,
  but the live query isn't wired up yet — see summary table.)

**kb_symptoms** — 154 rows
- **Stores:** physical/emotional symptoms (e.g. "chest tightness"), how people typically describe
  them, and which `kb_signals` rows they usually point back to.
- **Why:** users often describe a body feeling, not a clinical term — this bridges "my chest feels
  tight" to the real underlying cause.
- **Used:** alongside kb_signals, same not-yet-wired status.

**kb_fallback_scenarios**
- **Stores:** what to do when a conversation isn't going normally — user gives too little
  information, contradicts themselves, goes quiet, or belongs to a special group (e.g. a minor).
- **Why:** a script for "this isn't a normal exchange," so the AI doesn't freeze or guess.
- **Used:** whenever the conversation flow breaks the usual pattern.

## Group 2 — Understanding what the user means

**kb_scenarios**
- **Stores:** a category, a topic, a short scenario description, and an example phrase someone
  might actually say.
- **Why:** matches vague or indirect language to a known real-life situation (relationship
  trouble, career stress, etc.).
- **Used:** to classify what kind of situation the user is describing.

**kb_emotion_phrases**
- **Stores:** an emotion name (Overwhelm, Grief, Anxiety, ...) and one real example sentence per
  row.
- **Why:** tells the AI what emotion sits behind a message, even when the wording is indirect.
- **Used:** reading the emotional tone of a message.

**kb_layer_content**
- **Stores:** which "depth level" (Layer I–IV) a question or statement belongs to, and its text.
- **Why:** conversations go deeper in stages — this tracks how deep this exchange should go,
  separate from how clinically severe it is.
- **Used:** deciding how probing versus surface-level the next question should be.

**kb_clarification_phrases**
- **Stores:** a category and a ready-made phrase to use when the AI genuinely isn't sure what the
  user means.
- **Why:** gives the AI a safe way to ask for clarification instead of quietly guessing.
- **Used:** any low-confidence moment, at any point in the conversation.

**kb_anxiety_situations**
- **Stores:** a broad anxiety situation (e.g. "Public speaking") and its related sub-topics, as one
  block of text.
- **Why:** a coverage checklist, so the team can confirm anxiety topics are represented — not built
  for fine-grained matching.
- **Used:** as a reference list, not a live search target.

## Group 3 — Recommending something to do

**kb_content_chunks**
- **Stores:** a piece of real help content (a DBT skill, a self-care tool), which tier it applies
  to, and its full text.
- **Why:** this is the one table whose content genuinely gets handed back to a struggling user as
  a suggestion.
- **Used:** Tier 1 conversations, whenever the AI offers a coping tool.

**kb_sufficiency_patterns**
- **Stores:** a clinical pattern name, which tier (1–3) it maps to, and how much evidence counts as
  "enough" to make that call.
- **Why:** stops the AI from deciding how serious something is on a hunch — it's a checklist of
  what counts as sufficient evidence.
- **Used:** every message, to decide whether enough is known yet to assign a tier.

## Group 4 — Career-specific lookups

**kb_career_lookup**
- **Stores:** a career name, its broader field, and its academic stream.
- **Why:** a precise reference table so career-planning answers are factual, never invented.
- **Used:** whenever a user names or asks about a specific career.

**kb_tier_question_bank**
- **Stores:** real follow-up questions (open-ended or multiple-choice), tied to a scenario or
  career topic.
- **Why:** gives the AI real, pre-written questions to ask next, instead of making its own up.
- **Used:** during scenario-specific conversations, to choose the next question.

## Group 5 — Pure rules (never searched — just looked up, like a checklist)

**kb_routing_rules**
- **Stores:** a trigger condition and where to route the conversation, in a fixed priority order.
- **Why:** deterministic — "if X happens, always do Y," no AI judgment needed or wanted.
- **Used:** deciding where a conversation should go next.

**kb_guardrail_rules**
- **Stores:** parenting/child-related concern categories and how urgently each one needs a human
  referral.
- **Why:** same idea as routing rules, scoped specifically to parenting topics.
- **Used:** checked directly in code whenever a parenting concern comes up.

## Group 6 — System bookkeeping (not conversation content at all)

**kb_versions**
- **Stores:** a label and a status ("building" / "live" / "rolled_back") for each batch of
  knowledge-base data that gets loaded.
- **Why:** lets a knowledge-base update be tested before it goes live, and safely rolled back if
  something's wrong with it.
- **Used:** every time the knowledge base is updated.

**prompt_config**
- **Stores:** the AI's fixed persona and instruction text, versioned, with a clinical sign-off
  record.
- **Why:** the prompt is never editable by any user or admin on the fly — this is the one governed,
  auditable place it's allowed to live.
- **Used:** loaded once at the start of every conversation, into every prompt sent to the AI.

**sessions**
- **Stores:** one row per conversation — its mode (voice/text/avatar), language, current tier, a
  running summary, and a mood tag.
- **Why:** remembers who the user is and what's happened so far, across an entire conversation (and
  into the next one).
- **Used:** from the start to the end of every conversation.

**turn_audit_log**
- **Stores:** one row per message — what was retrieved, what matched, what tier was assigned, and
  how long each step took.
- **Why:** a legally required record, so anyone can later check exactly why the AI said what it
  said.
- **Used:** written silently after every message, never slowing the user down while it happens.
