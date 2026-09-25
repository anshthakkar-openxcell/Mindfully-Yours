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
    retrieved_guidance: str | None  # fetched-by-ID probing guidance, or searched self-care content
    recent_turns: list[str]  # already trimmed to MAX_RECENT_TURNS by the caller
    running_summary: str | None
    few_shot_examples: list[str]  # curated subset of Convo_Samples -- see 17_PERSONA_AND_CONVERSATION_STYLE.md


def build_prompt(inputs: PromptInputs) -> str:
    """
    Pure function -- no I/O, easy to unit test against fixed inputs. Keep it that way; any provider
    call belongs in app.pipeline.orchestrator, not here.
    """
    sections = [inputs.persona, render_for_prompt()]

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

    return "\n\n".join(sections)
