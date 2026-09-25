"""
Parser for `Kb Phase I(C11.csv` -- Routing Rules. 66 rules (Rule-025 incomplete: no route_to/priority).

Confirmed real structure (documnets/understanding/05_KNOWLEDGE_BASE_DEEP_DIVE.md §4): real header
at row 4: Rule ID, Trigger Condition, Logical Expression (always blank -- dev-filled, never
populated by the client), Route To, Override Reason, Trajectory Factor, Priority. The file has 23
raw columns from the export but only the first 7 are ever populated.

CRITICAL: Priority (1/2/3) is the real evaluation order, NOT Rule ID order -- confirmed to diverge
in the real data (e.g. RULE-004 is priority 1, RULE-002/003 are priority 2). See
app.safety.routing.evaluate_routing_rules, which enforces ordering by Priority, never by rule_id.
"""

from pathlib import Path

from app.ingestion.parsers.common import clean_cell, normalize_rule_id, read_client_csv

HEADER_ROW = 4


def parse_routing_rules(path: str | Path) -> list[dict]:
    df = read_client_csv(path, header_row=HEADER_ROW)
    df = df.dropna(subset=["Rule ID"])

    records = []
    for _, row in df.iterrows():
        priority = _parse_priority(row.get("Priority"))
        route_to = _clean(row.get("Route To"))

        records.append(
            {
                "rule_id": normalize_rule_id(str(row["Rule ID"])),
                "trigger_condition": _clean(row.get("Trigger Condition")) or "",
                "route_to": route_to,  # None for Rule-025 -- confirmed incomplete in source data
                "override_reason": _clean(row.get("Override Reason")),
                "trajectory_factor": _clean(row.get("Trajectory Factor")),
                "priority": priority,  # None for Rule-025
            }
        )
    return records


def _clean(value) -> str | None:
    # Delegates to the shared, NaN-safe cleaner -- see app.ingestion.parsers.common.clean_cell's
    # docstring for the bug this avoids (pandas NaN stringifying to the literal "nan").
    return clean_cell(value)


def _parse_priority(value) -> int | None:
    try:
        priority = int(value)
    except (TypeError, ValueError):
        return None
    return priority if priority in (1, 2, 3) else None
