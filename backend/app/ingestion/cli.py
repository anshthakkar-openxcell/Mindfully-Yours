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


def _ingestion_embedding_provider():
    """Same OpenAI provider as runtime, but with a generous timeout -- the runtime default (3s) is
    deliberately tight for the live latency budget and too short for large offline batches."""
    from app.core.config import get_settings
    from app.providers.embeddings.openai_embeddings import OpenAIEmbeddingProvider

    settings = get_settings()
    return OpenAIEmbeddingProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
        dimensions=settings.embed_dim,
        timeout=120.0,
    )


@app.command(name="ingest-therapist-turns")
def ingest_therapist_turns(
    convo_dir: Path = typer.Option(
        ..., help="Path to 'MYPL - Mindfully Yours Work/' inside convo data/decrypted/."
    ),
    embed: bool = typer.Option(True, help="Embed match-eligible rows (held rows are never embedded). Disable for a dry parse."),
    approve_eligible: bool = typer.Option(
        False,
        help="Mark every match-eligible row approved=True. Off by default: a row is only served at runtime "
        "once a therapist has signed it off -- see documnets/understanding/32_THERAPIST_FIRST_RESPONSE_APPROACH.md.",
    ),
    dry_run: bool = typer.Option(False, help="Parse and report only; write nothing to the database."),
) -> None:
    """Parse the therapists' User/AI dialogue files into (user message -> therapist reply) pairs and
    load them into kb_therapist_turns. Idempotent: re-running updates rows in place (keyed by content
    hash) and never resets a row's `approved` flag unless --approve-eligible is passed."""
    configure_logging()
    asyncio.run(_ingest_therapist_turns_async(convo_dir, embed, approve_eligible, dry_run))


async def _ingest_therapist_turns_async(convo_dir: Path, embed: bool, approve_eligible: bool, dry_run: bool) -> None:
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.db.models.kb_convo_content import KBTherapistTurn
    from app.ingestion.embedding import embed_field
    from app.ingestion.parsers import parse_therapist_turns

    rows, stats = parse_therapist_turns(convo_dir)
    logger.info(
        "parsed_therapist_turns",
        pairs_found=stats["pairs_found"],
        duplicates_dropped=stats["duplicates_dropped"],
        match_eligible=stats["match_eligible"],
        held=dict(stats["held"]),
    )
    typer.echo(
        f"Parsed {stats['pairs_found']} pairs ({stats['duplicates_dropped']} exact duplicates dropped): "
        f"{stats['match_eligible']} match-eligible, held: {dict(stats['held'])}"
    )
    if dry_run:
        typer.echo("Dry run -- nothing written.")
        return

    if embed:
        # Only rows that can ever be served are embedded -- held rows (crisis, governance, drafting
        # notes, too-short) get no vector, so a nearest-neighbour search cannot return them even
        # if a query forgot the eligibility filter.
        eligible = [r for r in rows if r["match_eligible"]]
        others = [r for r in rows if not r["match_eligible"]]
        eligible = await embed_field(
            eligible,
            source_field="user_text",
            target_field="context_embedding",
            embedding_provider=_ingestion_embedding_provider(),
        )
        rows = eligible + [{**r, "context_embedding": None} for r in others]
    else:
        rows = [{**r, "context_embedding": None} for r in rows]

    if approve_eligible:
        for r in rows:
            r["approved"] = bool(r["match_eligible"])

    update_cols = [
        "turn_index", "prior_context", "scenario", "section", "tier", "author",
        "is_opening", "match_eligible", "hold_reason", "language",
    ]
    if embed:
        update_cols.append("context_embedding")
    if approve_eligible:
        update_cols.append("approved")

    async with AsyncSessionLocal() as db:
        # Prune rows left behind by an earlier parser version: a row's identity is a hash of its
        # text, so a parser fix that changes a reply's text creates a NEW row and would otherwise
        # leave the old (possibly corrupted) one sitting in the table. Scoped to the source files
        # parsed in this run, so a partial re-run never touches other files' rows.
        from sqlalchemy import delete

        parsed_files = {r["source_file"] for r in rows}
        parsed_hashes = {r["content_hash"] for r in rows}
        pruned = await db.execute(
            delete(KBTherapistTurn).where(
                KBTherapistTurn.source_file.in_(parsed_files), KBTherapistTurn.content_hash.not_in(parsed_hashes)
            )
        )
        logger.info("therapist_turns_pruned_stale", rows=pruned.rowcount)
        for start in range(0, len(rows), 500):
            batch = rows[start : start + 500]
            stmt = pg_insert(KBTherapistTurn).values(batch)
            # `source_file` is deliberately NOT updated: a reply that appears in two files keeps the
            # file it was first loaded from. `is_preferred` is OR-ed, so a reply that is ALSO in the
            # client's Best Conversations becomes preferred without ever losing the flag later.
            stmt = stmt.on_conflict_do_update(
                index_elements=["content_hash"],
                set_={
                    **{c: getattr(stmt.excluded, c) for c in update_cols},
                    "is_preferred": KBTherapistTurn.is_preferred | stmt.excluded.is_preferred,
                },
            )
            await db.execute(stmt)
        await db.commit()

    logger.info("therapist_turns_loaded", rows=len(rows), embedded=embed, approved=approve_eligible)
    typer.echo(
        f"Loaded {len(rows)} rows into kb_therapist_turns "
        f"(embedded={embed}, approved={'eligible rows' if approve_eligible else 'none -- pending therapist review'})."
    )


@app.command(name="ingest-client-drop-2")
def ingest_client_drop_2(
    drop_dir: Path = typer.Option(
        ..., help="The DECRYPTED folder of the second client drop ('new uploaded documents/decrypted')."
    ),
    embed: bool = typer.Option(True, help="Generate embeddings (set false for a dry parse)."),
) -> None:
    """Load client drop #2: Best Conversations + AI Companion dialogues (-> kb_therapist_turns, approved),
    AI WELCOME RESPONSES (-> kb_welcome_responses), Situational Routing (-> kb_situational_routing, and
    each self-care strategy -> kb_content_chunks so Tier 1 self-care search can find it). Idempotent."""
    configure_logging()
    asyncio.run(_ingest_client_drop_2_async(drop_dir, embed))


async def _ingest_client_drop_2_async(drop_dir: Path, embed: bool) -> None:
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.db.models.kb import KBContentChunk
    from app.db.models.kb_convo_content import KBSituationalRouting, KBWelcomeResponse
    from app.ingestion.embedding import embed_field
    from app.ingestion.parsers import parse_situational_routing, parse_welcome_responses

    welcome = parse_welcome_responses(drop_dir / "AI WELCOME RESPONSES.docx")
    situations = parse_situational_routing(drop_dir / "Copy of Situational Routing.xlsx")
    typer.echo(f"Parsed {len(welcome)} welcome messages and {len(situations)} situations.")

    if embed:
        provider = _ingestion_embedding_provider()
        situations = await embed_field(
            situations, source_field="situation", target_field="situation_embedding", embedding_provider=provider
        )
        # Self-care chunks are embedded as "situation. strategy" -- the user's message describes the
        # SITUATION, so that is what it has to match; the strategy text alone would match poorly.
        chunk_inputs = [
            {**sit, "_chunk_text": f"{sit['situation']}. {sit['self_care_strategy']}"}
            for sit in situations
            if sit["self_care_strategy"]
        ]
        chunk_inputs = await embed_field(
            chunk_inputs, source_field="_chunk_text", target_field="embedding", embedding_provider=provider
        )
    else:
        chunk_inputs = [s for s in situations if s["self_care_strategy"]]
        for c in chunk_inputs:
            c["embedding"] = None

    chunk_rows = [
        {
            "chunk_id": f"sit_{c['situation_id'].lower().replace('-', '_')}_selfcare",
            "category": c["category"],
            "pattern_name": c["situation"],
            "tier": 1,
            "content_type": "self_care_tool",
            "text": c["self_care_strategy"],
            "embedding": c["embedding"],
            "source_document": c["source_file"],
            "language": "en",
            "linked_pattern_id": None,
        }
        for c in chunk_inputs
    ]
    situation_rows = [{k: v for k, v in s.items() if not k.startswith("_")} for s in situations]
    for s_row in situation_rows:
        s_row.setdefault("situation_embedding", None)

    async with AsyncSessionLocal() as db:
        await db.execute(pg_insert(KBWelcomeResponse).values(welcome).on_conflict_do_nothing(index_elements=["text"]))
        stmt = pg_insert(KBSituationalRouting).values(situation_rows)
        await db.execute(
            stmt.on_conflict_do_update(
                index_elements=["situation_id"],
                set_={c: getattr(stmt.excluded, c) for c in situation_rows[0] if c != "situation_id"},
            )
        )
        stmt = pg_insert(KBContentChunk).values(chunk_rows)
        await db.execute(
            stmt.on_conflict_do_update(
                index_elements=["chunk_id"],
                set_={c: getattr(stmt.excluded, c) for c in chunk_rows[0] if c != "chunk_id"},
            )
        )
        await db.commit()
    typer.echo(
        f"Loaded {len(welcome)} welcome messages, {len(situation_rows)} situations, "
        f"{len(chunk_rows)} self-care chunks (live for Tier 1 self-care search)."
    )

    # Therapist dialogues: same loader as drop 1, approved per the client/team decision (2026-10-09).
    await _ingest_therapist_turns_async(drop_dir, embed, approve_eligible=True, dry_run=False)


# The fixed English messages the pipeline itself can say (see app.pipeline.orchestrator). Translated
# ahead of time like every other fixed reply, so even a crisis fallback is instant in Hindi.
_FIXED_MESSAGES = [
    "I want to make sure you get the right support -- let me connect you with someone.",
    "I want to make sure you get the right support right now -- let me connect you with someone who can help.",
]


@app.command(name="translate-kb")
def translate_kb(
    kinds: str = typer.Option(
        "red_flag_script,fixed_message,clarifying_question,welcome,therapist_reply",
        help="Comma-separated, in priority order. Safety scripts first so a partial run still covers them.",
    ),
    styles: str = typer.Option("hi,hinglish", help="Which languages: hi (Devanagari), hinglish (Roman)."),
    concurrency: int = typer.Option(6, help="Parallel Sarvam calls."),
    limit: int = typer.Option(0, help="Stop after this many NEW translations (0 = no limit) -- for a trial run."),
) -> None:
    """Pre-translate every fixed English reply into Hindi / Hinglish (kb_translations), so a Hindi speaker
    gets it instantly at runtime. Idempotent and resumable: anything already translated is skipped."""
    configure_logging()
    asyncio.run(_translate_kb_async([k.strip() for k in kinds.split(",")], [x.strip() for x in styles.split(",")], concurrency, limit))


async def _translate_kb_async(kinds: list[str], styles: list[str], concurrency: int, limit: int) -> None:
    import httpx
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.models.kb import KBFallbackScenario, KBRedFlag
    from app.db.models.kb_convo_content import KBClarificationPhrase, KBTherapistTurn, KBTranslation, KBWelcomeResponse
    from app.pipeline.curated_match import GENERIC_CLARIFY_CATEGORIES
    from app.pipeline.localize import source_hash, store_translation
    from app.providers.factory import get_translator

    settings = get_settings()
    translator = get_translator()

    async def gather(kind: str) -> list[str]:
        async with AsyncSessionLocal() as db:
            if kind == "red_flag_script":
                rows = (await db.execute(select(KBRedFlag.bot_script).where(KBRedFlag.bot_script.is_not(None)))).scalars().all()
                rows += (await db.execute(select(KBFallbackScenario.bot_script).where(KBFallbackScenario.bot_script.is_not(None)))).scalars().all()
                return list(rows)
            if kind == "fixed_message":
                return list(_FIXED_MESSAGES)
            if kind == "clarifying_question":
                stmt = select(KBClarificationPhrase.phrase).where(
                    KBClarificationPhrase.category.in_(GENERIC_CLARIFY_CATEGORIES),
                    KBClarificationPhrase.phrase.like("%?"),
                    KBClarificationPhrase.has_drafting_note.is_(False),
                )
                return list((await db.execute(stmt)).scalars().all())
            if kind == "welcome":
                # Translated in their "Hi there, ..." form (the name slot filled), NOT the raw "Hi user, ..."
                # template -- otherwise the word "user" itself would be translated.
                from app.pipeline.welcome import fill_name

                rows = (await db.execute(select(KBWelcomeResponse.text).where(KBWelcomeResponse.approved.is_(True)))).scalars().all()
                return [fill_name(t, None) for t in rows]
            if kind == "therapist_reply":
                stmt = select(KBTherapistTurn.reply_text).where(KBTherapistTurn.approved.is_(True), KBTherapistTurn.match_eligible.is_(True))
                return list((await db.execute(stmt)).scalars().all())
        raise typer.BadParameter(f"unknown kind {kind!r}")

    async def already_done(style: str) -> set[str]:
        async with AsyncSessionLocal() as db:
            return set((await db.execute(select(KBTranslation.source_hash).where(KBTranslation.style == style))).scalars().all())

    sem = asyncio.Semaphore(concurrency)
    stats = {"new": 0, "failed": 0}

    async def one(text: str, style: str, kind: str) -> None:
        if limit and stats["new"] >= limit:
            return
        async with sem:
            for attempt in range(4):  # rate limits / blips: back off and retry
                try:
                    translated = await translator.from_english(text, style=style)  # type: ignore[arg-type]
                    await store_translation(text, style, translated, kind=kind, model=settings.sarvam_translate_model)
                    stats["new"] += 1
                    if stats["new"] % 100 == 0:
                        typer.echo(f"  ...{stats['new']} translated")
                    return
                except (httpx.HTTPError, Exception) as exc:  # noqa: BLE001
                    await asyncio.sleep(1.5 * (attempt + 1))
                    last = exc
            stats["failed"] += 1
            logger.error("translate_kb_item_failed", error=str(last), kind=kind, style=style)

    for kind in kinds:
        texts = sorted({t.strip() for t in await gather(kind) if t and t.strip()})
        for style in styles:
            done = await already_done(style)
            todo = [t for t in texts if source_hash(t) not in done]
            typer.echo(f"{kind} / {style}: {len(todo)} to translate ({len(texts) - len(todo)} already done)")
            await asyncio.gather(*[one(t, style, kind) for t in todo])
    typer.echo(f"Done: {stats['new']} new translations, {stats['failed']} failed.")


if __name__ == "__main__":
    app()
