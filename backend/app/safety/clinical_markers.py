"""
The Clinical Markers Reference Table -- static, always-present system-prompt content, never
embedded or searched (documnets/understanding/08_SAFETY_INTERLOCK_AND_TRIAGE.md §2). Extracted
verbatim from Clinical_Markers_Reference_Table (1).pdf.

This is real clinical content provided directly by the client as source-of-truth for the product
itself -- per documnets/understanding/12_SECURITY_COMPLIANCE_DPDP.md §7, this is different from
processing such content through a third-party AI coding assistant for a coincidental debugging
task. Do not paste this table (or any other real clinical KB content) into an unrelated tool.

Usage: this constant is the seed content for the `prompt_config` row keyed
'clinical_markers_table' (see app.db.models.kb.PromptConfig) -- the ingestion/admin tooling should
load it once, get clinical sign-off, and mark it live. It must never be exposed on any
general-purpose write API (see PromptConfig's docstring).
"""

from typing import Literal, TypedDict


class ClinicalMarker(TypedDict):
    marker: str
    what_it_means: str
    what_to_look_for: str
    lower_concern_example: str
    higher_concern_example: str
    # Three markers give their higher-concern (and, for Engagement, both) example as a third-person
    # behavioral description rather than a first-person quote -- preserve that distinction, don't
    # force these into a fake quote.
    example_style: Literal["quote", "description"]


CLINICAL_MARKERS: list[ClinicalMarker] = [
    {
        "marker": "Speech",
        "what_it_means": "How the user is communicating during the conversation",
        "what_to_look_for": (
            "Whether the user is communicating clearly and understandably, or whether their "
            "speech/text is unusually fast, very slow, difficult to follow, or difficult to interrupt."
        ),
        "lower_concern_example": "I've been stressed about my exams and I don't know how to manage everything.",
        "higher_concern_example": (
            "The user sends long, extremely rapid responses, jumps between unrelated topics and "
            "is difficult to follow."
        ),
        "example_style": "description",
    },
    {
        "marker": "Safety",
        "what_it_means": "Whether the user or someone else may be in immediate danger",
        "what_to_look_for": (
            "Thoughts of suicide/self-harm, plans or intent to harm themselves or someone else, "
            "recent serious self-harm, or saying they cannot keep themselves safe."
        ),
        "lower_concern_example": "I've been feeling low, but I don't have thoughts of hurting myself.",
        "higher_concern_example": "I have been thinking about killing myself and I have a plan.",
        "example_style": "quote",
    },
    {
        "marker": "Functional Impact",
        "what_it_means": "How much the difficulty is affecting the user's everyday life",
        "what_to_look_for": (
            "Impact on work/college, sleep, eating, relationships, self-care, responsibilities "
            "and usual routines."
        ),
        "lower_concern_example": "I'm anxious, but I'm still attending college and getting my work done.",
        "higher_concern_example": (
            "I've stopped attending classes, I'm barely sleeping and I can't keep up with anything."
        ),
        "example_style": "quote",
    },
    {
        "marker": "Reality Testing",
        "what_it_means": (
            "Whether the user can tell the difference between a thought/feeling and something "
            "that is actually happening"
        ),
        "what_to_look_for": (
            "Whether the user can consider other explanations for an experience or is completely "
            "certain that an unusual belief/experience is objectively happening."
        ),
        "lower_concern_example": (
            "Sometimes I feel like everyone is judging me, but I know it could just be my anxiety."
        ),
        "higher_concern_example": (
            "I know everyone is communicating about me through hidden messages, and there is no "
            "possibility that I'm mistaken."
        ),
        "example_style": "quote",
    },
    {
        "marker": "Emotional State",
        "what_it_means": "What the user is feeling and how strongly they are feeling it",
        "what_to_look_for": (
            "Intensity of emotions, ability to manage them, sudden/extreme changes, feeling "
            "overwhelmed or unable to cope."
        ),
        "lower_concern_example": "I'm upset about the breakup, but I can still manage my day.",
        "higher_concern_example": (
            "My emotions feel completely out of control and I don't know what I'm going to do."
        ),
        "example_style": "quote",
    },
    {
        "marker": "Thought Organisation",
        "what_it_means": "How clearly and logically the user's thoughts are coming across",
        "what_to_look_for": (
            "Whether the user can stay on topic and communicate a connected thought, or whether "
            "responses become very difficult to follow, highly disconnected or extremely scattered."
        ),
        "lower_concern_example": "I'm worried about work because I made a mistake yesterday.",
        "higher_concern_example": (
            "The user moves rapidly between unrelated ideas and their responses no longer form a "
            "clear or understandable sequence."
        ),
        "example_style": "description",
    },
    {
        "marker": "Thought Content",
        "what_it_means": "What kinds of thoughts are taking up the user's attention",
        "what_to_look_for": (
            "Persistent worry, hopelessness, guilt, self-criticism, suspicious thoughts, unusual "
            "beliefs, intrusive thoughts, or thoughts about harming self/others."
        ),
        "lower_concern_example": "I keep worrying that I'll fail my presentation.",
        "higher_concern_example": "There's no point in anything anymore. Everyone would be better off without me.",
        "example_style": "quote",
    },
    {
        "marker": "Sensory Experiences",
        "what_it_means": (
            "Whether the user is experiencing something through their senses that seems unusual "
            "or that others around them do not experience"
        ),
        "what_to_look_for": (
            "Reports of hearing, seeing, feeling or sensing something unusual; how often it "
            "happens; whether the user believes it is actually happening; and whether it affects "
            "their behaviour or safety."
        ),
        "lower_concern_example": "Sometimes when I'm falling asleep, I think I hear someone call my name.",
        "higher_concern_example": (
            "I regularly hear a voice speaking to me when nobody is there, and I follow what it "
            "tells me to do."
        ),
        "example_style": "quote",
    },
    {
        "marker": "Behavioural Changes",
        "what_it_means": "Whether the user's behaviour has noticeably changed from their usual pattern",
        "what_to_look_for": (
            "Increased impulsivity, risky behaviour, aggression, extreme withdrawal, unusual "
            "activity, inability to maintain routines, or significant changes from their normal "
            "behaviour."
        ),
        "lower_concern_example": "I've been staying home more because I've been stressed.",
        "higher_concern_example": (
            "I've barely slept, I've been spending huge amounts of money and doing things I "
            "normally wouldn't do."
        ),
        "example_style": "quote",
    },
    {
        "marker": "Engagement with AI",
        "what_it_means": "Whether the user is able to understand, respond to and participate in the conversation",
        "what_to_look_for": (
            "Whether the user can understand questions, provide relevant answers, reflect on "
            "their situation and engage with the conversation."
        ),
        "lower_concern_example": "User responds appropriately and can discuss their concerns.",
        "higher_concern_example": (
            "User is extremely confused, unable to follow simple questions or unable to "
            "participate meaningfully in the conversation."
        ),
        "example_style": "description",
    },
]


def render_for_prompt() -> str:
    """Render the table as plain text for inclusion in the system prompt. Kept as a pure function
    (no I/O) so prompt-assembly tests can assert on its exact output deterministically."""
    lines = ["Clinical Markers -- observation categories to silently read every turn:\n"]
    for m in CLINICAL_MARKERS:
        lines.append(f"- {m['marker']}: {m['what_it_means']}. Look for: {m['what_to_look_for']}")
    return "\n".join(lines)
