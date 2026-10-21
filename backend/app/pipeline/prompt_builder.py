"""
Prompt assembly -- pipeline step 8 of documnets/understanding/04_CONVERSATION_PIPELINE.md.

Assembles: persona + retrieved passages (fetched by ID or searched, per app.pipeline.retrieval)
+ trimmed recent history + running summary -- NEVER the full transcript. Per
documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §7: smaller prompts process faster in
addition to costing less; keep the persona/system prompt lean, since a bloated static prompt adds
fixed latency to every single call.

The LLM's job, once this prompt is assembled, is composing phrasing ONLY -- never deciding safety
or supplying facts not already retrieved. See app.providers.base.LLMProvider's docstring.
"""

from dataclasses import dataclass

from app.safety.clinical_markers import render_for_prompt

MAX_RECENT_TURNS = 6  # trimmed window, not the full transcript -- tune against real eval data


@dataclass
class PromptInputs:
    persona: str
    user_message: str  # the CURRENT turn's text -- see build_prompt's docstring for why this exists
    retrieved_guidance: str | None  # fetched-by-ID probing guidance, or searched self-care content
    recent_turns: list[str]  # already trimmed to MAX_RECENT_TURNS by the caller
    running_summary: str | None
    few_shot_examples: list[str]  # curated subset of Convo_Samples -- see 17_PERSONA_AND_CONVERSATION_STYLE.md
    # An explicit language line (app.pipeline.language_hint.language_instruction). Optional so existing
    # callers are unaffected; when given it replaces the generic "decide from their words" paragraph.
    language_instruction: str | None = None


def build_prompt(inputs: PromptInputs) -> str:
    """
    Pure function -- no I/O, easy to unit test against fixed inputs. Keep it that way; any provider
    call belongs in app.pipeline.orchestrator, not here.

    FIXED BUG (found 2026-09-28, not caught by review -- only surfaced by actually running the
    pipeline and inspecting the literal prompt string sent to the LLM): `user_message` did not
    exist as a field here at all, and nothing else in this function's inputs ever carried the
    current turn's text either. Every conversation was generating a reply to a prompt that never
    said what the user actually typed -- persona + the static Clinical Markers checklist only. This
    is why every LLM response looked like a generic opening line regardless of input. `user_message`
    is placed LAST, after all context, so it reads as "the specific thing to respond to now."
    """
    sections = [
        inputs.persona,
        # Per CLAUDE.md §5: "The LLM always replies in whatever language the user used in that
        # turn... let the model's own instruction-following handle it" -- made explicit here rather
        # than left implicit, since the rest of this prompt (persona, clinical markers, few-shot
        # examples) is entirely in English and could otherwise bias a reply towards English even
        # when the user just switched to Hindi or Hinglish mid-conversation.
        "Always reply in the same language the user just used, matching their script too -- if "
        "they wrote in Hindi (Devanagari or Romanized/Hinglish), reply in Hindi or Hinglish; if "
        "English, reply in English. Decide this from their actual words below, not from the "
        "language of these instructions. If they mix languages in one message, you may reply with "
        "a natural mix too -- don't force a single language where a bilingual speaker wouldn't.",
        render_for_prompt(),
    ]

    if inputs.language_instruction:
        # Explicit beats inferred: put it right after the persona so it outranks the generic paragraph.
        sections.insert(1, inputs.language_instruction)

    if inputs.few_shot_examples:
        sections.append("Example tone (for style only, not to copy verbatim):")
        sections.extend(inputs.few_shot_examples)

    if inputs.running_summary:
        sections.append(f"Conversation summary so far: {inputs.running_summary}")

    if inputs.recent_turns:
        sections.append("Recent turns:")
        sections.extend(inputs.recent_turns[-MAX_RECENT_TURNS:])

    if inputs.retrieved_guidance:
        sections.append(f"Grounding material (compose your reply from this, don't invent beyond it):\n{inputs.retrieved_guidance}")

    sections.append(f"The user just said: {inputs.user_message}\n\nRespond directly to this now.")

    return "\n\n".join(sections)


def build_rephrase_prompt(
    *,
    persona: str,
    user_message: str,
    examples: list[tuple[str, str]],
    recent_turns: list[str],
    language_instruction: str | None = None,
) -> str:
    """
    The prompt for a PARTIAL therapist match (doc 32): a deliberately SMALL prompt (no clinical
    markers table) that shows the LLM the closest therapist examples -- each as "someone said X,
    the therapist replied Y", best first -- so it gets the full idea of how the team handles this
    kind of situation, and asks it to write ONE reply for this person using only those ideas.
    `examples` is a list of (what_the_person_said, therapist_reply), best match first.
    app.pipeline.guardrail.check_rephrase_faithful enforces the "add nothing" rule on the output; if
    it fails, the best therapist reply is served as written instead.
    """
    sections = [
        persona,
        language_instruction or "Always reply in the same language the user just used.",
    ]
    if recent_turns:
        sections.append("Recent turns:")
        sections.extend(recent_turns[-MAX_RECENT_TURNS:])
    lines = ["Real examples from our therapist team, closest first:"]
    for n, (said, reply) in enumerate(examples, start=1):
        lines.append(f'{n}. When someone said: "{said}"\n   the therapist replied: "{reply}"')
    sections.append("\n".join(lines))
    sections.append(
        "Write ONE reply to the user's message below, in the same warm style, using ONLY the ideas, "
        "wording and questions that already appear in the therapist replies above -- reword them just "
        "enough to fit what this person actually said. Keep it about as short as the therapist replies. "
        "Do NOT add advice, suggestions, questions, facts, numbers or links that are not in those replies. "
        "Do not mention the therapists or these examples. Output only the final reply."
    )
    if language_instruction:
        # Repeated LAST, right before the message: the examples above are English, and the model copied
        # their language when the instruction only appeared at the top.
        sections.append(f"IMPORTANT -- language of your reply: {language_instruction}")
    sections.append(f"The user just said: {user_message}")
    return "\n\n".join(sections)
