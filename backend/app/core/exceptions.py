"""
Domain exceptions for the AI service. Kept distinct from generic HTTP errors so that safety-path
failures are unambiguous in logs and can never be silently swallowed by a broad except clause.

Per documnets/understanding/01_PROJECT_OVERVIEW.md principle #2 and 08_SAFETY_INTERLOCK_AND_TRIAGE.md
§6, any failure inside the safety interlock must fail SAFE -- i.e. toward the more cautious routing
outcome, never toward silently continuing as if nothing happened. SafetyInterlockError exists so
that guarantee is enforced structurally: callers must handle it explicitly, they cannot ignore it.
"""


class MindfullyAIError(Exception):
    """Base class for all AI-service domain errors."""


class SafetyInterlockError(MindfullyAIError):
    """
    Raised when the safety interlock itself fails to evaluate (timeout, data error, etc).

    The caller MUST treat this as a signal to fail toward the more cautious path (e.g. route to
    Tier 2/human review), never to proceed as if no red flag was present. Never catch this broadly
    and continue the normal conversation flow -- see 08_SAFETY_INTERLOCK_AND_TRIAGE.md §1.
    """


class MissingBotScriptError(MindfullyAIError):
    """
    Raised when a matched Red Flag or Fallback scenario has no bot_script to fetch verbatim
    (e.g. RF-028-031 today -- see documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #1).

    Must route to a hard human alert. Never caught in order to fall back to LLM-generated text.
    """

    def __init__(self, flag_or_scenario_id: str):
        self.flag_or_scenario_id = flag_or_scenario_id
        super().__init__(
            f"No verbatim bot_script available for '{flag_or_scenario_id}' -- "
            "this must route to a hard human alert, not LLM generation."
        )


class KBVersionNotLiveError(MindfullyAIError):
    """Raised when a query is attempted against a KB version that hasn't passed the
    pre-launch validation gate (documnets/understanding/07_INGESTION_PIPELINE.md §2, step 8)."""


class ProviderError(MindfullyAIError):
    """Raised by a provider adapter (app/providers/*) on a vendor-call failure. Pipeline code
    should catch this specifically to apply the graceful-degradation ladder (avatar -> voice ->
    text; interlock-only safe path if the LLM itself is unavailable) -- see
    documnets/understanding/09_LATENCY_AND_PERFORMANCE.md and 01_PROJECT_OVERVIEW.md §4."""

    def __init__(self, provider_name: str, detail: str):
        self.provider_name = provider_name
        self.detail = detail
        super().__init__(f"[{provider_name}] {detail}")
