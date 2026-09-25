"""
Batch embedding generation -- pipeline step 4 of documnets/understanding/07_INGESTION_PIPELINE.md.
Batched, not one call per text -- this is free efficiency during an offline step (no runtime
latency budget applies here, unlike app.pipeline).

Per documnets/understanding/06_SIGNAL_ENRICHMENT_PIPELINE.md §6 / CHUNKING_EMBEDDING_STRATEGY.md,
only specific fields per sheet are worth embedding -- this module embeds exactly those fields,
nothing else:
  - KBSignal.phrasings_text          -> phrasing_embedding
  - KBSymptom.how_described          -> how_described_embedding  (PHYS/PHSY rows only -- EM rows
                                          have no real phrasing to embed, see symptom_map.py)
  - KBRedFlag.trigger_phrases        -> trigger_embedding (joined, then embedded as one string)
  - KBSufficiencyPattern.pattern_name -> pattern_name_embedding (the ONE narrow embedding case)

Explicitly NOT embedded: routing rules, fallback trigger_condition, sufficiency
minimum/must-have signals -- these are rule/lookup content, not search targets. See
documnets/understanding/05_KNOWLEDGE_BASE_DEEP_DIVE.md and CHUNKING_EMBEDDING_STRATEGY.md.
"""

from app.providers.base import EmbeddingProvider

BATCH_SIZE = 64  # tune against the embedding provider's real batch limits once confirmed


async def embed_field(records: list[dict], *, source_field: str, target_field: str, embedding_provider: EmbeddingProvider) -> list[dict]:
    """
    Generic batched embed-one-field-into-another helper, reused across all four embeddable fields
    listed in the module docstring. Records missing `source_field` (e.g. EM- rows with no
    how_described-equivalent) get `target_field: None`, not an embedding of an empty string.
    """
    enriched = [dict(r) for r in records]
    to_embed_indices = [i for i, r in enumerate(enriched) if r.get(source_field)]

    for batch_start in range(0, len(to_embed_indices), BATCH_SIZE):
        batch_indices = to_embed_indices[batch_start : batch_start + BATCH_SIZE]
        texts = [enriched[i][source_field] for i in batch_indices]
        embeddings = await embedding_provider.embed(texts)
        for i, embedding in zip(batch_indices, embeddings, strict=True):
            enriched[i][target_field] = embedding

    for r in enriched:
        r.setdefault(target_field, None)

    return enriched


async def embed_red_flag_phrases(red_flags: list[dict], *, embedding_provider: EmbeddingProvider) -> list[dict]:
    """Red flags have a LIST of trigger phrases, not a single text field -- join them before
    embedding so the match target reflects the whole flag's phrasing space, per
    documnets/understanding/08_SAFETY_INTERLOCK_AND_TRIAGE.md §4."""
    with_joined_text = [
        {**rf, "_joined_phrases": " | ".join(rf["trigger_phrases"])} for rf in red_flags
    ]
    embedded = await embed_field(
        with_joined_text,
        source_field="_joined_phrases",
        target_field="trigger_embedding",
        embedding_provider=embedding_provider,
    )
    for r in embedded:
        r.pop("_joined_phrases", None)
    return embedded
