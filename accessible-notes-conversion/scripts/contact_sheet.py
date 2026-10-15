#!/usr/bin/env python3
"""
Render SVG figures to PNG and lay them out on one sheet for review.

Usage:
    python3 contact_sheet.py OUT.png figures/fig_c03_02_*.svg figures/fig_c03_05_*.svg
    python3 contact_sheet.py OUT.png --scale 1.6 --width 1400 figures/fig_hw02_*.svg

Look at every figure you change before you hand it back, and send the author
the sheet: most review comments are about placement (a label on a line, an
arrow stopping short, a curve off-centre) that only shows when rendered.

Each figure is rendered with cairosvg, which is also what the PDF build uses,
so what you see here is what the PDF will show. Figures are packed left to
right into rows no wider than --width pixels, on white, with the file name
under each.

Needs cairosvg and Pillow.
"""

import io
import sys
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)
    out = Path(args.pop(0))
    scale, width = 1.4, 1600
    if "--scale" in args:
        i = args.index("--scale")
        scale = float(args[i + 1])
        del args[i:i + 2]
    if "--width" in args:
        i = args.index("--width")
        width = int(args[i + 1])
        del args[i:i + 2]

    tiles = []
    for name in args:
        png = cairosvg.svg2png(url=name, scale=scale, background_color="white")
        im = Image.open(io.BytesIO(png)).convert("RGB")
        if im.width > width:
            im = im.resize((width, int(im.height * width / im.width)))
        tiles.append((Path(name).stem, im))

    rows, row, used = [], [], 0
    for t in tiles:
        if row and used + t[1].width + 16 > width:
            rows.append(row)
            row, used = [], 0
        row.append(t)
        used += t[1].width + 16
    if row:
        rows.append(row)

    label_h = 18
    height = sum(max(im.height for _, im in r) + label_h + 16 for r in rows)
    sheet = Image.new("RGB", (width, max(height, 1)), "white")
    draw = ImageDraw.Draw(sheet)
    y = 8
    for r in rows:
        x, h = 8, max(im.height for _, im in r)
        for stem, im in r:
            sheet.paste(im, (x, y))
            draw.text((x, y + h + 2), stem, fill=(90, 90, 90))
            x += im.width + 16
        y += h + label_h + 16
    sheet.save(out)
    print("wrote %s: %d figure(s)" % (out, len(tiles)))


if __name__ == "__main__":
    main()
