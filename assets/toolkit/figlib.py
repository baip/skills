#!/usr/bin/env python3
"""
Shared SVG drawing helpers for accessible course notes.

Every document's drawing script uses these, so every figure is drawn with the
same primitives, line weights and contrast ratios. A script does
`from figlib import ...` and defines its own figures, each ending in write().

Label mini-syntax used by txt():
    *x*   italic          ~x~   subscript          ^x^   superscript
Nesting is allowed, e.g. "*C*~*V*~" or "*V*~1~^*g*^".
"""

import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent         # scripts/figures/
ROOT = HERE.parent.parent                      # the project root
FIGDIR = ROOT / "figures"      # every drawing script writes here

INK = "#1a1a1a"       # 15.3:1 against white
FAINT = "#5a5a5a"     # 7.0:1 against white, used only for hatching and fills
FONT = "DejaVu Sans"

SUB_SHIFT = 0.30      # em, downward
SUP_SHIFT = -0.42     # em, upward
SMALL = 0.72          # relative font size inside sub/sup


# --------------------------------------------------------------------------
# text
# --------------------------------------------------------------------------

_TOKEN = re.compile(r"\*([^*]*)\*|~([^~]*)~|\^([^^]*)\^")


def _runs(s, italic=False, offset=0.0):
    """Flatten the label mini-syntax into (text, italic, offset) runs."""
    out, pos = [], 0
    for m in _TOKEN.finditer(s):
        if m.start() > pos:
            out.append((s[pos:m.start()], italic, offset))
        if m.group(1) is not None:
            out += _runs(m.group(1), True, offset)
        elif m.group(2) is not None:
            out += _runs(m.group(2), italic, offset + SUB_SHIFT)
        else:
            out += _runs(m.group(3), italic, offset + SUP_SHIFT)
        pos = m.end()
    if pos < len(s):
        out.append((s[pos:], italic, offset))
    return out


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------
# measuring
# --------------------------------------------------------------------------
#
# Label positions are worked out here rather than left to the SVG renderer.
# cairosvg, which makes the PDF figures, mis-places the tspans of a <text>
# that carries text-anchor="middle" or "end": every run after the first is
# laid out from the anchor point again, so "P_f = P_0" comes out with the
# equals sign printed on top of the subscript. Browsers get it right, so the
# bug is invisible on the website and wrong in every PDF.
#
# Resolving the anchor here and always emitting text-anchor="start" avoids it
# and is exact in both renderers, provided the width is measured in the font
# that will be used. DejaVu Sans ships with matplotlib as well as with most
# Linux distributions; if neither is found the width falls back to an
# estimate, which shifts a centred label by a pixel or two and nothing else.

_FONT_FILES = ("DejaVuSans.ttf", "DejaVuSans-Oblique.ttf")
_FONT_DIRS = (
    "/usr/share/fonts/truetype/dejavu/",
    "/usr/share/fonts/dejavu/",
    "/usr/local/share/fonts/",
    "/Library/Fonts/",
    str(Path.home() / "Library/Fonts/"),
)
_FONTS = {}


def _font(italic):
    """A PIL font for measuring, or None when DejaVu cannot be found."""
    name = _FONT_FILES[1] if italic else _FONT_FILES[0]
    if name in _FONTS:
        return _FONTS[name]
    font = None
    try:
        from PIL import ImageFont
        paths = [d + name for d in _FONT_DIRS]
        try:
            import matplotlib
            paths.append(str(Path(matplotlib.get_data_path())
                             / "fonts/ttf" / name))
        except Exception:
            pass
        for p in paths:
            if Path(p).exists():
                font = ImageFont.truetype(p, 64)
                break
    except Exception:
        font = None
    _FONTS[name] = font
    return font


def _advance(text, size, italic):
    """Advance width of one plain run at the given size."""
    font = _font(italic)
    if font is None:
        return 0.55 * size * len(text)       # rough, and only a fallback
    return font.getlength(text) / 64.0 * size


def _width(s, size):
    """Advance width of a label mini-syntax string at the given size."""
    return sum(_advance(t, size * (SMALL if o else 1.0), i)
               for t, i, o in _runs(s) if t)


def txt(x, y, s, size=13, anchor="start", weight="normal", color=INK):
    """One <text> element. Returns SVG markup."""
    spans, current = [], 0.0
    for text, italic, offset in _runs(s):
        if not text:
            continue
        dy = (offset - current) * size
        current = offset
        attrs = [f'dy="{dy:.2f}"']
        if offset:
            attrs.append(f'font-size="{size * SMALL:.1f}"')
        if italic:
            attrs.append('font-style="italic"')
        spans.append(f'<tspan {" ".join(attrs)}>{_esc(text)}</tspan>')
    # The anchor is resolved here, not by the renderer: see _advance above.
    x0 = {"start": x, "middle": x - _width(s, size) / 2,
          "end": x - _width(s, size)}[anchor]
    # xml:space="preserve" matters too. A label becomes one tspan per run, and
    # the default white-space handling trims the leading space of each one,
    # which is what ran "*T* = 900" together into "T=900".
    return (
        f'<text x="{x0:.1f}" y="{y}" font-family="{FONT}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="start" fill="{color}" '
        f'xml:space="preserve">'
        + "".join(spans)
        + "</text>"
    )


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------

def arrow(x1, y1, x2, y2, head=7, width=2, color=INK, dash=None):
    """Straight line with a solid arrowhead at (x2, y2)."""
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    back = head * 1.6
    # stop the shaft short so it does not poke through the head
    sx, sy = x2 - back * 0.55 * math.cos(ang), y2 - back * 0.55 * math.sin(ang)
    p1 = (x2 - back * math.cos(ang - 0.38), y2 - back * math.sin(ang - 0.38))
    p2 = (x2 - back * math.cos(ang + 0.38), y2 - back * math.sin(ang + 0.38))
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{sx:.1f}" y2="{sy:.1f}" '
        f'stroke="{color}" stroke-width="{width}"{d}/>'
        f'<polygon points="{x2},{y2} {p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}" '
        f'fill="{color}"/>'
    )


def dbl_arrow(x1, y1, x2, y2, **kw):
    return arrow(x1, y1, x2, y2, **kw) + arrow(x2, y2, x1, y1, **kw)


def hatch(x0, y0, x1, y1, step=9, color=FAINT, width=1.1):
    """45-degree hatching clipped analytically to a rectangle."""
    out, c = [], x0 + y0
    while c <= x1 + y1:
        ax, bx = max(x0, c - y1), min(x1, c - y0)
        if bx > ax:
            out.append(
                f'<line x1="{ax:.1f}" y1="{c - ax:.1f}" x2="{bx:.1f}" y2="{c - bx:.1f}" '
                f'stroke="{color}" stroke-width="{width}"/>'
            )
        c += step
    return "".join(out)


def hatch_poly(pts, step=9, color=FAINT, width=1.1):
    """45-degree hatching clipped to an arbitrary closed polygon."""
    def inside(px, py):
        n, hit = len(pts), False
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            if (y1 > py) != (y2 > py):
                if px < x1 + (py - y1) * (x2 - x1) / (y2 - y1):
                    hit = not hit
        return hit

    xs = [q[0] for q in pts]
    ys = [q[1] for q in pts]
    out, c = [], min(xs) + min(ys)
    cmax, fine = max(xs) + max(ys), 0.7
    while c <= cmax:
        ax, bx = max(min(xs), c - max(ys)), min(max(xs), c - min(ys))
        run, k = None, ax
        while k <= bx + fine:
            k = min(k, bx)
            if inside(k, c - k):
                if run is None:
                    run = k
            else:
                if run is not None and k - run > 1.5:
                    out.append(f'<line x1="{run:.1f}" y1="{c - run:.1f}" '
                               f'x2="{k:.1f}" y2="{c - k:.1f}" stroke="{color}" '
                               f'stroke-width="{width}"/>')
                run = None
            if k >= bx:
                break
            k += fine
        if run is not None and bx - run > 1.5:
            out.append(f'<line x1="{run:.1f}" y1="{c - run:.1f}" '
                       f'x2="{bx:.1f}" y2="{c - bx:.1f}" stroke="{color}" '
                       f'stroke-width="{width}"/>')
        c += step
    return "".join(out)


def rect(x, y, w, h, dash=None, width=2, color=INK, fill="none"):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" '
            f'stroke="{color}" stroke-width="{width}"{d}/>')


def line(x1, y1, x2, y2, dash=None, width=2, color=INK):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
            f'stroke-width="{width}"{d}/>')


def path(d, dash=None, width=2, color=INK, fill="none"):
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<path d="{d}" fill="{fill}" stroke="{color}" '
            f'stroke-width="{width}"{da}/>')


def ellipse(cx, cy, rx, ry, dash=None, width=2, color=INK, fill="none"):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" '
            f'stroke="{color}" stroke-width="{width}"{d}/>')


def piston(x, y, w, h=11):
    """A hatched piston slab."""
    return rect(x, y, w, h) + hatch(x + 1, y + 1, x + w - 1, y + h - 1, step=7)


def cylinder(x, ytop, w, ybot):
    """Open-topped cylinder: two side walls and a base."""
    return (line(x, ytop, x, ybot) + line(x + w, ytop, x + w, ybot)
            + line(x, ybot, x + w, ybot))


def write(name, vb_w, vb_h, body):
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vb_w} {vb_h}" '
        f'width="{vb_w}" height="{vb_h}" role="img">\n  '
        + body + "\n</svg>\n"
    )
    FIGDIR.mkdir(exist_ok=True)
    (FIGDIR / name).write_text(svg, encoding="utf-8")
    print("wrote", FIGDIR.name + "/" + name)


# --------------------------------------------------------------------------
# additions for the Second Law notes
# --------------------------------------------------------------------------

def wavy(x1, y1, x2, y2, amp=3.4, period=14, width=1.8, color=INK,
         head=6, arrow="end"):
    """Sinusoidal line, the printed convention for a heat interaction.

    arrow: "end" puts the head at (x2, y2), "start" at (x1, y1), None omits it.
    """
    import math
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1:
        return ""
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    stop = max(length - (head * 1.6 if arrow == "end" else 0), 1)
    start = head * 1.6 if arrow == "start" else 0
    pts, s = [], start
    while s <= stop:
        a = amp * math.sin(2 * math.pi * (s - start) / period)
        pts.append(f"{x1 + ux * s + nx * a:.1f},{y1 + uy * s + ny * a:.1f}")
        s += 1.4
    out = (f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" '
           f'stroke-width="{width}"/>')
    if arrow == "end":
        out += arrow_head(x2, y2, ux, uy, head, color)
    elif arrow == "start":
        out += arrow_head(x1, y1, -ux, -uy, head, color)
    return out


def arrow_head(x, y, ux, uy, head=6, color=INK):
    """Solid triangular head at (x, y) pointing along the unit vector."""
    import math
    ang = math.atan2(uy, ux)
    back = head * 1.6
    p1 = (x - back * math.cos(ang - 0.38), y - back * math.sin(ang - 0.38))
    p2 = (x - back * math.cos(ang + 0.38), y - back * math.sin(ang + 0.38))
    return (f'<polygon points="{x},{y} {p1[0]:.1f},{p1[1]:.1f} '
            f'{p2[0]:.1f},{p2[1]:.1f}" fill="{color}"/>')


def slab(x, y, w, h, label=None, size=14, color=INK):
    """A reservoir drawn as a plain rectangle, optionally lettered."""
    out = rect(x, y, w, h, color=color)
    if label:
        out += txt(x + w / 2, y + h / 2 + size * 0.36, label, size, "middle",
                   color=color)
    return out


def engine(cx, cy, r=17, label=None, size=12):
    """A cyclic device drawn as a circle, optionally lettered."""
    out = ellipse(cx, cy, r, r)
    if label:
        out += txt(cx, cy + size * 0.36, label, size, "middle")
    return out


def vec_accent(x, y, size=15, anchor="start", color=INK):
    """A small arrow accent drawn above a symbol.

    WeasyPrint's SVG text does not compose the combining arrow U+20D7 over a
    letter, so inside a figure the accent is drawn rather than typed. Place it
    with the same x, y and anchor as the txt() call it decorates.
    """
    w = size * 0.52
    cx = {"start": x + size * 0.26, "middle": x, "end": x - size * 0.26}[anchor]
    y0 = y - size * 0.92
    x0, x1 = cx - w / 2, cx + w / 2
    return (f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1 - 1.4:.1f}" '
            f'y2="{y0:.1f}" stroke="{color}" stroke-width="1.3"/>'
            + arrow_head(x1, y0, 1, 0, size * 0.20, color))


def bar_accent(x, y, size=15, anchor="start", color=INK, width=1.4):
    """A macron drawn above a symbol, for a specific (per unit mass) quantity.

    WeasyPrint's SVG text does not compose U+0304 over a letter, so inside a
    figure the accent is drawn. Place it with the same x, y and anchor as the
    txt() call it decorates.
    """
    w = size * 0.54
    cx = {"start": x + size * 0.27, "middle": x, "end": x - size * 0.27}[anchor]
    y0 = y - size * 0.88
    return (f'<line x1="{cx - w / 2:.1f}" y1="{y0:.1f}" '
            f'x2="{cx + w / 2:.1f}" y2="{y0:.1f}" stroke="{color}" '
            f'stroke-width="{width}"/>')


def tilde_accent(x, y, size=15, anchor="start", color=INK, width=1.3):
    """A tilde drawn above a symbol, for a per-mole quantity.

    G, H, S and C have no precomposed tilde form, and WeasyPrint's SVG text
    does not compose U+0303 over a letter, so inside a figure the accent is
    drawn. Place it with the same x, y and anchor as the txt() call. Where a
    precomposed character exists, as for Ã, Ũ and Ṽ, use that instead.
    """
    w = size * 0.50
    cx = {"start": x + size * 0.30, "middle": x, "end": x - size * 0.30}[anchor]
    y0 = y - size * 1.04
    return (f'<path d="M {cx - w / 2:.1f} {y0:.1f} '
            f'C {cx - w / 6:.1f} {y0 - w * 0.34:.1f} '
            f'{cx + w / 6:.1f} {y0 + w * 0.34:.1f} '
            f'{cx + w / 2:.1f} {y0:.1f}" fill="none" stroke="{color}" '
            f'stroke-width="{width}"/>')


def dot_accent(x, y, size=15, anchor="start", color=INK):
    """A dot drawn above a symbol, for a rate.

    Q has no precomposed dotted form in Unicode, and neither renderer
    composes U+0307 over it, so Q̇ inside a figure must be drawn. Place it
    with the same x, y and anchor as the txt() call. For a single dotted
    capital standing on its own, dotted() below is simpler.
    """
    cx = {"start": x + size * 0.34, "middle": x, "end": x - size * 0.34}[anchor]
    return (f'<circle cx="{cx:.1f}" cy="{y - size * 0.92:.1f}" '
            f'r="{size * 0.085:.2f}" fill="{color}"/>')


def hat_accent(x, y, size=15, anchor="start", color=INK, width=1.3):
    """A circumflex drawn above a symbol, for a per unit mass quantity.

    Ŝ, Ĥ and Ĉ are precomposed and should be typed; V has no precomposed
    circumflex form, so V̂ inside a figure is drawn.
    """
    w = size * 0.42
    cx = {"start": x + size * 0.30, "middle": x, "end": x - size * 0.30}[anchor]
    y0 = y - size * 0.86
    return (f'<path d="M {cx - w / 2:.1f} {y0:.1f} L {cx:.1f} '
            f'{y0 - w * 0.62:.1f} L {cx + w / 2:.1f} {y0:.1f}" fill="none" '
            f'stroke="{color}" stroke-width="{width}" '
            f'stroke-linejoin="miter"/>')


def dotted(x, y, letter, size=15, anchor="start", color=INK):
    """An italic capital with a rate dot drawn centred above it.

    The precomposed dotted capitals (Ẇ, Ṡ, Ṁ, Ṅ, Ṗ, Ṫ) exist, but in DejaVu
    Sans Oblique their dot is small and set off-centre, so it reads faintly
    at figure sizes. Drawing the dot over the measured centre of the glyph,
    a little larger than dot_accent's, keeps it clear. `letter` is the bare
    letter; it is set italic here.
    """
    w = _width(f"*{letter}*", size)
    x0 = {"start": x, "middle": x - w / 2, "end": x - w}[anchor]
    cx = x0 + w / 2 + size * 0.04          # the italic lean moves the top right
    return (txt(x0, y, f"*{letter}*", size, color=color)
            + f'<circle cx="{cx:.1f}" cy="{y - size * 0.94:.1f}" '
              f'r="{size * 0.11:.2f}" fill="{color}"/>')


# --------------------------------------------------------------------------
# state numbers and label placement
# --------------------------------------------------------------------------

def state(cx, cy, n, size=15, color=INK):
    """A state number in a circle, centred on (cx, cy).

    The circled digits U+2460 onward are missing from the fonts the PDF
    build falls back on, so a label typed as a circled digit vanishes from
    the PDF. The circle is drawn and the digit set inside it instead, which
    renders the same everywhere. In prose, write "state 1".
    """
    r = size * 0.56
    return (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.2f}" fill="none" '
            f'stroke="{color}" stroke-width="1.3"/>'
            + txt(cx, cy + size * 0.27, str(n), round(size * 0.74, 1),
                  "middle", color=color))


def _box_gap(box, px, py):
    """Distance from a point to a box, zero inside it."""
    x0, y0, x1, y1 = box
    return math.hypot(max(x0 - px, 0.0, px - x1), max(y0 - py, 0.0, py - y1))


def _box_box(a, b):
    """Distance between two boxes, zero if they overlap."""
    return math.hypot(max(a[0] - b[2], 0.0, b[0] - a[2]),
                      max(a[1] - b[3], 0.0, b[1] - a[3]))


def place_label(geo, placed, x, y, label, size=13, near=44.0):
    """Put a label beside the point (x, y) in the clearest gap in the drawing.

    In a dense figure a fixed offset per label lands some of them on a line,
    so the offset is searched instead. Sample every curve you draw into
    `geo` (a list of (x, y) points, a point every few pixels is plenty), and
    keep the boxes of labels already placed in `placed`. Candidate positions
    on rings around the point are scored on how far the label's box sits
    from both, with a mild preference for staying close. A label that has to
    sit far from its point gets a hairline leader so that it cannot be read
    as belonging to a neighbour.

    Returns (svg, box). Append the box to `placed` before the next call.
    """
    w, h = _width(label, size), size * 0.82
    local = [q for q in geo if abs(q[0] - x) < near and abs(q[1] - y) < near]
    best, best_box = None, None
    for rr in (10.0, 13.0, 16.0, 19.0, 23.0, 27.0):
        for i in range(48):
            a = 2 * math.pi * i / 48
            cx, cy = x + rr * math.cos(a), y + rr * math.sin(a)
            box = (cx - w / 2 - 1.5, cy - h / 2 - 1.5,
                   cx + w / 2 + 1.5, cy + h / 2 + 1.5)
            clear = min([_box_gap(box, *q) for q in local], default=20.0)
            apart = min([_box_box(box, q) for q in placed], default=20.0)
            score = min(clear, 4.0) * 5.0 + min(apart, 6.0) * 2.5 - rr * 0.5
            if best is None or score > best[0]:
                best, best_box = (score, cx, cy), box
    _, cx, cy = best
    out = txt(cx, cy + size * 0.36, label, size, "middle")
    d = math.hypot(cx - x, cy - y)
    if d > 17.0:
        ux, uy = (cx - x) / d, (cy - y) / d
        hw = (best_box[2] - best_box[0]) / 2
        hh = (best_box[3] - best_box[1]) / 2
        ts = [t for t in ((best_box[0] - x) / ux if ux else None,
                          (best_box[2] - x) / ux if ux else None,
                          (best_box[1] - y) / uy if uy else None,
                          (best_box[3] - y) / uy if uy else None)
              if t is not None and t > 0
              and abs(x + t * ux - cx) <= hw + 0.01
              and abs(y + t * uy - cy) <= hh + 0.01]
        end = min(ts or [d])
        out = line(x + 4.5 * ux, y + 4.5 * uy,
                   x + (end - 1.0) * ux, y + (end - 1.0) * uy,
                   width=0.9, color=FAINT) + out
    return out, best_box


def label(x, y, segs, size=13, anchor="start", color=INK):
    """A label built from segments, some of them carrying a drawn accent.

    `segs` is a list of (mini-syntax string, accent), the accent being None,
    "dot", "hat", "tilde", "bar" or "vec". Use it where a symbol has no
    precomposed form (Q with a dot, V with a circumflex, H with a tilde):
    each segment is measured with the real font metrics and its accent is
    drawn over that segment's first glyph. For example
    label(x, y, [("*Q*", "dot"), ("~*C*~", None)]) draws Q-dot sub C.
    """
    fns = {"dot": dot_accent, "hat": hat_accent, "tilde": tilde_accent,
           "bar": bar_accent, "vec": vec_accent}
    widths = [_width(t, size) for t, _ in segs]
    x0 = {"start": x, "middle": x - sum(widths) / 2,
          "end": x - sum(widths)}[anchor]
    out, cx = [], x0
    for (t, acc), w in zip(segs, widths):
        out.append(txt(round(cx, 1), y, t, size, "start", color=color))
        if acc:
            out.append(fns[acc](round(cx, 1), y, size, "start", color=color))
        cx += w
    return "".join(out)
