# Mindfully Yours — Client Knowledge Base: Content Map & Ingestion Approach (v2 — full Phase I received)

Companion reference to `APPROACH.md`, `CLAUDE.md`, `LATENCY.md`, `INGESTION.md`, `LIVEKIT.md`, `DATA_PROTECTION_SECURITY.md`, `CONVERSATION_REASONING_FLOW.md`, and `END_TO_END_RAG_APPROACH.md`. This supersedes the first version of this file. The client has now sent essentially the complete Phase I knowledge base -- 8 real files, not 4 -- and the biggest blocker from the first version (the undefined signal-code legend) is resolved. One smaller gap remains, noted in Section 5.

---

## 1. All eight documents received, and what each one is for

| Document | What it is | Which part of the architecture it serves |
|---|---|---|
| **Clinical Markers Reference Table** | 10 observational categories (Speech, Safety, Emotional State, etc.) | Silent triage -- always-present prompt content |
| **Convo_Samples.pdf** | Example conversations showing tone and pacing | Persona/prompt engineering -- few-shot + eval set |
| **Knowledge_Base_Directory** | Table of contents for the whole KB | Internal build-planning only, never reaches the AI |
| **Kb_Phase_I_A1.csv -- Signal Legend** | 285 entries: `SIG-001`-`SIG-285`, each with a clinical concept and 5-10 real example phrasings | **Resolves the code-legend blocker.** This is what every `SIG:` reference throughout the routing tables actually means |
| **Kb_Phase_I_A2.csv -- Physical/Emotional Symptom Map** | `PHYS-001` onward -- physical complaints (disorganized speech, psychomotor retardation, conversion symptoms) mapped to their likely emotional/mental root | Resolves every `PHYS:` reference in the routing tables |
| **Kb_Phase_I_9.csv -- Sufficiency Threshold** | Tier 1/2/3 definitions per clinical category, with minimum/must-have signals, confidence thresholds, probing guidance, exit triggers | The "how much evidence before routing" logic |
| **Kb_Phase_I_C11.csv -- Routing Rules** | Explicit `RULE-001` onward, plain-English if/then logic: exact signal combination -> exact tier | **This is the deterministic rules table**, already written by the client in almost exactly the structure this project's architecture called for |
| **Kb_Phase_I_7.csv -- Red Flags** | `RF-001` onward: direct and disguised trigger phrases, clinical meaning, immediate action, and the *exact* bot script to use verbatim | Feeds the safety interlock directly -- this is the highest-priority content in the whole KB |
| **Kb_Phase_I_17.csv -- Fallback & Safety Net** | What to do when signals are vague, contradictory, or the user disengages -- each with a scripted response and escalation path | Handles the "not enough information, and it's not getting clearer" case that pure tier logic doesn't cover |

---

## 2. How the pieces fit together -- the real picture, not the placeholder one

Previously, `Kb_Phase_I_9.csv`'s tier logic pointed at `SIG`/`PHYS`/`EM` codes with no definition anywhere. Now the chain is complete for `SIG` and `PHYS`:

```
User says something
      |
Matched against real phrasing examples in A1 (SIG codes) and A2 (PHYS codes)
      |
Identified signals checked against Kb_Phase_I_C11's explicit RULE-XXX logic
      |
Rule fires -> exact tier assigned, with a stated clinical reason
      |
If a Red Flag (Kb_Phase_I_7) is present at any point -> Tier 3 immediately, skip everything else
      |
If signals are present but insufficient, contradictory, or the user disengages ->
Kb_Phase_I_17's fallback logic takes over, with its own scripted response
```

This is a real, traceable pipeline now -- not a design with a placeholder in the middle.

---

## 3. Storage structure, updated with real field names

### 3a. The Signal & Symptom Legend -- a lookup table, not embedded content

From `A1` and `A2`:
```
signal_id        e.g. "SIG-002", "PHYS-003"
clinical_concept e.g. "Suicidal ideation (passive)", "Psychomotor retardation"
example_phrasings   the 5-10 real quotes -- genuinely useful as embedding material,
                     since this is exactly the kind of natural, varied phrasing an
                     embedding-based signal detector (per the one-LLM-call fix) needs
                     to match against indirect or non-obvious user language
```
**This table is the one piece of the legend that's worth embedding**, specifically because its whole purpose is matching varied real-world phrasing to a concept -- that's a semantic-similarity problem, not a lookup.

### 3b. The Routing Rules -- the deterministic table, exactly as designed

From `Kb_Phase_I_C11.csv`:
```
rule_id            e.g. "RULE-001"
trigger_condition  plain-English, e.g. "For Major Depressive Disorder (SIG002-003), no other signal required"
route_to           e.g. "Tier 3"
override_reason    clinical justification
trajectory_factor  how worsening/stable/improving affects the rule
priority           **a real, separate field in the source data (1, 2, or 3) -- does NOT follow rule_id order.** e.g. RULE-004 carries priority 1 while RULE-002 and RULE-003 carry priority 2, so RULE-004 must be checked first despite its higher number
```
This is a direct lookup, but the evaluation order must come from the actual `Priority` column (1 → 2 → 3), not from `rule_id` sequence -- the two do not match in the real data.

### 3c. Red Flags -- the highest-priority, always-checked-first table

From `Kb_Phase_I_7.csv`:
```
flag_id              e.g. "RF-001"
trigger_phrases       5+ examples, explicitly including disguised/indirect versions
clinical_meaning
immediate_action      e.g. "Tier 3 + SOS flag"
bot_script            exact wording, to be used verbatim -- not paraphrased by the LLM
escalation_target     e.g. "Psychiatrist + crisis review"
```
**Critical detail**: the client explicitly wrote these scripts to be used *verbatim*, not as guidance for the LLM to phrase in its own words. This is a meaningful constraint worth respecting exactly -- per `CLAUDE.md`'s safety-interlock principle, red-flag responses shouldn't be left to model generation at all.

### 3d. Fallback & Safety Net -- scripted responses for the "not clear yet" case

From `Kb_Phase_I_17.csv`, organized into three sections:
- **Section A -- Insufficient signal**: vague disclosure, high topic diversity, low model confidence
- **Section B -- Contradictory signals**: stated wellbeing contradicts emotional content, ambiguous safety situations, mixed practical/mental-health concerns
- **Section C -- User disengagement**: one-word answers, mid-disclosure abandonment, repeated session restarts without progress

Each row has: `scenario_type`, `trigger_condition`, `fallback_action`, `bot_script`, `escalation_path`, `clinical_reasoning`. Same principle as Red Flags -- the bot scripts here are meant to be used close to verbatim, not loosely paraphrased.

---

## 4. What this changes about the conversation flow described in `CONVERSATION_REASONING_FLOW.md`

Step 4 ("sufficiency check") in that file described checking against a rules table with placeholder logic. **That table now has real content** -- `Kb_Phase_I_C11`'s `RULE-XXX` entries -- and it should be loaded exactly as authored, **evaluated by its real `Priority` field (1, then 2, then 3) -- not by `RULE-ID` number.** The two orderings genuinely differ in the real data (e.g. `RULE-004` is priority 1, `RULE-002` is priority 2), so building this on ID order would silently apply rules in the wrong sequence. One rule (`Rule-025`) has no priority or route_to set at all and should be excluded until the client fills it in.

Step 3 (the safety interlock) should now be built directly from `Kb_Phase_I_7`'s Red Flag list -- both the direct and disguised trigger phrases matter equally, since the client explicitly designed this to catch indirect language, not just obvious statements.

A genuinely new case, not previously in the flow: **what happens when there's *some* signal but not enough to route confidently, and it's staying that way** (vague, contradictory, or the user is disengaging). This isn't a "keep probing" case -- `Kb_Phase_I_17` shows the client has a distinct, third response type for it, with its own scripted language. Worth adding as an explicit branch alongside "not enough yet" and "enough, route now."

---

## 5. What's still actually missing -- down to one item

1. **`EM` codes are confirmed missing.** The full 285-row signal legend (`A1`) contains only `SIG` codes -- no `EM` entries anywhere in it. Every `EM:` reference throughout `Kb_Phase_I_9` and `Kb_Phase_I_C11` still points at an undefined code. This needs its own legend file from the client, structured the same way `A1` and `A2` are (an ID, a concept, and example phrasings).
2. Whether Convo_Samples.pdf is a close script or a style guide -- still open, unrelated to this update.
3. Confirm there isn't a "Guardrail questions" component distinct from what's now covered by `Kb_Phase_I_17` -- the Directory listed it separately, but its content may already be folded into the Fallback & Safety Net sheet. Worth a quick confirmation rather than assuming.

---

## 6. What NOT to do -- updated

- Don't paraphrase Red Flag or Fallback bot scripts through the LLM -- use them close to verbatim, per how the client explicitly wrote them.
- Don't treat the Routing Rules (`C11`) as guidance for the LLM to interpret -- they're deterministic, priority-ordered logic, evaluated the same way every time.
- Don't build the safety interlock's phrase-matching only on direct language -- `Kb_Phase_I_7`'s disguised/indirect examples are there specifically because real users don't always say things plainly.
- Don't proceed to build the EM-dependent parts of the routing/sufficiency logic until that legend arrives -- this is now the only remaining hard blocker.
- Don't assume the embedding-based signal pre-filter (from the one-LLM-call fix) needs to be built from scratch -- `A1`'s and `A2`'s example phrasings are exactly the training/matching material it needs.

---

*Companion file to `APPROACH.md`, `CLAUDE.md`, `LATENCY.md`, `INGESTION.md`, `LIVEKIT.md`, `DATA_PROTECTION_SECURITY.md`, `CONVERSATION_REASONING_FLOW.md`, and `END_TO_END_RAG_APPROACH.md`. Supersedes the first version of this file. Update again once the EM-code legend and the Guardrail-questions confirmation arrive.*
