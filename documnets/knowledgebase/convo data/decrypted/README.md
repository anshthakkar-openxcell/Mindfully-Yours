# What this folder is

A **deduplicated, decrypted, readable copy** of the client's `../MYPL - Mindfully Yours Work/` drop.
The originals are password-protected Word documents; this folder holds plain, openable copies so
the content can actually be reviewed and ingested.

**Full analysis of every file in here**: [`documnets/understanding/18_NEW_CONVO_DATA_CATALOG.md`](../../../understanding/18_NEW_CONVO_DATA_CATALOG.md).

## Why this folder has 44 files, not 46

Three files were intentionally excluded because they add no unique content (verified by direct
diff, not assumed):
- `Anam/dbt-skills-workbook.docx` — a byte-different but content-identical duplicate of the copy
  kept at `.../Anam/dbt-skills-workbook.docx` (differs only in redundant internal Word XML from a
  re-save).
- `Anam/Self Help Conversation - Anam.docx` — a strict subset of `.../Anam/Conversations + Self
  Help - Anam/SELF-HELP CONVERSATIONS.docx`, which is kept instead.
- `Anam/Conversations + Self Help - Anam.zip` — contains the same 8 files already present
  individually in the sibling extracted folder.

## What's still missing

Three files did not decrypt with the password used for the rest of the drop and are **not present
here at all** (not broken copies — simply absent, since there was nothing valid to copy):
- `Anam/Conversation Combinations- sleep.docx`
- `Anam/Conversations Combinations- anxiety 3rd person.docx`
- `Anam/Miscellaneous Conversations.docx`

Anam may have used an individual password different from the rest of the team. Ask her directly,
or check for a second password, then re-run the decryption for just these 3 files.

## Do not re-encrypt or delete the original folder

`../MYPL - Mindfully Yours Work/` (the original, password-protected files) is kept as-is — this
folder is a working copy for review/ingestion, not a replacement.
