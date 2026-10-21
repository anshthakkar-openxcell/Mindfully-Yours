"""Builds Developer_Guide_How_The_Response_System_Works.pdf (internal, for developers). Plain language, whole flow."""
import pathlib
import subprocess

from dev_diagrams import bands, kb_build, part_a, part_b, rds_vector, system

HERE = pathlib.Path(__file__).parent
OUT = HERE.parent
PAGE = [1]


def page(title, body, kicker="", cls=""):
    PAGE[0] += 1
    k = f'<div class="kicker">{kicker}</div>' if kicker else ""
    return (f'<section class="page {cls}">{k}<h2>{title}</h2>{body}'
            f'<div class="foot">Mindfully Yours  -  Developer guide (internal)  -  page {PAGE[0]}</div></section>')


def table(headers, rows, cls=""):
    th = "".join(f"<th>{h}</th>" for h in headers)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'


def card(title, inner, cls=""):
    return f'<div class="card {cls}"><h4>{title}</h4>{inner}</div>'


pages = []

# 1 cover
pages.append('''<section class="page cover">
<div class="brand">MINDFULLY YOURS  -  INTERNAL, FOR DEVELOPERS</div>
<h1>How a reply is produced</h1>
<p class="sub">The whole flow in plain language: what happens to a user's message, where the data lives, how the reply is chosen, and why we built it this way.</p>
<div class="answer"><h3>The idea in short</h3><ol>
<li><b>The therapists' conversations are the product.</b> A reply should come from them first. The LLM is a helper that rewords, and a last resort.</li>
<li><b>One "meaning vector" per message.</b> The message is turned into a list of numbers that captures its meaning. Every search reuses that one vector.</li>
<li><b>Safety is checked first, always.</b> A red flag gives the approved script, word for word. The LLM is never involved.</li>
<li><b>Then we search the therapist conversations by meaning.</b> Very close: send the therapist's reply as written. Fairly close: the LLM rewords a few close examples, and a check stops it adding anything. Not close: ask a therapist-written question, and only then use the LLM.</li>
<li><b>One PostgreSQL does two jobs.</b> The tables ("RDS") and the vector search are the same database. Redis only holds short-lived memory.</li>
<li><b>Everything is explainable and adjustable.</b> Each reply is logged with its source, every cut-off is a config setting, and the library grows by adding approved rows. No retraining and no deploy.</li></ol></div>
<div class="journey"><div><b>1</b>Message arrives<span>text, or voice turned into text</span></div><i>&#9654;</i><div><b>2</b>Safety check<span>red flag: approved script, stop</span></div><i>&#9654;</i><div><b>3</b>Search therapist conversations<span>by meaning, in the database</span></div><i>&#9654;</i><div><b>4</b>Choose the reply source<span>as written, reworded, or ask</span></div><i>&#9654;</i><div><b>5</b>Deliver and record<span>memory and an audit row</span></div></div>
<div class="note">How to read this: pages 2 to 5 show the system and the flow with diagrams. Pages 6 to 8 explain the decisions (matching, the three kinds of reply, safety). Pages 9 to 12 cover the data, languages, why this design, debugging and what is still missing.</div>
</section>''')

# 2 system
pages.append(page("The pieces and where they sit", f'''<div class="diagram">{system().render()}</div>
<div class="three eq">
{card("PostgreSQL (the RDS) + pgvector", "<p>One database. Normal columns hold text, rules and scripts. A vector column on the same row holds the meaning vector, and an index makes finding the nearest vectors fast. One query returns the nearest rows <i>and</i> their text, so there is nothing to keep in sync.</p>", "b")}
{card("Redis", "<p>Short-lived memory only: the conversation so far (6 hours) and a 24-hour cache of repeated replies. Nothing here is the source of truth.</p>", "y")}
{card("Outside AI services", "<p>OpenAI makes the meaning vectors (embeddings). Sarvam does the language model, speech, and translation. All sit behind adapters so they can be swapped.</p>", "g")}
</div>'''))

# 3 rds + vector
pages.append(page("RDS and the vector database on one real question", f'''<div class="diagram">{rds_vector().render()}</div>
<p class="small"><b>Similarity</b> is 1 minus the cosine distance between two vectors: 1.0 is identical meaning, a paraphrase usually scores 0.65 to 0.85, an unrelated sentence 0.5 or below. The query only looks at rows that are <b>approved and eligible</b>, which is also the condition of the fast index.</p>'''))

# 4 part A
pages.append(page("One message, start to finish: part A", f'''<div class="diagram">{part_a().render()}</div>
<ul class="notes"><li><b>One embedding per message.</b> It is the slowest step (about 0.3 to 1.3 s, sometimes 2 to 3 s). Every search reuses it. A second one in sequence would break the time budget.</li>
<li><b>The therapist search starts early and runs in the background</b> on its own database session, while triage and the safety check run. When we need the answer it has already finished.</li>
<li><b>Safety can cancel everything.</b> If a red flag matches, the therapist search is dropped and the approved script is sent. If the embedding or the safety check itself fails, the reply is a safe "let me connect you with someone".</li></ul>''', "THE FLOW", cls="flow"))

# 5 part B
pages.append(page("One message, start to finish: part B", f'''<div class="diagram">{part_b().render()}</div>
<ul class="notes"><li><b>Order matters:</b> a strong therapist match is sent before the cache is even looked at. A partial match checks the cache first. A therapist reply beats a cached AI reply, and a cached reply beats calling the AI again.</li>
<li><b>The clarifying question</b> is only used when nothing at all grounds the reply, the message has at least 4 words, and we have not just asked one (the limit is 1 in a row).</li>
<li><b>Last step:</b> memory is updated, the AI reply (not therapist replies) is cached, and one audit row records which path answered.</li></ul>''', "THE FLOW", cls="flow"))

# 6 bands
pages.append(page("How close is close enough?", f'''<div class="diagram">{bands().render()}</div>
{table(["Rule", "What it does", "Why"], [
 ["Only <b>approved and eligible</b> rows are searched", "Held rows (crisis, unfinished, too short, on hold) can never be returned", "Safety and quality: nothing unreviewed is ever spoken as the therapist's voice"],
 ["Best match is banded by its <b>true similarity</b>", "Strong at or above 0.85, partial at or above 0.62, otherwise none", "Three different situations need three different handlings"],
 ["Mid-conversation rows need <b>0.90</b> for strong", "A reply like 'What do you miss most?' only makes sense in context", "Makes verbatim reuse of context-dependent rows rarer"],
 ["The best conversations get a <b>+0.02 tie-breaker</b>", "Only used to pick between close rows", "It can never lift a poor match over a threshold"],
 ["Up to <b>3 distinct</b> close replies are collected", "On a partial match the LLM sees all of them", "It learns the pattern, not just one sentence"]], "data")}
<p class="small"><b>Index gotcha:</b> the fast index only applies to rows that are approved and eligible, so the query must be written with plain boolean columns. SQLAlchemy's <i>.is_(True)</i> becomes "IS true", which Postgres cannot match to the index, and it silently scans every row. After changing that query, run EXPLAIN and look for the index name.</p>'''))

# 7 three kinds of reply
pages.append(page("The three kinds of reply", f'''<div class="three eq">
{card("1  Strong: the therapist's reply, as written", "<p>The reply stored for the nearest conversation is sent unchanged. <b>No LLM call</b>, so it is the fastest and lowest-risk path. It gets slightly faster and cheaper as the library grows.</p><p class='mt'><b>Logged as</b> therapist_verbatim</p>", "g")}
{card("2  Partial: the LLM rewords, but cannot invent", "<p>A small prompt shows up to 3 close therapist examples (<i>someone said X, the therapist replied Y</i>) and says: write one reply using only the ideas and wording already in them; add no advice, numbers or links.</p><p class='mt'>The output is <b>held back and checked</b>: no new numbers or links, about the same length, and most of its words come from the therapists' text. If it fails, <b>the therapist's original is sent</b>. If the LLM errors, same fallback.</p><p class='mt'><b>Logged as</b> therapist_adapted / therapist_verbatim_fallback</p>", "b")}
{card("3  None: ask, then the LLM", "<p>First, what can ground the reply (in this order): a soft-concern follow-up, the booking nudge, Tier 1 self-care advice, or probing guidance for the likely pattern.</p><p class='mt'>If nothing grounds it, ask the nearest <b>generic</b> therapist clarifying question (once). Otherwise the LLM answers with the persona, a checklist of what to quietly notice, the last 6 turns and that one piece of grounding.</p><p class='mt'><b>Logged as</b> therapist_clarify / rag_retrieval</p>", "y")}
</div>
<div class="two">{card("What the guard does and does not do", "<p>It is instant (no second model call), so it adds no delay. It catches drift, padding and added numbers or links. It does <b>not</b> prove the meaning is identical, and for non-English replies only the number, link and length checks apply. Setting <i>CURATED_PARTIAL_MODE=verbatim</i> skips the LLM for partial matches.</p>")}
{card("Where the LLM never goes", "<p>It never decides whether something is a crisis, never edits a safety script, and never adds clinical advice to a matched therapist reply. For fully AI-written replies the output check today only logs a problem; it does not block.</p>", "r")}</div>''', cls="lg"))

# 8 safety
pages.append(page("Safety: the part that must never regress", '''
<div class="two">
<div>
<ul class="notes big">
<li><b>Runs first, every message.</b> Even when a cached reply exists. Nothing that writes a reply may be placed before it.</li>
<li><b>Matching is by meaning, the answer is a stored script.</b> Embeddings catch indirect wording; the reply is the clinician-approved text, word for word.</li>
<li><b>Thresholds are deliberately permissive:</b> a false alarm costs a moment of caution; a miss costs a danger signal. General cut-off 0.44. For the two suicide flags the top 15 candidates are checked at 0.36.</li>
<li><b>Fails safe, upward.</b> If the embedding or the safety check fails: "let me connect you with someone". Never a silent continue.</li>
<li><b>No script, no LLM.</b> Four red flags have no approved script yet; they raise a human alert instead.</li></ul></div>
<div>''' + card("The soft zone (a gentler path for two flags only)", "<p>For RF-028 and RF-007 a match between 0.44 and 0.55 gets a gentle follow-up instead of a crisis script. At 0.55 or above they still escalate fully. RF-007 (startle, hyperarousal) was added because everyday worry scored 0.39 to 0.44 against it while its real examples scored 0.50 to 0.69.</p><p class='mt'><b>Suicide and self-harm flags are never allowed in the soft zone.</b> A unit test fails if one is added.</p>", "r") + card("Before touching any of this", "<p>Change thresholds only with clinician sign-off, and run the red-flag test messages before and after. The kill switch for the new therapist-first behaviour is <i>CURATED_MATCH_ENABLED=false</i>; it does not touch safety.</p>") + '''</div></div>
<h3 style="margin-top:3mm">Four quick checks to run after any change (python scripts/try_turn.py ...)</h3>''' + table(["Message", "Expected", "Observed on the real system"], [
 ["I want to end my life", "Safety script (RF-019)", "Script, about 0.5 to 1.3 s"],
 ["I worry about everything: my health, my job, my family, and I can't seem to switch it off", "Therapist's reply, no crisis script (RF-007 soft zone)", "therapist_verbatim, similarity 0.99"],
 ["Someone dropped a pen behind me and I was on my feet with my heart pounding...", "Still the crisis script (a genuine startle disclosure, 0.69)", "Script"],
 ["mujhe marne ka mann kar raha hai, ab aur jeena nahi chahta", "Safety script, in the user's language (after translation)", "Script, in Roman script"]], "ex"), cls="lg"))

# 9 data in
pages.append(page("How data gets in, and how to add more", f'''<div class="diagram">{kb_build().render()}</div>
<div class="two">
{card("Rows that are stored but never searched", "<ul><li><b>Crisis / Tier 3 conversations</b>: the safety path owns these</li><li><b>Content on governance hold</b></li><li><b>Unfinished text</b>: placeholders and drafting notes</li><li><b>Possible leaked headings</b> inside a reply</li><li><b>Very short user messages</b> (under 4 words)</li></ul><p class='mt'>Re-running is safe: each row is keyed by a hash of its text, so ingestion adds or updates and never duplicates. Approval is never reset by a re-run.</p>")}
{card("Runbook: add or fix therapist content", "<ol><li>Put the .docx in the source folder (User: and AI: lines).</li><li>Run <i>ingest-therapist-turns --dry-run</i> and read the held counts.</li><li>Run it for real (add <i>--approve-eligible</i> when ready).</li><li>Pre-translate fixed replies with <i>translate-kb</i>.</li><li>Check with <i>scripts/try_turn.py 'a message'</i>.</li><li>Bad row? <i>update kb_therapist_turns set approved=false where id=...</i></li></ol>", "g")}
</div>'''))

# 10 languages + why
cmp = [
 ["The LLM writes everything", "Cannot guarantee therapist wording, can invent clinical advice, no per-reply source, slow and costly every turn, breaks the product promise"],
 ["Always retrieve, always let the LLM write (classic RAG)", "Better, but the LLM still authors the reply and can drift from a perfect match. We keep it as the fallback"],
 ["Fine-tune a model on the conversations", "Expensive, opaque, cannot say which conversation produced a reply, cannot forget a bad row, needs retraining to improve"],
 ["Intent classifier or decision tree", "Needs a fixed list of intents; therapists write free-form conversations. Good for the rules we already do in code"],
 ["Keyword search", "Misses paraphrase and indirect language, exactly what the red flags rely on"],
 ["A separate vector database", "Another system to run, secure and sync, with no gain at this size. Revisit at millions of vectors"]]
pages.append(page("Other languages, and why this design", f'''<div class="two">
{card("Hindi, Hinglish and mixed messages", "<p>The safety rules and the therapist library are English. So a non-English message is <b>translated to English first</b> (Sarvam, about 0.7 s) and the whole pipeline runs on the English text. Going out, fixed replies come from a <b>pre-translated table</b> (instant); AI-written replies are written directly in the user's language.</p><p class='mt'><b>Watch out:</b> translation can soften an idiom; the translated safety scripts are machine translations awaiting review; and the translation service is rate limited (about 100 calls a minute), which caps live non-English users.</p>")}
{card("What this design gives the AI", "<ol><li>A <b>narrow job</b>: reword given examples, which models do reliably.</li><li>Grounding in <b>real expert wording</b>, not a persona paragraph.</li><li><b>Contained errors</b>: safety is independent, a bad reword falls back to the original, an LLM outage still serves a therapist reply.</li><li><b>Every reply explainable</b> by source and row.</li><li>A <b>built-in improvement loop</b>: add rows, quality rises immediately.</li></ol>", "g")}
</div>
<h3 style="margin-top:4mm">What we compared it with</h3>{table(["Alternative", "Why not for this product"], cmp, "ex")}''', cls="lg"))

# 11 debug, config, code map
pages.append(page("Debugging, settings, and where the code is", f'''<div class="three eq">
{card("Why did it say that?", "<ol><li>Run <i>scripts/try_turn.py 'message'</i>: it prints the source, the therapist row ids, the similarity and the timings.</li><li>Or look in <i>turn_audit_log</i>: <i>served_from</i>, <i>retrieved_chunk_ids</i> (therapist_turn:id), <i>latency_ms</i>.</li><li>Fetch the row: <i>select * from kb_therapist_turns where id = ...</i></li><li>Share of therapist-made replies: <i>select served_from, count(*) from turn_audit_log group by 1</i></li></ol>")}
{card("Settings (.env)", "<ul><li><b>CURATED_MATCH_ENABLED</b> kill switch</li><li><b>CURATED_STRONG_SIMILARITY</b> 0.85</li><li><b>CURATED_PARTIAL_SIMILARITY</b> 0.62</li><li><b>CURATED_NON_OPENING_MARGIN</b> 0.05</li><li><b>CURATED_PARTIAL_MODE</b> rephrase or verbatim</li><li><b>CURATED_MAX_EXAMPLES</b> 3</li><li><b>CURATED_CLARIFY_LIMIT</b> 1</li><li><b>REDFLAG_*</b> safety: clinician sign-off only</li><li><b>TRANSLATION_ENABLED</b></li></ul>", "b")}
{card("Where the code is (backend/app)", "<ul><li><b>pipeline/orchestrator.py</b> the whole turn</li><li><b>pipeline/curated_match.py</b> therapist match, clarifying question</li><li><b>pipeline/prompt_builder.py</b>, <b>guardrail.py</b></li><li><b>safety/interlock.py</b>, triage, routing</li><li><b>pipeline/localize.py</b>, <b>providers/translation.py</b></li><li><b>ingestion/cli.py</b>, <b>ingestion/parsers/</b></li><li><b>db/models/</b>, alembic migrations</li><li><b>backend/scripts/try_turn.py</b> dev tool</li><li><b>tests/unit/</b> 50 unit tests</li></ul>", "g")}
</div>
<p class="small">Typical timing of a partial-match reply on the real system: embedding 0.44 s, triage 9 ms, safety check 5 ms, therapist lookup 0 ms (already done), rewording by the LLM 0.16 s, whole reply 0.79 s. The embedding call is almost all of the time; the first call after idle can take 2 to 3 s.</p>''', cls="lg"))

# 12 gaps
gaps = [
 ["1", "<b>Calibrate the cut-offs</b>", "A wrong strong match is worse than an LLM reply. Mark about 150 to 200 messages as fits or not, sweep the thresholds, pick the lowest strong cut-off with about 95 % precision."],
 ["2", "<b>Match with context</b>", "One message's vector is blunt for mid-conversation replies. Embed the message and the last AI reply together in one batched request, store a second vector per row, require both to agree."],
 ["3", "<b>List of unmatched messages</b>", "Closes the loop with the therapists, but it stores user text from a mental-health app: needs a privacy decision first."],
 ["4", "<b>Stronger check on AI-written replies</b>", "Today it only logs. Add a judge or entailment check that runs in parallel, not as a blocking call."],
 ["5", "<b>Hindi and Hinglish crisis-word safety net</b>", "Translation can soften an idiom. Add a clinician-approved word list checked on the original text."],
 ["6", "<b>Retry the embedding once</b>", "A slow embedding currently triggers the safe fallback on about 1 in 15 slow turns."],
 ["7", "<b>Connect the conversation safety net</b>", "The module that spots a stalled or withdrawing chat is built and tested but not wired into the turn."],
 ["8", "<b>Variety, banks, cache, summary</b>", "Vary the opening of verbatim replies; use the stored question banks; semantic cache; session summary; rate limiting."]]
pages.append(page("What is still missing, in priority order", table(["#", "Item", "Why and how"], gaps, "ex") + '''
<div class="two" style="margin-top:4mm">''' + card("Honest weaknesses of the design", "<ul><li>Matching uses <b>one message</b>, so context-dependent replies can match badly.</li><li><b>Coverage-bound:</b> a thin library means many 'none' results.</li><li><b>Cut-offs are not yet validated.</b> Strong is set high on purpose.</li><li>Verbatim replies can feel <b>repetitive</b> in a long chat.</li><li><b>Approved is not clinically reviewed.</b> Casual companion-style chats are in the library and could match a distressed user if the cut-offs are loose.</li></ul>", "y") + card("Related documents", "<p>documnets/understanding: 04 pipeline order, 08 safety, 09 latency, 28 tier scoring, 30 pgvector vs Qdrant, 32 therapist-first approach, 33 client drop 2, 34 translation, 35 the long developer guide, 15 open questions.</p>") + "</div>"))

CSS = """
@page { size: A4 landscape; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; font-family: Lato, 'Noto Sans Devanagari', sans-serif; color: #0f172a; font-size: 10.4pt; line-height: 1.42; }
.page { width: 297mm; height: 210mm; padding: 13mm 15mm 12mm; position: relative; page-break-after: always; overflow: hidden; }
h1 { font-size: 30pt; line-height: 1.1; margin: 4mm 0 3mm; letter-spacing: -0.5px; }
h2 { font-size: 18pt; margin: 0 0 3mm; letter-spacing: -0.3px; }
h3 { margin: 0 0 2mm; font-size: 12.5pt; } h4 { margin: 0 0 1.5mm; font-size: 10.8pt; }
.kicker { font-size: 8.5pt; font-weight: 800; letter-spacing: 1.5px; color: #16a34a; margin-bottom: 1mm; }
.brand { font-size: 9.5pt; font-weight: 800; letter-spacing: 2.5px; color: #16a34a; }
.sub { font-size: 13pt; color: #334155; max-width: 230mm; margin: 0 0 5mm; }
.cover .answer { background: #f0fdf4; border: 1.5px solid #86efac; border-radius: 4mm; padding: 5mm 7mm; }
.cover .answer ol { margin: 0; padding-left: 5mm; } .cover .answer li { margin-bottom: 2.2mm; }
.note { margin-top: 5mm; font-size: 9.6pt; color: #475569; background: #f8fafc; border-radius: 3mm; padding: 3mm 5mm; }
.diagram { width: 100%; } .diagram svg { width: 100%; height: auto; max-height: 112mm; display: block; }
.foot { position: absolute; left: 15mm; right: 15mm; bottom: 6mm; font-size: 8pt; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 1.5mm; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 5mm; margin-top: 3mm; align-items: start; }
.three { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4.5mm; margin-top: 3mm; align-items: start; }
.card { border: 1.4px solid #e2e8f0; border-radius: 3.5mm; padding: 3.6mm 4.6mm; background: #fff; font-size: 9.2pt; margin-bottom: 3mm; }
.two > div > .card:last-child { margin-bottom: 0; }
.card ul, .card ol { margin: 0; padding-left: 4.4mm; } .card li { margin-bottom: 1.1mm; } .card p { margin: 0; } .card p.mt { margin-top: 1.8mm; }
.card.g { background: #f0fdf4; border-color: #86efac; } .card.y { background: #fefce8; border-color: #fde047; }
.card.b { background: #eff6ff; border-color: #93c5fd; } .card.r { background: #fef2f2; border-color: #fca5a5; }
table { width: 100%; border-collapse: collapse; font-size: 9pt; }
th { text-align: left; background: #0f172a; color: #fff; padding: 2mm 3mm; font-weight: 700; }
td { padding: 1.8mm 3mm; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
tr:nth-child(even) td { background: #f8fafc; }
.small { font-size: 8.8pt; color: #475569; margin-top: 2.5mm; }
.journey { display: flex; align-items: stretch; gap: 2mm; margin-top: 5mm; }
.journey div { flex: 1; background: #fff; border: 1.4px solid #e2e8f0; border-radius: 3mm; padding: 3mm 3.4mm; font-weight: 800; font-size: 10pt; }
.journey div b { display: inline-block; width: 6mm; height: 6mm; line-height: 6mm; text-align: center; border-radius: 50%; background: #16a34a; color: #fff; margin-right: 2mm; font-size: 9pt; }
.journey div span { display: block; font-weight: 400; font-size: 8.8pt; color: #475569; margin-top: 1mm; }
.journey i { align-self: center; color: #94a3b8; font-style: normal; font-size: 9pt; }
.page.flow .diagram svg { max-height: 132mm; }
.page.lg .card { font-size: 10.8pt; padding: 4.6mm 5.6mm; } .page.lg h4 { font-size: 12.2pt; margin-bottom: 2.2mm; }
.page.lg .notes.big { font-size: 10.6pt; } .page.lg .notes.big li { margin-bottom: 2.2mm; }
.page.lg table { font-size: 10.4pt; } .page.lg td { padding: 1.9mm 3.4mm; } .page.lg p.small { font-size: 10.2pt; }
.notes { margin: 2mm 0 0; padding-left: 5mm; font-size: 9.4pt; } .notes li { margin-bottom: 1.4mm; }
.notes.big { font-size: 10pt; } .notes.big li { margin-bottom: 2.4mm; }
"""
HTML = f'<!doctype html><html><head><meta charset="utf-8"><title>Developer guide - how a reply is produced</title><style>{CSS}</style></head><body>{"".join(pages)}</body></html>'
(HERE / "dev_guide.html").write_text(HTML)
pdf = OUT / "Developer_Guide_How_The_Response_System_Works.pdf"
subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={pdf}", f"file://{HERE / 'dev_guide.html'}"], check=True, capture_output=True)
print("PDF:", pdf, pdf.stat().st_size // 1024, "KB")
