"""Developer-guide-only diagrams. Reuses the SVG kit and the shared diagrams from the client PDF's source folder."""
import pathlib
import sys

CLIENT_SRC = pathlib.Path(__file__).resolve().parents[2] / "Client Presentation" / "AI Response Flow" / "source"
sys.path.insert(0, str(CLIENT_SRC))
from svgkit import Svg  # noqa: E402
from diagrams import kb_build, part_a, part_b, rds_vector, system  # noqa: E402,F401


def bands():
    """The similarity scale: where 'none', 'partial' and 'strong' sit, with real examples plotted."""
    s = Svg(1110, 330, 0)
    x0, x1, lo, hi = 60, 1050, 0.40, 1.00
    X = lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)  # noqa: E731
    y, h = 160, 64
    s.rect(X(0.40), y, X(0.62) - X(0.40), h, "#fef2f2", "#fca5a5", rx=0, sw=1.6)
    s.rect(X(0.62), y, X(0.85) - X(0.62), h, "#fefce8", "#fde047", rx=0, sw=1.6)
    s.rect(X(0.85), y, X(1.00) - X(0.85), h, "#dcfce7", "#86efac", rx=0, sw=1.6)
    s.text((X(0.40) + X(0.62)) / 2, y + 26, "NONE", 15, 800, "#991b1b", "middle")
    s.text((X(0.40) + X(0.62)) / 2, y + 44, "below 0.62", 12, 400, "#7f1d1d", "middle")
    s.text((X(0.62) + X(0.85)) / 2, y + 26, "PARTIAL", 15, 800, "#854d0e", "middle")
    s.text((X(0.62) + X(0.85)) / 2, y + 44, "0.62 to 0.85", 12, 400, "#713f12", "middle")
    s.text((X(0.90) + X(1.00)) / 2 + 6, y + 26, "STRONG", 15, 800, "#166534", "middle")
    s.text((X(0.90) + X(1.00)) / 2 + 6, y + 44, "0.85 and above", 12, 400, "#14532d", "middle")
    # axis ticks
    for i in range(0, 7):
        v = 0.40 + i * 0.10
        s.text(X(v), y + h + 20, f"{v:.1f}", 11, 400, "#64748b", "middle")
    # mid-conversation strong boundary
    s.arrow([(X(0.90), y - 8), (X(0.90), y + h + 4)], dashed=True, color="#16a34a", head=False)
    s.text(X(0.90), y - 14, "0.90 if the row is mid-conversation", 11, 700, "#16a34a", "middle")
    # explanation under each zone
    s.mtext(X(0.40) + 8, y + h + 46, ["ask a therapist question,", "then (only then) the LLM"], 12, 400, "#7f1d1d")
    s.mtext(X(0.62) + 8, y + h + 46, ["LLM rewords a few close", "therapist examples (checked)"], 12, 400, "#713f12")
    s.mtext(X(0.85) + 8, y + h + 46, ["therapist's reply as written", "(no LLM at all)"], 12, 400, "#14532d")
    # real examples (spot checks): labels stagger downward left-to-right so no label sits on another's leader line
    ex = [(0.50, "teenage son won't talk to me  0.50  (wrong topic: correctly rejected)", 62),
          (0.55, "fight with partner about money  0.55", 84),
          (0.64, "quit smoking, keep relapsing  0.64", 106),
          (0.66, "moved to a new city, feel alone  0.66", 128),
          (0.80, "worry about everything  0.80", 84),
          (1.00, "an exact therapist sentence  1.00", 106)]
    for v, label, ty in ex:
        cx = X(v)
        s.arrow([(cx, ty + 6), (cx, y)], color="#94a3b8", head=False)
        s.e.append(f'<circle cx="{cx}" cy="{y}" r="5.5" fill="#0f172a"/>')
        if v >= 1.0:
            s.text(cx - 8, ty, label, 11.5, 700, "#0f172a", "end")
        else:
            s.text(cx + 8, ty, label, 11.5, 700, "#0f172a", "start")
    s.text(20, 30, "Similarity = how close the user's message is to the nearest therapist reply (1.0 = identical meaning).", 12.5, 400, "#334155")
    s.text(20, 312, "Real spot checks, not a validated set. The cut-offs are provisional until calibrated with a therapist-labelled sample.", 12, 400, "#64748b")
    return s
