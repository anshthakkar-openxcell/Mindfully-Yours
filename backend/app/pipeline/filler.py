"""
Filler-phrase selection -- masks processing latency naturally, per
documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §4. Extracted verbatim from
Mindfully_Yours_AI_Latency_Filler_Phrases.pdf. Selection is RULE-BASED (match situation + expected
gap length to a category), never an LLM decision, and never embedded/searched.

NEVER surface an implementation-leaking phrase ("I'm processing embeddings", "Searching the vector
database", etc) -- see FORBIDDEN_PHRASES below and the design principles in the docstring on
select_filler().
"""

import random
from enum import Enum


class FillerSituation(str, Enum):
    VERY_SHORT_DELAY = "very_short_delay"
    THINKING = "thinking"
    LISTENING = "listening"
    EMOTIONAL = "emotional"
    INFORMATION_LOOKUP = "information_lookup"
    LONGER_ANSWER = "longer_answer"
    UNCLEAR_INPUT = "unclear_input"
    LONGER_LATENCY = "longer_latency"


# Representative subset per category -- see the source PDF for the full lists (14/12/12/12/10/10/8/7
# phrases respectively across the English categories). Extend from the source before shipping;
# these are enough to exercise the selection logic end-to-end today.
_ENGLISH_PHRASES: dict[FillerSituation, list[str]] = {
    FillerSituation.VERY_SHORT_DELAY: ["Hmm…", "Okay…", "Right…", "I see…", "Got it…"],
    FillerSituation.THINKING: [
        "Hmm, let me think about that.",
        "Let me take a moment with that.",
        "Give me a moment to put that together.",
    ],
    FillerSituation.LISTENING: ["I hear you.", "I'm with you.", "I'm listening.", "I understand."],
    FillerSituation.EMOTIONAL: [
        "Hmm… I hear you.",
        "Yeah… that sounds like a lot.",
        "Let's take this one step at a time.",
        "You don't have to rush through this.",
    ],
    FillerSituation.INFORMATION_LOOKUP: [
        "Let me check that for you.",
        "Let me look into that.",
        "Give me a moment while I check.",
    ],
    FillerSituation.LONGER_ANSWER: [
        "Okay, there's a little to unpack here.",
        "Let's break this down together.",
        "There are a few ways we can look at this.",
    ],
    FillerSituation.UNCLEAR_INPUT: [
        "Hmm, let me make sure I understood you.",
        "Just so I'm following you correctly…",
        "Could you tell me a little more about that?",
    ],
    FillerSituation.LONGER_LATENCY: [
        "Give me just a moment while I think about that.",
        "I want to take a moment and give you a thoughtful answer.",
        "Let me take a little time to think this through.",
    ],
}

_HINDI_PHRASES = [
    "Hmm… ek minute.",
    "Haan, samajh raha hoon.",
    "Achha… ek pal.",
    "Theek hai, ek pal.",
]

_HINGLISH_PHRASES = [
    "Haan, I get what you mean.",
    "Okay, ek minute, let me think.",
    "Thoda sochte hain.",
]

FORBIDDEN_PHRASES = [
    "I'm processing embeddings",
    "Searching the vector database",
    "Retrieving chunks",
    "Running the RAG pipeline",
    "The LLM is generating a response",
]


def select_filler(situation: FillerSituation, *, language: str = "en") -> str | None:
    """
    Rule-based filler selection. `language` follows the current turn's language ('en' | 'hi' |
    'hi-en' for Hinglish), per documnets/understanding/13_LANGUAGE_PHASING.md -- the filler
    language always matches the conversation's current language, same as the LLM's own reply.

    Design principles this function must respect (verbatim from the source library):
    - Vary phrases to reduce repetition and avoid a robotic experience (hence random.choice, not
      a fixed lookup).
    - Use fillers only when there is actual latency or a conversational reason for a pause --
      the CALLER decides whether to invoke this at all; this function never decides that itself.
    - Keep technical implementation details invisible to the user -- see FORBIDDEN_PHRASES.
    """
    if language == "hi":
        return random.choice(_HINDI_PHRASES)
    if language == "hi-en":
        return random.choice(_HINGLISH_PHRASES)

    phrases = _ENGLISH_PHRASES.get(situation)
    return random.choice(phrases) if phrases else None
