"""
Signal enrichment -- joins A1 (signals) + C11 (rules) + A2 (symptoms) into enriched records, per
documnets/understanding/06_SIGNAL_ENRICHMENT_PIPELINE.md. Computed ONCE at ingestion time so the
runtime pipeline never needs a live cross-reference lookup (this is what makes
app.pipeline.retrieval.fetch_probing_guidance a direct fetch, not a join, at query time).

Confirmed real result on the actual client data (not an estimate): only 25 of 285 signals
auto-match to a routing rule via this simple approach, because most of C11's 66 rules reference
RANGES or COMBINATIONS ("SIG 001-017 minus SIG002-003") that single-number matching can't expand.
See documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #4 -- this is a known, documented
limitation, not a bug to silently paper over. Treat this module's output as a validated STARTING
format, not a finished mapping, until a real range/combination parser is built.
"""

from app.ingestion.parsers.common import match_signal_in_trigger_condition


def enrich_signals_with_rules(signals: list[dict], rules: list[dict]) -> list[dict]:
    """
    Merge 1 from documnets/understanding/06_SIGNAL_ENRICHMENT_PIPELINE.md §2: for each signal,
    find every routing rule whose trigger_condition mentions that signal's number.

    Returns a new list (does not mutate `signals`), each record with `matched_rules` added:
    a list of {"rule_id": ..., "priority": ..., "route_to": ...} dicts, ordered by priority.
    """
    enriched = []
    for signal in signals:
        signal_number = int(signal["signal_id"].split("-")[1])
        matches = [
            {"rule_id": rule["rule_id"], "priority": rule["priority"], "route_to": rule["route_to"]}
            for rule in rules
            if rule["route_to"] is not None  # exclude Rule-025 and any other incomplete rule
            and match_signal_in_trigger_condition(rule["trigger_condition"], signal_number)
        ]
        matches.sort(key=lambda m: m["priority"] or 99)
        enriched.append({**signal, "matched_rules": matches or None})
    return enriched


def enrich_symptoms_with_signals(symptoms: list[dict], enriched_signals: list[dict]) -> list[dict]:
    """
    Merge 2 from documnets/understanding/06_SIGNAL_ENRICHMENT_PIPELINE.md §3: for each symptom
    (PHYS-/PHSY- rows only -- `linked_signal_ids` is already [] for EM- rows, see
    app.ingestion.parsers.symptom_map), pull forward a SUMMARY of its linked signals -- not the
    full signal record, which would bloat every row with duplicate content already available
    elsewhere (see app.db.models.kb.KBSignal for the source of truth).
    """
    signals_by_id = {s["signal_id"]: s for s in enriched_signals}

    enriched = []
    for symptom in symptoms:
        linked_ids = symptom.get("linked_signal_ids") or []
        resolved = [signals_by_id[sid] for sid in linked_ids if sid in signals_by_id]

        linked_concepts = [s["clinical_concept"] for s in resolved[:6]]
        any_red_flag = any(s["red_flag"] for s in resolved)
        max_severity = max((s["severity"] for s in resolved if s["severity"] is not None), default=None)

        enriched.append(
            {
                **symptom,
                "linked_concepts": linked_concepts or None,
                "any_linked_red_flag": any_red_flag,
                "max_linked_severity": max_severity,
            }
        )
    return enriched
