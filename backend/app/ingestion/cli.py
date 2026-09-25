"""
Ingestion CLI -- the entrypoint for Epic B (offline KB ingestion), run as a script, never through
the HTTP API. Usage: `python -m app.ingestion.cli ingest --kb-dir documnets/knowledgebase`.

Per documnets/understanding/07_INGESTION_PIPELINE.md: this runs once per document and again on any
KB update -- it does not touch the live conversation latency budget, so correctness matters far
more than speed here.
"""

import asyncio
from pathlib import Path

import typer

from app.core.logging import configure_logging, get_logger
from app.db.models.kb import (
    KBFallbackScenario,
    KBRedFlag,
    KBRoutingRule,
    KBSignal,
    KBSufficiencyPattern,
    KBSymptom,
    KBVersion,
)
from app.db.session import AsyncSessionLocal
from app.ingestion.enrichment import enrich_signals_with_rules, enrich_symptoms_with_signals
from app.ingestion.parsers import (
    parse_fallback_scenarios,
    parse_red_flags,
    parse_routing_rules,
    parse_signal_legend,
    parse_sufficiency,
    parse_symptom_map,
)
from app.providers.factory import get_embedding_provider

app = typer.Typer(help="Mindfully Yours AI service -- KB ingestion CLI")
logger = get_logger(__name__)


@app.command()
def ingest(
    kb_dir: Path = typer.Option(..., help="Path to the directory containing the raw KB CSV files."),
    label: str = typer.Option(..., help="A label for this KB version, e.g. 'v1-2026-09-25'."),
    embed: bool = typer.Option(True, help="Whether to generate embeddings (slow, costs money -- disable for a dry parse-only run)."),
) -> None:
    """Parse every real KB sheet, enrich, optionally embed, and load into a new (non-live) KB version."""
    configure_logging()
    asyncio.run(_ingest_async(kb_dir, label, embed))


async def _ingest_async(kb_dir: Path, label: str, embed: bool) -> None:
    logger.info("ingestion_started", kb_dir=str(kb_dir), label=label)

    signals = parse_signal_legend(kb_dir / "Kb Phase I(A1.csv")
    symptoms = parse_symptom_map(kb_dir / "Kb Phase I(A2.csv")
    rules = parse_routing_rules(kb_dir / "Kb Phase I(C11.csv")
    red_flags = parse_red_flags(kb_dir / "Kb Phase I(7.csv")
    sufficiency = parse_sufficiency(kb_dir / "Kb Phase I(9.csv")
    fallback = parse_fallback_scenarios(kb_dir / "Kb Phase I(17.csv")

    logger.info(
        "parsed_kb_sheets",
        signals=len(signals),
        symptoms=len(symptoms),
        rules=len(rules),
        red_flags=len(red_flags),
        sufficiency=len(sufficiency),
        fallback=len(fallback),
    )

    missing_scripts = [rf["flag_id"] for rf in red_flags if rf["bot_script"] is None]
    if missing_scripts:
        logger.warning(
            "red_flags_missing_bot_script",
            flag_ids=missing_scripts,
            note="See documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #1 -- these must "
            "route to a hard human alert at runtime, not block ingestion, but MUST be flagged loudly.",
        )

    signals = enrich_signals_with_rules(signals, rules)
    symptoms = enrich_symptoms_with_signals(symptoms, signals)

    if embed:
        from app.ingestion.embedding import embed_field, embed_red_flag_phrases

        embedding_provider = get_embedding_provider()
        signals = await embed_field(
            signals, source_field="phrasings_text", target_field="phrasing_embedding", embedding_provider=embedding_provider
        )
        symptoms = await embed_field(
            symptoms, source_field="how_described", target_field="how_described_embedding", embedding_provider=embedding_provider
        )
        red_flags = await embed_red_flag_phrases(red_flags, embedding_provider=embedding_provider)
        sufficiency = await embed_field(
            sufficiency, source_field="pattern_name", target_field="pattern_name_embedding", embedding_provider=embedding_provider
        )

    async with AsyncSessionLocal() as db:
        version = KBVersion(label=label, status="building")
        db.add(version)
        await db.flush()

        db.add_all([KBSignal(**s) for s in signals])
        db.add_all([KBSymptom(**s) for s in symptoms])
        db.add_all([KBRoutingRule(**r) for r in rules])
        db.add_all([KBRedFlag(**rf) for rf in red_flags])
        db.add_all([KBSufficiencyPattern(**s) for s in sufficiency])
        db.add_all([KBFallbackScenario(**f) for f in fallback])

        await db.commit()
        logger.info("ingestion_loaded_as_building_version", version_id=version.version_id)

    typer.echo(
        f"Ingested KB version '{label}' (id={version.version_id}) with status='building'. "
        "Run the validation suite (app.ingestion.validation) before activating it -- "
        "see documnets/understanding/07_INGESTION_PIPELINE.md §2 step 6-8."
    )


if __name__ == "__main__":
    app()
