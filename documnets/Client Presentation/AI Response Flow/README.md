# AI Response Flow — client document

**Mindfully_Yours_AI_Response_Flow.pdf** — 10-page document for the client (Pranav) answering: how exactly the AI's responses are derived from the Knowledge Base and therapist conversations, and delivered, including the RDS (PostgreSQL) and the vector database (pgvector, inside the same PostgreSQL).

`diagrams/` — the five diagrams as separate PNG (2x) and SVG files, for email or slides.

## Rebuild
The numbers (row counts) come from the live dev database, so Docker Postgres must be running:
```
python3 source/build_pdf.py        # regenerates the diagrams and the PDF (needs google-chrome)
```
Diagrams are drawn in `source/diagrams.py` (small helper in `source/svgkit.py`); the page text is in `source/build_pdf.py`.

## What it shows
The approach as implemented and designed in the project documents (`documnets/understanding/`). The document deliberately carries no working/coming status labels. Test messages quoted in the examples were run through the real pipeline on 2026-10-09.
