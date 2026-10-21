"""
A fast, no-network guess at the language STYLE of one user message: "en", "hi" (Devanagari) or
"hinglish" (Hindi written in Latin letters, often mixed with English).

Why this exists: the therapist library is English-only (doc 13 -- Hindi is a later phase with its own
library). A Hindi or Hinglish message matches it badly (measured 0.14-0.21 similarity), so serving an
English therapist reply or an English clarifying question to someone speaking Hindi is wrong and
confusing. Messages that are not clearly English therefore skip the English library and go to the
LLM, which is told to answer in the user's own language. This is a heuristic, deliberately instant
(no API call -- see doc 32 Gate 1); a message that mixes Hindi and English counts as non-English.
"""

from __future__ import annotations

import re
from typing import Literal

Style = Literal["en", "hi", "hinglish"]

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LETTERS = re.compile(r"[A-Za-zऀ-ॿ]")
_WORDS = re.compile(r"[a-z']+")
# Hindi words written in Latin letters. Chosen to be distinctive: ambiguous words that are also
# ordinary English ("main", "to", "me", "so", "par", "man", "do") are deliberately left out.
_HINGLISH_MARKERS = frozenset(
    """hai hain nahi nahin kya mujhe mujhko mera meri mere aur kuch bahut bohot raha rahi rahe lagta lagti
    lag mann tum aap yeh yah woh kyun kyu lekin abhi sab thoda hoon hun tha thi karna karne kiya gaya
    gayi chahta chahti chahiye pichhle mahine ghar jeena marne zindagi dukh pareshan udaas accha acha
    theek thik samajh toh bhi hoga hogi kabhi kuchh apni apna apne unka unki uska uski isliye kyunki
    matlab bilkul bas dost""".split()
)


def detect_language_style(text: str) -> Style:
    letters = _LETTERS.findall(text)
    if not letters:
        return "en"
    if len(_DEVANAGARI.findall(text)) >= 2:
        return "hi"
    words = _WORDS.findall(text.lower())
    hits = {w for w in words if w in _HINGLISH_MARKERS}
    if len(hits) >= 2 or (hits and len(words) <= 4):
        return "hinglish"
    return "en"


def language_instruction(style: Style) -> str:
    """The explicit language line for the LLM prompt -- replaces leaving it to the model to guess,
    which got it wrong in testing (an English message answered in Hinglish)."""
    if style == "en":
        return "The user is writing in English -- reply in English only."
    return (
        "The user is writing in Hindi, or a mix of Hindi and English (Hinglish). Reply in the SAME mix "
        "and the SAME script they used -- Devanagari if they wrote Devanagari, Roman letters if they "
        "wrote Roman letters -- in simple, everyday words, never formal or textbook Hindi."
    )
