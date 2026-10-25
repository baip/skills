#!/usr/bin/env python3
"""
Render SVG figures to PNG and lay them out on one sheet for review.

Usage:
    python3 contact_sheet.py OUT.png figures/fig_c03_02_*.svg figures/fig_c03_05_*.svg
    python3 contact_sheet.py OUT.png --scale 1.6 --width 1400 figures/fig_hw02_*.svg
    python3 contact_sheet.py OUT.png \\
        --original originals/07.pdf 1 0.24 0.12 0.60 0.25 figures/fig_c07_01_*.svg \\
        --original work/07/zoom-1.png figures/fig_c07_02_*.svg

Look at every figure you change before you hand it back, and send the author
the sheet: most review comments are about placement (a label on a line, an
arrow stopping short, a curve off-centre) that only shows when rendered.

--original puts the original beside the next figure named, at the same
height, so the two are compared as images rather than against a memory of
the sketch. Give it either an image (a crop from render_pages.py --zoom) or
PDF PAGE X0 Y0 X1 Y1, the same page and fractions of the page as --zoom
takes. Pair every figure that redraws something in an original: a reversed
axis, a closed vessel that should be open or a curve count that is one too
many is plain side by side and easy to miss in the redraw alone.

Each figure is rendered with cairosvg, which is also what the PDF build uses,
so what you see here is what the PDF will show. Figures are packed left to
right into rows no wider than --width pixels, on white, with the file name
under each.

Needs cairosvg and Pillow, and pdftoppm (poppler) for a PDF original.
"""

import io
import subprocess
import sys
import tempfile
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw

GAP, LABEL_H = 16, 18


def original_crop(pdf, page, box):
    """One page of a PDF at 200 dpi, cropped to fractions of the page."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["pdftoppm", "-r", "200", "-png", "-f", str(page),
                        "-l", str(page), str(pdf), tmp + "/p"], check=True)
        im = Image.open(sorted(Path(tmp).glob("p-*.png"))[-1]).convert("RGB")
        w, h = im.size
        x0, y0, x1, y1 = box
        return im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))


def pair(original, label, im, stem):
    """The original and the redraw side by side, scaled to one height."""
    o = original.resize((max(1, int(original.width * im.height
                                    / original.height)), im.height))
    tile = Image.new("RGB", (o.width + GAP + im.width, im.height), "white")
    tile.paste(o, (0, 0))
    tile.paste(im, (o.width + GAP, 0))
    return tile, [(0, label), (o.width + GAP, stem)]


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

    tiles, pending = [], None
    while args:
        name = args.pop(0)
        if name == "--original":
            src = args.pop(0)
            if src.lower().endswith(".pdf"):
                page = int(args.pop(0))
                box = [float(args.pop(0)) for _ in range(4)]
                pending = (original_crop(src, page, box),
                           "original, %s page %d" % (Path(src).name, page))
            else:
                pending = (Image.open(src).convert("RGB"),
                           "original, " + Path(src).name)
            continue
        png = cairosvg.svg2png(url=name, scale=scale, background_color="white")
        im = Image.open(io.BytesIO(png)).convert("RGB")
        stem = Path(name).stem
        if pending:
            im, labels = pair(*pending, im, stem)
            pending = None
        else:
            labels = [(0, stem)]
        if im.width > width:
            k = width / im.width
            im = im.resize((width, int(im.height * k)))
            labels = [(int(x * k), s) for x, s in labels]
        tiles.append((labels, im))
    if pending:
        sys.exit("--original must come before the figure it goes with")

    rows, row, used = [], [], 0
    for t in tiles:
        if row and used + t[1].width + GAP > width:
            rows.append(row)
            row, used = [], 0
        row.append(t)
        used += t[1].width + GAP
    if row:
        rows.append(row)

    height = sum(max(im.height for _, im in r) + LABEL_H + GAP for r in rows)
    sheet = Image.new("RGB", (width, max(height, 1)), "white")
    draw = ImageDraw.Draw(sheet)
    y = 8
    for r in rows:
        x, h = 8, max(im.height for _, im in r)
        for labels, im in r:
            sheet.paste(im, (x, y))
            for dx, s in labels:
                draw.text((x + dx, y + h + 2), s, fill=(90, 90, 90))
            x += im.width + GAP
        y += h + LABEL_H + GAP
    sheet.save(out)
    print("wrote %s: %d figure(s)" % (out, len(tiles)))


if __name__ == "__main__":
    main()
