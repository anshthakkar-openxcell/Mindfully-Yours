"""Builds Mindfully_Yours_AI_Response_Flow.pdf: diagrams (svgkit/diagrams.py) + client-facing pages -> HTML -> headless Chrome.
Numbers come straight from the live database so nothing in the PDF is typed from memory."""
import datetime
import pathlib
import subprocess

from diagrams import kb_build, part_a, part_b, rds_vector, system

HERE = pathlib.Path(__file__).parent
OUT = HERE.parent


def q(sql):
    r = subprocess.run(["docker", "exec", "mindfully_postgres", "psql", "-U", "mindfully", "-d", "mindfully_ai", "-At", "-F", "|", "-c", sql],
                       capture_output=True, text=True, check=True)
    return [line.split("|") for line in r.stdout.strip().splitlines()]


def n(table, where=""):
    return int(q(f"select count(*) from {table} {where}")[0][0])


C = {
    "red_flags": n("kb_red_flags"), "signals": n("kb_signals"), "symptoms": n("kb_symptoms"),
    "patterns": n("kb_sufficiency_patterns"), "rules": n("kb_routing_rules"), "fallback": n("kb_fallback_scenarios"),
    "turns": n("kb_therapist_turns"), "turns_ok": n("kb_therapist_turns", "where approved"),
    "clar": n("kb_clarification_phrases"), "selfcare": n("kb_content_chunks", "where content_type='self_care_tool'"),
    "situations": n("kb_situational_routing"), "welcome": n("kb_welcome_responses", "where approved"),
    "trans": n("kb_translations"), "layers": n("kb_layer_content"), "emotions": n("kb_emotion_phrases"),
    "scenarios": n("kb_scenarios"), "tierq": n("kb_tier_question_bank"),
}


def f(v):
    return f"{v:,}"


SEARCHABLE = C["turns"] + C["signals"] + C["symptoms"] + C["patterns"] + C["layers"] + C["scenarios"] + C["emotions"] + C["tierq"]
TODAY = datetime.date(2026, 10, 9).strftime("%d %B %Y")
PAGE_NO = [1]


def page(title, body, kicker=""):
    PAGE_NO[0] += 1
    k = f'<div class="kicker">{kicker}</div>' if kicker else ""
    return (f'<section class="page">{k}<h2>{title}</h2>{body}'
            f'<div class="foot">Mindfully Yours  -  How the AI produces a reply  -  page {PAGE_NO[0]}</div></section>')


def chips(*kinds):
    cls = {"RDS": "c-rds", "VECTOR": "c-vec", "REDIS": "c-red", "AI": "c-ai"}
    return " ".join(f'<span class="chip {cls[k.split()[0]]}">{k}</span>' for k in kinds)


def table(headers, rows, cls=""):
    th = "".join(f"<th>{h}</th>" for h in headers)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'


pages = []

# 1 ---- cover
pages.append(f'''<section class="page cover">
<div class="brand">MINDFULLY YOURS</div>
<h1>How the AI produces a reply</h1>
<p class="sub">The flow from a user's message, through your Knowledge Base and therapist conversations, the database and the AI, to the reply the user receives.</p>
<div class="meta">Prepared for the Mindfully Yours clinical and product team &nbsp;|&nbsp; Version 1.0</div>
<div class="answer">
<h3>The short answer</h3>
<ol>
<li><b>Your therapists' conversations come first.</b> Every message is compared, by meaning, with the approved therapist replies in the library. When one fits, the user gets <i>your therapist's reply</i>, as written or lightly reworded. The AI language model writes a reply on its own only when nothing in the library fits, and then it stays short and careful.</li>
<li><b>Safety is checked first, every time.</b> A message that matches a red flag gets your team's approved script, word for word. No AI writing is involved.</li>
<li><b>One PostgreSQL database does two jobs.</b> The ordinary tables (the RDS) hold the text, rules and scripts; the vector search (pgvector) inside the same database finds the closest match by meaning. They are not two separate systems.</li>
<li><b>Users in other languages get the same treatment</b>: the message is translated for the safety check and the search, and the reply comes back in their own language.</li>
</ol></div>
<div class="stats">
<div><b>Therapists first</b><span>approved therapist replies are searched before anything else</span></div>
<div><b>Safety first</b><span>every message is checked against the red flags</span></div>
<div><b>Your language</b><span>users in other languages get the same care</span></div>
<div><b>One database</b><span>PostgreSQL holds both the tables and the vector search</span></div>
</div>
<div class="note">This document describes the approach: how a user's message is understood, how the Knowledge Base and the therapist conversations are searched, and how the reply is chosen and delivered.</div>
</section>''')

# 2 ---- system
pages.append(page("The system at a glance", f'<div class="diagram">{system().render()}</div><p class="small">Hosting: the architecture places the database and services in AWS Mumbai (India) for data residency. The outside AI services can be swapped behind adapters, with your written consent.</p>'))

# 3 ---- RDS + vector
pages.append(page("RDS and the vector database, working together on one question", f'''
<div class="diagram">{rds_vector(C["turns"]).render()}</div>
<p class="small">This is a real example from the running system. The user's message is turned into a meaning vector, compared with the vector stored beside each therapist conversation, and the closest rows come back together with their full text. The three closest rows are all about moving to a new place and struggling with it, even though none uses the same words.</p>'''))

# 4 ---- what is stored where
rows = [
    ["Safety red flags and approved scripts (with translated copies)", chips("RDS", "VECTOR"), "Safety check (step 7)"],
    ["Signals people express, and symptoms", chips("RDS", "VECTOR"), "Triage (step 6)"],
    ["Patterns and how to keep probing", chips("RDS", "VECTOR"), "Triage; guidance for the AI"],
    ["Rules: when something counts as Tier 1, 2 or 3", chips("RDS"), "Triage (read by code, not searched)"],
    ["<b>Therapist conversations</b> (user said / therapist replied); only approved ones are searched", chips("RDS", "VECTOR"), "Therapist match (steps 5, 8)"],
    ["Therapist clarifying questions (the general ones are used)", chips("RDS", "VECTOR"), "When nothing matches (step 8)"],
    ["Self-care advice for everyday situations", chips("RDS", "VECTOR"), "Guidance for the AI (step 8)"],
    ["Welcome messages", chips("RDS"), "Start of a conversation"],
    ["Audit trail of every reply", chips("RDS"), "Record the turn (step 11)"],
    ["Live conversation memory; short-term reply cache", chips("REDIS"), "Steps 2 and 11"],
]
pages.append(page("What is stored where", table(["What it is", "Where it lives", "Used by"], rows, "data") + f'''
<p class="small"><b>RDS</b> = stored as ordinary rows of text and rules. <b>VECTOR</b> = also given a meaning vector so it can be searched by meaning. <b>REDIS</b> = fast short-lived memory, not permanent storage.</p>'''))

# 5 ---- KB build
pages.append(page("How the Knowledge Base gets into the database", f'''
<div class="diagram">{kb_build(C["turns_ok"], C["turns"]).render()}</div>
<p class="small">Your team's files are read once, checked, saved, given meaning vectors and approved. Rows that could be unsafe or unfinished are kept in the database but are never searchable (no vector, not approved): crisis conversations (the safety check owns those), unfinished text, content on governance hold, and one-word messages that would match anything. The loads so far cover the clinical sheets, the question banks, the self-care tools and the therapist conversations.</p>'''))


# 6 ---- ladder
def rung(n_, color, title, when, who):
    return (f'<div class="rung" style="border-left-color:{color}"><div class="num" style="background:{color}">{n_}</div>'
            f'<div class="rb"><b>{title}</b><span>{when}</span></div><div class="who">{who}</div></div>')


pages.append(page("Where does the reply come from?", f'''
<p class="lead">There are five possible sources for a reply. They are tried in this order, and the first one that applies is used. The closer the match, the more the reply is purely your therapists' words.</p>
<div class="ladder">
{rung(1, "#ef4444", "Approved safety script, word for word", "A red flag is detected in the message", "Your team's words only")}
{rung(2, "#16a34a", "The therapist's reply, exactly as written", "A very close match in the library (a strong match)", "Your therapists' words only. The AI is not used.")}
{rung(3, "#4ade80", "The therapists' replies, lightly reworded", "A fair match (a partial match)", "The AI sees a few close therapist examples and may add nothing new")}
{rung(4, "#22c55e", "A therapist-written clarifying question", "Nothing matches, and nothing else can guide the reply", "Your therapists' words only")}
{rung(5, "#eab308", "A short, careful AI reply", "Still nothing that fits", "AI language model, with self-care advice if found; suggests a practitioner when unsure")}
</div>
<div class="two"><div class="card"><h4>What "close" means</h4><p>Every message and every therapist conversation is turned into a meaning vector. "How close" is a similarity score between the two. The cut-offs between strong, partial and none are <b>provisional starting values</b>, set conservatively so that "exactly as written" is only used for very clear matches. They are meant to be set with your therapists, using a sample of messages they mark as "fits" or "does not fit".</p></div>
<div class="card"><h4>Always true</h4><ul><li>The safety check runs before everything else.</li><li>The AI never decides whether something is a crisis.</li><li>Every reply is recorded with which of the five sources produced it, so the share coming from your therapists can be reported.</li></ul></div></div>'''))

# 7, 8 ---- the flow chart
pages.append(page("Step by step, part A: message in, safety checked", f'<div class="diagram">{part_a().render()}</div>', "THE FLOW CHART"))
pages.append(page("Step by step, part B: choosing the reply and sending it", f'<div class="diagram">{part_b().render()}</div>', "THE FLOW CHART"))

# 9 ---- RAG
pages.append(page("What the AI language model sees (the RAG step)", '''
<p class="lead"><b>RAG</b> means <i>retrieve, then generate</i>: first the system <b>retrieves</b> the relevant material from the database; only then is the AI asked to <b>write</b> a reply using that material. The AI is never asked to work from memory alone.</p>
<div class="three">
<div class="card g"><h4>Always given to the AI</h4><ul>
<li>The persona and tone (warm, calm, non-clinical)</li>
<li>The language to reply in</li>
<li>A short checklist of what to quietly notice (the Clinical Markers)</li>
<li>The last few messages of this conversation</li>
<li>The user's message</li></ul></div>
<div class="card b"><h4>Plus one kind of retrieved material</h4><ul>
<li><b>Close therapist examples</b> (a few) when the match is partial</li>
<li><b>Self-care advice</b> found by searching for the user's situation</li>
<li><b>Therapist probing guidance</b> for the closest pattern</li>
<li>A gentle <b>booking suggestion</b>, once concern has persisted and its duration and impact are clear</li>
<li>A therapist <b>follow-up question</b> for a possible concern</li></ul></div>
<div class="card r"><h4>The AI is never asked to</h4><ul>
<li>decide whether a message is a crisis (the safety check does that)</li>
<li>add advice to a matched therapist reply</li>
<li>work from other users' conversations</li>
<li>diagnose, or name a clinical condition to the user</li></ul></div></div>
<div class="two" style="margin-top:0">
<div class="card"><h4>Checked before the user sees it</h4><p>When the AI rewords therapist replies, the result is checked: it must reuse the therapists' own wording, add no numbers or links, and stay about as short. If it drifts, the therapist's original reply is sent instead.</p></div>
<div class="card mono"><h4>A real example of what the AI is shown (shortened), for a partial match</h4>
<p><i>Real examples from our therapist team, closest first:</i><br>1. When someone said: "I miss my home, my family and my friends. I don't know anyone in this city..."<br>&nbsp;&nbsp;&nbsp;&nbsp;the therapist replied: "It sounds like you feel homesick and lonely in the new place. How can I help you?"<br>2. When someone said: "I've recently moved to a new city for work and I'm really struggling..."<br>&nbsp;&nbsp;&nbsp;&nbsp;the therapist replied: "hey thanks for sharing that. Can you tell me more about the hardest part for you so far?"<br><i>Write ONE reply, using ONLY the ideas, wording and questions already in the therapist replies. Do NOT add advice or facts that are not in them.</i><br>The user just said: "I just moved to a new city for college and I feel so alone..."<br><b>The AI wrote:</b> "It sounds like you feel alone in the new place. How can I help you?"</p></div></div>'''))

# 10 ---- examples
ex = [
    ['"Hi, I just moved away from my home last month, and things have not been easy ever since."', "Very close (strong)", "Therapist's reply, as written", '"Moving away from home can be quite tough. What about this move has been the most difficult for you?"', "about 1 s"],
    ['"I just moved to a new city for college and I feel so alone, I don\'t know anyone here"', "Fair (partial)", "Therapists' replies, lightly reworded", '"It sounds like you feel alone in the new place. How can I help you?"', "about 1 to 1.5 s"],
    ['"I just don\'t really know how to put this into words"', "None", "Therapist clarifying question", '"I\'m not completely sure I understand what you mean. Could you tell me a little more?"', "under 1 s"],
    ['"my teenage son won\'t talk to me anymore"', "None", "Short careful AI reply", '"Oh, that sounds really heavy, and I can hear how much it hurts you. It takes so much patience to watch someone you love pull away..."', "about 1.5 to 2.5 s"],
]
pages.append(page("Worked examples from the running system", table(["What the user said", "How close", "Where the reply came from", "What the user received"], [r[:4] for r in ex], "ex") +
                  '<p class="small">These are test messages run through the real pipeline (not user data). Messages in other languages take slightly longer because of the translation step.</p>'))

# 11 ---- status
dec = ["When a match is only partial: should the AI reword the therapists' replies (the current design) or send them as written?", "Is one clarifying question before any AI reply the right amount?", "A few therapists' time to mark a sample of messages as fits or does not fit, to set the match cut-offs", "A clinician to review the translated safety scripts, and the gentler handling of one trauma-symptom flag", "Who wrote the therapist replies that do not name an author?", "Keep the vector search inside the same PostgreSQL (recommended at this size), or use a separate vector database later?"]
gl = [("RDS", "The managed PostgreSQL database that stores all the written content."), ("Vector database / pgvector", "The part of that database that finds the closest match by meaning."), ("Meaning vector (embedding)", "A list of numbers that captures what a sentence means, so similar meanings sit close together."), ("RAG", "Retrieve relevant material first, then let the AI write using it."), ("Redis", "Fast, short-lived memory for the current conversation."), ("Tier 1 / 2 / 3", "Self-care, professional support, immediate crisis support."), ("Red flag", "A message pattern that needs your approved safety script immediately."), ("Triage", "Quietly reading each message for signals and how serious things are.")]
CSS = """
@page { size: A4 landscape; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; font-family: Lato, 'Noto Sans Devanagari', sans-serif; color: #0f172a; font-size: 10.4pt; line-height: 1.42; }
.page { width: 297mm; height: 210mm; padding: 13mm 15mm 12mm; position: relative; page-break-after: always; overflow: hidden; }
h1 { font-size: 30pt; line-height: 1.1; margin: 4mm 0 3mm; letter-spacing: -0.5px; }
h2 { font-size: 18pt; margin: 0 0 4mm; letter-spacing: -0.3px; }
h3 { margin: 0 0 2mm; font-size: 13pt; } h4 { margin: 0 0 1.5mm; font-size: 11pt; }
.kicker { font-size: 8.5pt; font-weight: 800; letter-spacing: 1.5px; color: #16a34a; margin-bottom: 1mm; }
.brand { font-size: 10pt; font-weight: 800; letter-spacing: 3px; color: #16a34a; }
.sub { font-size: 13pt; color: #334155; max-width: 215mm; margin: 0 0 3mm; }
.meta { font-size: 9.5pt; color: #64748b; margin-bottom: 6mm; }
.cover .answer { background: #f0fdf4; border: 1.5px solid #86efac; border-radius: 4mm; padding: 5mm 7mm; }
.cover .answer ol { margin: 0; padding-left: 5mm; } .cover .answer li { margin-bottom: 2mm; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4mm; margin-top: 5mm; }
.stats div { border: 1.4px solid #e2e8f0; border-radius: 3mm; padding: 3mm 4mm; background: #fff; }
.stats b { display: block; font-size: 14pt; color: #16a34a; line-height: 1.1; } .stats span { font-size: 8.8pt; color: #475569; }
.note { margin-top: 5mm; font-size: 9.5pt; color: #475569; background: #f8fafc; border-radius: 3mm; padding: 3mm 5mm; }
.lead { font-size: 11.5pt; margin: 0 0 4mm; max-width: 250mm; color: #1e293b; }
.diagram { width: 100%; } .diagram svg { width: 100%; height: auto; max-height: 160mm; display: block; }
.foot { position: absolute; left: 15mm; right: 15mm; bottom: 6mm; font-size: 8pt; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 1.5mm; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 5mm; margin-top: 4mm; }
.three { display: grid; grid-template-columns: 1fr 1.25fr 1fr; gap: 5mm; margin: 3mm 0 4mm; }
.card { border: 1.4px solid #e2e8f0; border-radius: 3.5mm; padding: 4mm 5mm; background: #fff; font-size: 9.6pt; }
.card ul, .card ol { margin: 0; padding-left: 4.5mm; } .card li { margin-bottom: 1.2mm; } .card p { margin: 0; }
.card.g { background: #f0fdf4; border-color: #86efac; } .card.y { background: #fefce8; border-color: #fde047; }
.card.b { background: #eff6ff; border-color: #93c5fd; } .card.r { background: #fef2f2; border-color: #fca5a5; }
dl { margin: 0; } dt { font-weight: 800; font-size: 9.4pt; } dd { margin: 0 0 1.3mm; color: #334155; font-size: 9.2pt; }
table { width: 100%; border-collapse: collapse; font-size: 9.2pt; }
th { text-align: left; background: #0f172a; color: #fff; padding: 2.2mm 3mm; font-weight: 700; }
td { padding: 1.7mm 3mm; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
tr:nth-child(even) td { background: #f8fafc; }
.ex td { font-size: 8.9pt; } .dev { font-family: 'Noto Sans Devanagari', sans-serif; }
.chip { display: inline-block; font-size: 7.4pt; font-weight: 800; padding: 0.6mm 2mm; border-radius: 3mm; margin-right: 1mm; border: 1px solid; }
.c-rds { color: #1d4ed8; background: #eff6ff; border-color: #93c5fd; } .c-vec { color: #7e22ce; background: #faf5ff; border-color: #d8b4fe; }
.c-red { color: #c2410c; background: #fff7ed; border-color: #fdba74; } .c-ai { color: #0f766e; background: #f0fdfa; border-color: #5eead4; }
.small { font-size: 8.8pt; color: #475569; margin-top: 3mm; }
.ladder { display: flex; flex-direction: column; gap: 2.2mm; }
.rung { display: grid; grid-template-columns: 11mm 1fr 82mm; align-items: center; gap: 4mm; border: 1.4px solid #e2e8f0; border-left-width: 2.6mm; border-radius: 3mm; padding: 2.6mm 4mm; background: #fff; }
.rung .num { width: 8mm; height: 8mm; border-radius: 50%; color: #fff; font-weight: 800; display: flex; align-items: center; justify-content: center; }
.rung .rb b { display: block; font-size: 10.8pt; } .rung .rb span { font-size: 9.2pt; color: #475569; }
.rung .who { font-size: 9pt; color: #334155; background: #f8fafc; border-radius: 2mm; padding: 1.6mm 2.4mm; }
.three.eq { grid-template-columns: 1fr 1fr 1fr; margin: 0 0 4mm; } .three.eq .card { font-size: 8.6pt; padding: 3.2mm 4mm; } .three.eq li { margin-bottom: 0.9mm; }
.card.gl dl { display: grid; grid-template-columns: repeat(4, 1fr); gap: 2mm 6mm; } .card.gl dt { font-size: 8.4pt; } .card.gl dd { font-size: 8pt; margin: 0; }
.card.dec { margin-bottom: 5mm; font-size: 10.4pt; } .card.dec li { margin-bottom: 2.4mm; }
.card.mono p { font-size: 8.4pt; line-height: 1.36; }
"""
HTML = (f'<!doctype html><html><head><meta charset="utf-8"><title>How the AI produces a reply - Mindfully Yours</title>'
        f'<style>{CSS}</style></head><body>{"".join(pages)}</body></html>')
(HERE / "AI_Response_Flow.html").write_text(HTML)
pdf = OUT / "Mindfully_Yours_AI_Response_Flow.pdf"
subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={pdf}", f"file://{HERE / 'AI_Response_Flow.html'}"], check=True, capture_output=True)
print("PDF:", pdf, pdf.stat().st_size // 1024, "KB")
