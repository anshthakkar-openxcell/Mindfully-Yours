"""Tiny SVG diagram kit: boxes, diamonds, orthogonal arrows. Units are sized so that a 1100-wide
viewBox printed on a landscape A4 page gives ~8.5-11pt text."""
from html import escape as esc

FONT = "Lato, 'Noto Sans Devanagari', sans-serif"
TAG = {  # data-store / vendor chips
    "RDS": "#1d4ed8", "VECTOR DB": "#7e22ce", "REDIS": "#c2410c", "AI": "#0f766e",
}

class Svg:
    def __init__(self, w, h, y0=0):
        self.w, self.h, self.y0, self.e = w, h, y0, []

    # ---- text helper: lines = list of (text, size, weight, color); centred on cx, block centred on cy
    def _text_block(self, cx, cy, lines, anchor="middle"):
        lh = [s * 1.28 for (_, s, _, _) in lines]
        total = sum(lh)
        y = cy - total / 2
        out = []
        for (t, s, wgt, col), h in zip(lines, lh):
            y += h
            if isinstance(t, list):  # list of (text,color,weight) runs (tag line)
                runs = "".join(f'<tspan fill="{c}" font-weight="{w}">{esc(x)}</tspan>' for x, c, w in t)
                out.append(f'<text x="{cx}" y="{y - s*0.25:.1f}" font-size="{s}" text-anchor="{anchor}">{runs}</text>')
            else:
                out.append(f'<text x="{cx}" y="{y - s*0.25:.1f}" font-size="{s}" font-weight="{wgt}" fill="{col}" text-anchor="{anchor}">{esc(t)}</text>')
        return "".join(out)

    def _lines(self, title, body, tags, dark):
        tc = "#ffffff" if dark else "#0f172a"
        bc = "#cbd5e1" if dark else "#334155"
        L = []
        for t in title:
            L.append((t, 15, 700, tc))
        for b in body:
            L.append((b, 12, 400, bc))
        if tags:
            runs = []
            for i, (name, note) in enumerate(tags):
                col = TAG.get(name, "#475569")
                if i: runs.append(("   \u00b7   ", "#94a3b8", 400))
                runs.append((name, col, 800))
                if note: runs.append(("  " + note, col, 400))
            L.append((runs, 11, 400, "#000"))
        return L

    def box(self, x, y, w, h, fill, stroke, title, body=(), tags=(), dashed=False, dark=False, rx=14, sw=1.8):
        d = ' stroke-dasharray="7 5"' if dashed else ""
        self.e.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')
        self.e.append(self._text_block(x + w / 2, y + h / 2, self._lines(title, body, tags, dark)))
        return (x, y, w, h)

    def diamond(self, cx, cy, w, h, fill, stroke, title, body=(), sw=1.8):
        pts = f"{cx},{cy-h/2} {cx+w/2},{cy} {cx},{cy+h/2} {cx-w/2},{cy}"
        self.e.append(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
        self.e.append(self._text_block(cx, cy, self._lines(title, body, (), False)))

    def cluster(self, x, y, w, h, fill, stroke, label, sub="", dashed=False):
        d = ' stroke-dasharray="8 6"' if dashed else ""
        self.e.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="{fill}" stroke="{stroke}" stroke-width="1.8"{d}/>')
        sub_t = f'<tspan font-weight="400" font-size="12" fill="#475569">  {esc(sub)}</tspan>' if sub else ""
        self.e.append(f'<text x="{x+16}" y="{y+24}" font-size="14" font-weight="800" fill="#0f172a">{esc(label)}{sub_t}</text>')

    def text(self, x, y, s, size=12, weight=400, color="#334155", anchor="start"):
        self.e.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{esc(s)}</text>')

    def arrow(self, pts, label=None, lpos=None, dashed=False, color="#64748b", both=False, lsize=12, head=True):
        d = "M " + " L ".join(f"{x},{y}" for x, y in pts)
        da = ' stroke-dasharray="7 5"' if dashed else ""
        ms = ' marker-start="url(#ah)"' if both else ""
        me = ' marker-end="url(#ah)"' if head else ""
        self.e.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.9"{da}{me}{ms}/>')
        if label:
            lx, ly = lpos if lpos else ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2)
            self.e.append(f'<text x="{lx}" y="{ly}" font-size="{lsize}" font-weight="700" fill="#334155" text-anchor="middle" '
                          f'style="paint-order:stroke;stroke:#fff;stroke-width:5px;stroke-linejoin:round">{esc(label)}</text>')

    def legend(self, x, y, items):
        cx = x
        for kind, label in items:
            if kind in TAG:
                self.e.append(f'<text x="{cx}" y="{y}" font-size="12" font-weight="800" fill="{TAG[kind]}">{kind}</text>')
                w = 8 * len(kind) + 6
                self.e.append(f'<text x="{cx+w}" y="{y}" font-size="12" fill="#334155">{esc(label)}</text>')
                cx += w + 7.2 * len(label) + 26
            else:
                dashed = kind == "planned"
                d = ' stroke-dasharray="6 4"' if dashed else ""
                fill = "#f1f5f9" if dashed else "#dcfce7"
                stroke = "#94a3b8" if dashed else "#16a34a"
                self.e.append(f'<rect x="{cx}" y="{y-12}" width="26" height="15" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.6"{d}/>')
                self.e.append(f'<text x="{cx+34}" y="{y}" font-size="12" fill="#334155">{esc(label)}</text>')
                cx += 34 + 7.2 * len(label) + 26

    def mtext(self, x, y, lines, size=11, weight=400, color="#334155", anchor="start", lh=1.3):
        for i, t in enumerate(lines):
            self.e.append(f'<text x="{x}" y="{y + i * size * lh:.1f}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{esc(t)}</text>')

    def rect(self, x, y, w, h, fill, stroke="none", rx=8, sw=1.4, dashed=False):
        d = ' stroke-dasharray="6 4"' if dashed else ""
        self.e.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def render(self):
        defs = ('<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
                '<path d="M0,0 L10,5 L0,10 z" fill="#64748b"/></marker></defs>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 {self.y0} {self.w} {self.h - self.y0}" font-family="{FONT}" '
                f'width="100%" preserveAspectRatio="xMidYMid meet">{defs}{"".join(self.e)}</svg>')
