# Knowledge Base Source Files

Copies (originals are untouched) of every file the ingestion code reads to build the knowledge base.

| Folder | What it feeds |
|---|---|
| `1_Clinical_Phase_I_Sheets` | Signals, symptoms, routing rules, red flags + safety scripts, sufficiency patterns, fallback scenarios, Clinical Markers (safety / triage / tier logic) |
| `2_Question_Banks_Emotions_Scenarios` | Layer I-IV question banks, emotion phrases, scenario lists, clarification questions, tier question banks, parenting guardrails |
| `3_Lookups_and_Self_Help_Tools` | Career lookup, DBT self-help workbook (Tier 1 self-care recommendations) |
| `4_Therapist_Conversation_Files` | The therapists' "User / AI" dialogues, turned into the therapist-reply table (`kb_therapist_turns`) |
| `5_Client_Drop_2` | Second client drop (decrypted copies): welcome messages, Situational Routing sheet, Best Conversations, AI Companion conversations — see documnets/understanding/33_CLIENT_DROP_2_ADDITIONS.md |

Not copied on purpose: `Career Conversation Sets 1.docx` (one template repeated 500 times), the 3 password-locked files, the architecture/planning documents, and `Pathway For AI...` (a flow spec, not ingested content).

Note: `22-8_Offline Work Week 2.docx` is in folder 4 but is on a governance hold, so it is loaded and never served (see documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #26).
