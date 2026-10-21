from svgkit import Svg

LEGEND = [("RDS", "database tables"), ("VECTOR DB", "search by meaning"),
          ("REDIS", "live memory"), ("AI", "outside AI service")]


def part_a():
    s = Svg(1110, 690, 36)
    s.box(20, 50, 200, 100, "#0f172a", "#0f172a", ["1  The user sends", "a message"], ["typed in the app, or spoken", "(voice becomes text first)"], dark=True)
    s.box(255, 50, 215, 100, "#fff7ed", "#f97316", ["2  Remember the", "conversation so far"], ["last few messages and the", "running severity score"], [("REDIS", "live memory")])
    s.diamond(590, 100, 190, 120, "#f0fdfa", "#14b8a6", ["3  Another", "language?"])
    s.box(770, 50, 320, 100, "#faf5ff", "#a855f7", ['4  Make a "meaning vector"'], ["the message turned into numbers that", "capture its meaning. Done once and", "reused by every step below."], [("AI", "OpenAI embedding")])
    s.box(500, 205, 180, 100, "#f0fdfa", "#14b8a6", ["Translate to English"], ["so every step below", "understands the message"], [("AI", "Sarvam translation")])
    s.arrow([(220, 100), (255, 100)]); s.arrow([(470, 100), (495, 100)])
    s.arrow([(685, 100), (770, 100)], "no", (727, 88))
    s.arrow([(590, 160), (590, 205)], "yes", (612, 188))
    s.arrow([(680, 255), (930, 255), (930, 150)])
    s.box(770, 345, 320, 105, "#faf5ff", "#a855f7", ["6  Silent triage +", "severity score"], ["which signals and patterns are present?", "how serious has it been so far?"], [("VECTOR DB", ""), ("RDS", "signals, patterns, rules")])
    s.arrow([(1010, 150), (1010, 345)])
    s.box(770, 490, 320, 105, "#f0fdf4", "#22c55e", ["5  Look for a similar", "therapist conversation"], ["runs in the background while step 6", "runs; its result is used in Part B"], [("VECTOR DB", ""), ("RDS", "therapist conversations")])
    s.arrow([(1090, 100), (1102, 100), (1102, 542), (1090, 542)])
    s.diamond(590, 397, 210, 140, "#fef2f2", "#ef4444", ["7  SAFETY CHECK", "matches a", "red flag?"])
    s.arrow([(770, 397), (695, 397)])
    s.box(180, 335, 270, 125, "#fee2e2", "#ef4444", ["Approved safety script,", "word for word"], ["in the user's own language.", "No AI writing. Flagged for follow-up."], [("VECTOR DB", ""), ("RDS", "red flags + scripts")])
    s.arrow([(485, 397), (450, 397)], "yes", (467, 386))
    s.box(490, 520, 200, 85, "#e2e8f0", "#64748b", ["No red flag:", "continue to Part B"])
    s.arrow([(590, 467), (590, 520)], "no", (610, 497))
    s.legend(20, 672, LEGEND)
    return s


def part_b():
    s = Svg(1110, 772, 26)
    s.box(20, 50, 190, 85, "#e2e8f0", "#64748b", ["From Part A"], ["message understood,", "no red flag found"])
    s.diamond(400, 92, 230, 112, "#f0fdf4", "#22c55e", ["8  How close is the", "therapist match?"])
    s.arrow([(210, 92), (285, 92)])
    s.box(20, 215, 220, 120, "#dcfce7", "#16a34a", ["STRONG", "The therapist's reply,", "exactly as written"], ["the AI language model is", "not used at all"])
    s.box(270, 215, 300, 140, "#dcfce7", "#16a34a", ["PARTIAL", "AI rewords the therapists' replies"], ["sees a few close therapist examples and", "may add nothing new. If it drifts, the", "therapist's original reply is sent instead."], [("AI", "Sarvam language model")])
    s.diamond(830, 285, 240, 132, "#fefce8", "#eab308", ["NONE", "any other", "guidance found?"])
    s.arrow([(400, 148), (400, 185), (130, 185), (130, 215)], "strong", (265, 177))
    s.arrow([(400, 148), (400, 215)], "partial", (455, 203))
    s.arrow([(400, 148), (400, 185), (830, 185), (830, 219)], "none", (700, 177))
    s.box(555, 420, 250, 125, "#dcfce7", "#16a34a", ["Therapist-written", "clarifying question"], ['no advice: "tell me a little more".', "Asked once; then the AI may answer."], [("VECTOR DB", ""), ("RDS", "clarifying questions")])
    s.box(840, 420, 250, 140, "#fefce8", "#eab308", ["AI writes a short,", "careful reply"], ["uses therapist self-care advice or", "guidance if found. Suggests a", "practitioner if unsure or serious."], [("VECTOR DB", ""), ("RDS", "self-care"), ("AI", "language model")])
    s.arrow([(830, 351), (830, 388), (680, 388), (680, 420)], "nothing found", (755, 380))
    s.arrow([(830, 351), (830, 388), (965, 388), (965, 420)], "found", (905, 380))
    # bus into step 9
    s.arrow([(420, 355), (420, 592), (130, 592)], head=False)
    s.arrow([(680, 545), (680, 592), (420, 592)], head=False)
    s.arrow([(965, 560), (965, 592), (680, 592)], head=False)
    s.arrow([(130, 335), (130, 628)])
    s.box(20, 628, 270, 92, "#f0fdfa", "#14b8a6", ["9  Reply in the user's", "own language"], ["fixed replies come from a", "pre-translated table: instant"], [("RDS", "translations")])
    s.box(320, 628, 230, 92, "#0f172a", "#0f172a", ["10  Reply is delivered"], ["streamed as text, or", "spoken aloud (voice)"], dark=True)
    s.box(580, 628, 270, 92, "#eff6ff", "#3b82f6", ["11  Record the turn"], ["memory updated, plus an audit trail:", "which path answered, what matched"], [("REDIS", ""), ("RDS", "audit log")])
    s.arrow([(290, 674), (320, 674)]); s.arrow([(550, 674), (580, 674)])
    s.legend(20, 760, LEGEND)
    return s


def system():
    s = Svg(1110, 650, 36)
    s.box(20, 215, 140, 100, "#0f172a", "#0f172a", ["The user"], ["on a phone or the web;", "types or speaks"], dark=True)
    s.cluster(190, 55, 275, 395, "#ffffff", "#94a3b8", "Apps and backend", "(other team)", dashed=True)
    s.box(210, 90, 235, 80, "#f8fafc", "#94a3b8", ["Product backend"], ["NestJS: login, bookings,", "practitioner features"])
    s.box(210, 205, 235, 75, "#f8fafc", "#94a3b8", ["Mobile + web app"], ["Flutter / Next.js"])
    s.box(210, 330, 235, 90, "#eff6ff", "#3b82f6", ["LiveKit"], ["carries the live voice call"])
    s.cluster(495, 55, 300, 340, "#f0fdf4", "#22c55e", "THE AI SERVICE", "(Python / FastAPI)")
    s.box(515, 100, 260, 95, "#fee2e2", "#ef4444", ["Safety check"], ["always first, on every message", "cannot be skipped"])
    s.box(515, 245, 260, 125, "#ffffff", "#22c55e", ["Response engine"], ["triage, therapist-conversation", "match, chooses where the", "reply comes from"])
    s.cluster(835, 55, 255, 340, "#eff6ff", "#3b82f6", "YOUR DATA", "(AWS Mumbai)")
    s.box(855, 95, 215, 150, "#ffffff", "#3b82f6", ["PostgreSQL database", "(RDS)"], ["with built-in vector search", "(pgvector): one database,", "two jobs. Knowledge Base,", "therapist conversations,", "safety rules, audit log"])
    s.box(855, 290, 215, 85, "#ffffff", "#f97316", ["Redis"], ["live conversation memory,", "short-term reply cache"])
    s.cluster(495, 430, 595, 185, "#f0fdfa", "#14b8a6", "OUTSIDE AI SERVICES", "(swappable behind adapters)")
    s.box(515, 470, 265, 120, "#ffffff", "#14b8a6", ["Sarvam AI"], ["speech to text, text to speech,", "the language model, translation"])
    s.box(815, 470, 255, 120, "#ffffff", "#a855f7", ["OpenAI"], ['"embeddings": turn text into', "meaning vectors for searching"])
    s.arrow([(160, 265), (210, 245)], both=True)
    s.arrow([(327, 205), (327, 170)], both=True)
    s.text(338, 192, "messages, login", 11, 700, "#334155")
    s.arrow([(327, 280), (327, 330)], dashed=True)
    s.text(338, 310, "voice", 11, 700, "#334155")
    s.arrow([(445, 130), (515, 140)], "text", (480, 126), both=True)
    s.arrow([(445, 375), (475, 375), (475, 178), (515, 178)], dashed=True, both=True)
    s.text(481, 300, "voice", 11, 700, "#334155")
    s.arrow([(645, 195), (645, 245)])
    s.arrow([(775, 150), (855, 150)], both=True)
    s.arrow([(775, 290), (815, 290), (815, 200), (855, 200)], both=True)
    s.arrow([(775, 335), (855, 335)], both=True)
    s.arrow([(600, 370), (600, 470)], "write, translate, speak", (600, 420), both=True)
    s.arrow([(720, 370), (720, 412), (940, 412), (940, 470)], "embed", (830, 404))
    s.text(870, 273, "search + read", 11, 700, "#334155")
    s.legend(20, 640, LEGEND[:4])
    return s


def kb_build(ok=5230, total=6440):
    s = Svg(1110, 615, 36)
    xs = [20, 300, 580, 860]
    W = 230
    s.box(xs[0], 55, W, 190, "#0f172a", "#0f172a", ["Your team's files"], ["clinical sheets (Excel / CSV)", "Word documents", "therapist conversations", "self-care tools"], dark=True)
    s.box(xs[1], 55, W, 190, "#fff7ed", "#f97316", ["1  Read and clean"], ["a reader for each file type;", "conversations are split into", '"user said / therapist replied"', "pairs; duplicates removed"])
    s.box(xs[2], 55, W, 190, "#fef2f2", "#ef4444", ["2  Safety gates"], ["held back, never used for a reply:", "crisis conversations, unfinished", "text, sensitive content on hold,", "one-word messages"])
    s.box(xs[3], 55, W, 190, "#eff6ff", "#3b82f6", ["3  Saved in the", "database (RDS)"], ["every row keeps its source file,", "author, tier and status"], [("RDS", "")])
    for i in range(3):
        s.arrow([(xs[i] + W, 150), (xs[i + 1], 150)])
    s.arrow([(xs[3] + W / 2, 245), (xs[3] + W / 2, 315)])
    s.box(xs[3], 315, W, 190, "#faf5ff", "#a855f7", ["4  Meaning vector", "added"], ["OpenAI turns each text into", "numbers capturing its meaning;", "saved beside the row with a", "fast search index"], [("VECTOR DB", "same database"), ("AI", "OpenAI")])
    s.box(xs[2], 315, W, 190, "#f0fdf4", "#22c55e", ["5  Approved for use"], ["only approved, eligible rows can", "ever be found by a search.", "Today: only approved therapist", "replies are used"])
    s.arrow([(xs[3], 410), (xs[2] + W, 410)]); s.arrow([(xs[2], 410), (xs[1] + W, 410)])
    s.box(xs[1], 315, W, 190, "#dcfce7", "#16a34a", ["Result:", "a searchable", "Knowledge Base"], ["ready for the live flow"])
    s.legend(20, 560, LEGEND[:4])
    s.text(20, 598, "Re-run whenever your team adds or changes files: it only adds what is new.", 12, 400, "#475569")
    return s


def rds_vector(total=6440):
    s = Svg(1110, 565, 0)
    # left: message -> vector
    s.box(20, 30, 250, 125, "#0f172a", "#0f172a", ["The user's message"], ['"I just moved to a new city', 'for college and I feel so alone,', 'I don\'t know anyone here"'], dark=True)
    s.arrow([(145, 155), (145, 215)])
    s.box(20, 215, 250, 150, "#faf5ff", "#a855f7", ["1  Turn it into a", "meaning vector"], ["a long list of numbers that", "captures what it means.", "Similar meanings give", "similar numbers."], [("AI", "OpenAI embedding")])
    # middle cluster
    s.cluster(305, 20, 545, 505, "#eff6ff", "#3b82f6", "ONE POSTGRESQL DATABASE (RDS)", "with built-in vector search")
    s.text(325, 62, "2  Vector search: the message's vector is compared with the vector stored beside", 12, 700, "#7e22ce")
    s.text(325, 79, "every row; the closest rows are picked (closer = more similar meaning).", 12, 700, "#7e22ce")
    # table
    tx, ty = 325, 100
    s.rect(tx, ty, 505, 36, "#0f172a", rx=6)
    s.text(tx + 12, ty + 15, "Therapist conversations table", 12, 800, "#ffffff")
    s.text(tx + 12, ty + 29, "every conversation your therapists wrote", 10.5, 400, "#cbd5e1")
    colA, colB, colC = tx, tx + 180, tx + 365
    s.rect(tx, ty + 38, 505, 28, "#e2e8f0", rx=0)
    s.text(colA + 12, ty + 57, "What the user said", 11, 800, "#1d4ed8"); s.text(colB + 12, ty + 57, "Therapist's reply", 11, 800, "#1d4ed8"); s.text(colC + 12, ty + 57, "Meaning vector", 11, 800, "#7e22ce")
    rows = [
        (["I miss my home, my family and", "my friends. I don't know anyone", "in this city. It is so hard..."], ["It sounds like you feel homesick", "and lonely in the new place.", "How can I help you?"], "0.66", "Homesickness"),
        (["I've recently moved to a new city", "for work and I'm really struggling.", "I thought I'd be excited..."], ["hey thanks for sharing that. Can", "you tell me more about the", "hardest part for you so far?"], "0.66", "Bipolar/transition issues"),
        (["I moved here for university about", "three months ago. At first I was", "excited because it felt like..."], ["Looks like you've been feeling", "lonely, while at the same time you", "have been avoiding people. Would..."], "0.65", "No friends"),
    ]
    y = ty + 70
    for ua, ra, sim, about in rows:
        s.rect(tx, y, 505, 76, "#ffffff", "#93c5fd", rx=0, sw=1.2)
        s.rect(colC, y, 140, 76, "#faf5ff", "#d8b4fe", rx=0, sw=1.2)
        s.mtext(colA + 12, y + 20, ua, 11, 400, "#0f172a"); s.mtext(colB + 12, y + 20, ra, 11, 400, "#0f172a")
        s.text(colC + 12, y + 22, "close match", 11, 800, "#7e22ce")
        s.rect(colC + 12, y + 31, 110, 9, "#e9d5ff", rx=4); s.rect(colC + 12, y + 31, 110 * float(sim), 9, "#a855f7", rx=4)
        s.text(colC + 12, y + 56, "[ vector ]", 10.5, 400, "#7e22ce"); s.text(colC + 12, y + 68, about, 10, 400, "#475569")
        y += 76
    s.rect(tx, y, 505, 30, "#f8fafc", "#cbd5e1", rx=0, sw=1.2)
    s.text(tx + 252, y + 20, "... many more rows, each with its own vector, ranked further away", 11, 400, "#64748b", "middle")
    s.text(325, y + 54, "3  The same query returns the full text of those rows from the ordinary columns (RDS).", 12, 700, "#1d4ed8")
    s.text(325, y + 71, "Text and vectors live in one table, so they can never fall out of step.", 12, 400, "#334155")
    s.text(325, y + 100, "Only rows that are approved and eligible are ever searched (see page 5).", 12, 400, "#334155")
    # right
    s.box(885, 110, 205, 290, "#f0fdf4", "#22c55e", ["4  The reply engine", "uses the closest rows"], ["", "Very close:", "the top row's reply is sent", "exactly as written", "", "Fairly close:", "a few rows are shown to", "the AI, which rewords them", "", "Not close:", "a clarifying question, or a", "short careful AI reply"])
    s.arrow([(270, 290), (305, 290)], "compare", (288, 278), lsize=11)
    s.arrow([(830, 255), (885, 255)])
    s.legend(20, 552, LEGEND[:3])
    return s


if __name__ == "__main__":
    import sys
    for name, fn in (("d2_rds_vector", rds_vector), ("d1_system", system), ("d3_kb_build", kb_build), ("d4a_receive_and_safety", part_a), ("d4b_choose_and_deliver", part_b)):
        open(f"{name}.svg", "w").write(fn().render())
    print("ok")
