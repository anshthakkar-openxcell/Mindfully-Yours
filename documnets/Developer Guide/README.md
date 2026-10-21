# Developer guide (internal)

**Simple_Explanation_How_It_Works_And_Why.pdf** (and the same text as `.md`) — plain 3-page explanation, no diagrams or styling: how the reply system works step by step, and why it is the best approach. Start here.

**Developer_Guide_How_The_Response_System_Works.pdf** — 12-page, plain-language walkthrough of how a reply is produced: the pieces (RDS + pgvector are one PostgreSQL), the whole per-message flow (two diagrams), how "close enough" is decided, the three kinds of reply, safety rules, how data gets in, other languages, why this design, debugging/settings/code map, and what is still missing.

The long-form reference with every detail is `documnets/understanding/35_DEVELOPER_GUIDE_HOW_THE_RESPONSE_SYSTEM_WORKS.md`; this PDF is the short, visual version of it.

## Rebuild
Reuses the diagram kit from `documnets/Client Presentation/AI Response Flow/source/`.
```
python3 source/build_dev_pdf.py     # needs google-chrome
```
(Row counts are not used in this PDF, so the database does not need to be running.)
