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

# ============================================================================
# `ingest` (above) covers the 6 original Phase I sheets.
# `ingest-convo-data` (below) covers the Sept 2026 convo-data drop -- see
# documnets/understanding/21_NEW_CONTENT_INGESTION_PLAN.md for the full per-file plan this
# implements. Kept as a separate command, not folded into `ingest`, since the two operate on
# entirely different source directories and produce entirely different tables.
# ============================================================================


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


@app.command(name="ingest-convo-data")
def ingest_convo_data(
    convo_dir: Path = typer.Option(
        ..., help="Path to 'MYPL - Mindfully Yours Work/' inside convo data/decrypted/."
    ),
    career_csv: Path = typer.Option(
        ..., help="Path to 'Career Field & Stream Lookup.csv' (in The Real Useful Knowledge/2. .../)."
    ),
    label: str = typer.Option(..., help="A label for this KB version, e.g. 'convo-v1-2026-09-28'."),
    embed: bool = typer.Option(True, help="Whether to generate embeddings -- disable for a dry parse-only run."),
) -> None:
    """Parse the Sept 2026 convo-data drop and load it into its own tables (see
    documnets/understanding/21_NEW_CONTENT_INGESTION_PLAN.md for exactly what each file becomes)."""
    configure_logging()
    asyncio.run(_ingest_convo_data_async(convo_dir, career_csv, label, embed))


async def _ingest_convo_data_async(convo_dir: Path, career_csv: Path, label: str, embed: bool) -> None:
    from app.db.models.kb import KBVersion
    from app.db.models.kb_convo_content import (
        KBAnxietySituation,
        KBCareerLookup,
        KBClarificationPhrase,
        KBEmotionPhrase,
        KBGuardrailRule,
        KBLayerContent,
        KBScenario,
        KBTierQuestionBank,
    )
    from app.ingestion.parsers import (
        parse_anxiety_situations,
        parse_career_lookup,
        parse_career_question_set,
        parse_clarification_bank,
        parse_dbt_skills_workbook,
        parse_guardrail_table,
        parse_heading_based_layer_file,
        parse_layer_ii,
        parse_list_of_emotions_tanisha,
        parse_list_of_scenarios,
        parse_phase_ii_emotion_expression,
        parse_phase_ii_layer_i_and_iv,
        parse_questions_by_scenario,
    )

    logger.info("convo_data_ingestion_started", convo_dir=str(convo_dir), label=label)

    layer_content = [
        *parse_heading_based_layer_file(convo_dir / "Layer I Questions and Statments.docx", layer="I"),
        *parse_layer_ii(convo_dir / "Layer II Question Bank.docx"),
        *parse_heading_based_layer_file(convo_dir / "Layer III.docx", layer="III"),
        *parse_heading_based_layer_file(convo_dir / "Layer 2 to 3 Transitions.docx", layer="II-III"),
        *parse_phase_ii_layer_i_and_iv(convo_dir / "PHASE II Layer I and IV Questions.docx"),
    ]

    emotion_phrases = [
        *[
            {**r, "canonical_emotion_group": None}
            for r in parse_phase_ii_emotion_expression(convo_dir / "PHASE II_ Emotion Associated user expression.docx")
        ],
        *[
            {**r, "canonical_emotion_group": None}
            for r in parse_list_of_emotions_tanisha(convo_dir / "List of Emotions - Tanisha.docx")
        ],
    ]

    scenarios = parse_list_of_scenarios(convo_dir / "List of Scenarios - Tanisha.docx")
    anxiety_situations = parse_anxiety_situations(convo_dir / "Anxiety Situations.docx")
    clarification_phrases = parse_clarification_bank(convo_dir / "Questions For When AI Is Not Sure - Tanisha.docx")
    guardrail_rules = parse_guardrail_table(convo_dir / "Parenting_Child Related.docx")
    career_lookup = parse_career_lookup(career_csv)
    dbt_tools = parse_dbt_skills_workbook(
        convo_dir / "MYPL KB 7th Sept" / "Anam" / "dbt-skills-workbook.docx"
    )

    questions = parse_questions_by_scenario(convo_dir / "Questions.docx")
    tier_bank = [
        *[
            {
                "bank_source": "questions_by_scenario",
                "scenario_or_topic": q["scenario"],
                "subsection": q["subsection"],
                "question_type": "open",
                "question_text": q["text"],
                "answer_options_raw": None,
                "tier_routing": None,
                "source_file": q["source_file"],
            }
            for q in questions["open_questions"]
        ],
        *[
            {
                "bank_source": "questions_by_scenario",
                "scenario_or_topic": q["scenario"],
                "subsection": q["subsection"],
                "question_type": "close_ended",
                "question_text": q["question"],
                "answer_options_raw": q["answer_options_raw"],
                "tier_routing": None,
                "source_file": q["source_file"],
            }
            for q in questions["close_ended_questions"]
        ],
        *[
            {
                "bank_source": "career_question_set",
                "scenario_or_topic": c["topic"],
                "subsection": None,
                "question_type": "close_ended",
                "question_text": c["question"],
                "answer_options_raw": c["possible_responses_raw"],
                "tier_routing": c["tier_routing"],
                "source_file": c["source_file"],
            }
            for c in parse_career_question_set(convo_dir / "Question Set - Career.docx")
        ],
    ]

    gov_hold_count = sum(1 for s in scenarios if s["pending_governance_review"])
    logger.info(
        "parsed_convo_data",
        layer_content=len(layer_content),
        emotion_phrases=len(emotion_phrases),
        scenarios=len(scenarios),
        scenarios_pending_governance=gov_hold_count,
        anxiety_situations=len(anxiety_situations),
        clarification_phrases=len(clarification_phrases),
        guardrail_rules=len(guardrail_rules),
        career_lookup=len(career_lookup),
        dbt_tools=len(dbt_tools),
        tier_bank=len(tier_bank),
    )
    if gov_hold_count:
        logger.warning(
            "scenarios_pending_governance_review",
            count=gov_hold_count,
            note="See documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #26 -- these rows "
            "are loaded but MUST be excluded from any live retrieval index until the clinical + "
            "legal governance decision is made.",
        )

    if embed:
        from app.ingestion.embedding import embed_field

        embedding_provider = get_embedding_provider()
        layer_content = await embed_field(
            layer_content, source_field="text", target_field="text_embedding", embedding_provider=embedding_provider
        )
        emotion_phrases = await embed_field(
            emotion_phrases, source_field="phrase", target_field="phrase_embedding", embedding_provider=embedding_provider
        )
        scenarios = await embed_field(
            scenarios, source_field="phrase", target_field="phrase_embedding", embedding_provider=embedding_provider
        )
        clarification_phrases = await embed_field(
            clarification_phrases, source_field="phrase", target_field="phrase_embedding", embedding_provider=embedding_provider
        )
        career_lookup = await embed_field(
            career_lookup, source_field="career_name", target_field="career_name_embedding", embedding_provider=embedding_provider
        )
        tier_bank = await embed_field(
            tier_bank, source_field="question_text", target_field="question_embedding", embedding_provider=embedding_provider
        )
        # dbt_tools load into the EXISTING KBContentChunk table, whose vector column is literally
        # named `embedding` (not `text_embedding` like this module's own new tables) -- embed_field
        # is called with that exact target name so the KBContentChunk(**...) call below lines up.
        dbt_tools = await embed_field(
            dbt_tools, source_field="text", target_field="embedding", embedding_provider=embedding_provider
        )

    async with AsyncSessionLocal() as db:
        version = KBVersion(label=label, status="building")
        db.add(version)
        await db.flush()

        db.add_all([KBLayerContent(**r) for r in layer_content])
        db.add_all([KBEmotionPhrase(**r) for r in emotion_phrases])
        db.add_all([KBScenario(**r) for r in scenarios])
        db.add_all([KBAnxietySituation(**r) for r in anxiety_situations])
        db.add_all([KBClarificationPhrase(**r) for r in clarification_phrases])
        db.add_all([KBGuardrailRule(**r) for r in guardrail_rules])
        db.add_all([KBCareerLookup(**r) for r in career_lookup])
        db.add_all([KBTierQuestionBank(**r) for r in tier_bank])

        from app.db.models.kb import KBContentChunk

        db.add_all(
            [
                KBContentChunk(
                    chunk_id=f"dbt_{tool['tool_name'].lower().replace(' ', '_')}",
                    category="self_care",
                    pattern_name=None,
                    tier=1,
                    content_type="self_care_tool",
                    text=tool["text"],
                    embedding=tool.get("embedding"),
                    source_document=tool["source_file"],
                    language="en",
                    linked_pattern_id=None,
                )
                for tool in dbt_tools
            ]
        )

        await db.commit()
        logger.info("convo_data_loaded_as_building_version", version_id=version.version_id)

    typer.echo(
        f"Ingested convo-data KB version '{label}' (id={version.version_id}) with status='building'. "
        f"{gov_hold_count} scenario rows are pending governance review -- see "
        "documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #26. "
        "NOTE: Questions.docx and Parenting_Child Related.docx's other tables are only partially "
        "covered -- see documnets/understanding/21_NEW_CONTENT_INGESTION_PLAN.md for exactly what's "
        "still missing."
    )


if __name__ == "__main__":
    app()
