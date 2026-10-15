#!/usr/bin/env python3
"""
Draw the figures of 01_Example.md.

Usage:
    python3 scripts/figures/make_figures_01.py

Every figure is written into figures/ as fig_e01_NN_<name>.svg. The
accessibility metadata (the caption, which is the long description, and the
short alt text) lives in the Markdown, not here, so a figure can be redrawn
without touching its description and vice versa.

Curves are computed from their equations rather than traced from the
original, so each bends the way its own equation makes it bend.
"""

from figlib import INK, arrow, path, txt, write


def fig01():
    """One isotherm, P V = constant, with a marked state."""
    b = []
    ox, oy, right, top = 60, 250, 330, 30          # the axes
    b += [arrow(ox, oy, right, oy, head=6, width=1.8)]
    b += [arrow(ox, oy, ox, top, head=6, width=1.8)]
    b += [txt(ox - 20, top + 12, "*P*", 15)]
    b += [txt(right + 4, oy + 6, "*V*", 15)]

    # the data box maps onto the middle of the plotting area, so the curve
    # sits centred between the axes rather than crowding one of them
    sx = lambda v: 90 + (v - 0.8) * 110.0
    sy = lambda p: 230 - (p - 0.40) * 120.0
    k = 1.6
    vs = [0.9 + (2.9 - 0.9) * i / 120 for i in range(121)]
    d = "M " + " L ".join(f"{sx(v):.1f} {sy(k / v):.1f}" for v in vs)
    b += [path(d, width=2.2)]

    v1 = 1.5
    x1, y1 = sx(v1), sy(k / v1)
    b += [f'<circle cx="{x1:.1f}" cy="{y1:.1f}" r="3.4" fill="{INK}"/>']
    b += [txt(x1 + 8, y1 - 8, "(*V*~1~, *P*~1~)", 13)]
    write("fig_e01_01_isotherm.svg", 360, 280, "".join(b))


if __name__ == "__main__":
    fig01()
