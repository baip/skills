#!/usr/bin/env python3
"""
Render the pages of an original as images you can read, and zoom into them.

Usage:
    python3 render_pages.py ORIGINAL.pdf OUTDIR            # every page
    python3 render_pages.py ORIGINAL.pdf OUTDIR --pages 3-5
    python3 render_pages.py ORIGINAL.pdf OUTDIR --zoom 4 0.10 0.30 0.55 0.45

Text extraction from a OneNote export or a scan returns only the typed text:
every handwritten line and every sketch is ink, so the transcription has to be
made from images. Each page is rendered at 130 dpi and also split into a top
and a bottom half (p-03.png, p-03-top.png, p-03-bottom.png), because a whole
page viewed at once is too small to read subscripts, primes and accents.

--zoom PAGE X0 Y0 X1 Y1 renders one page at 300 dpi and crops the given
region, in fractions of the page width and height, to zoom-PAGE.png. Use it
for anything you are not sure of: a struck term, a brace label, whether a
subscript is x_j or x_i, whether a mark is = or ≃.

Needs pdftoppm (poppler) and Pillow.
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image


def render(pdf, out, first=None, last=None, dpi=130, prefix="p"):
    cmd = ["pdftoppm", "-r", str(dpi), "-png"]
    if first:
        cmd += ["-f", str(first)]
    if last:
        cmd += ["-l", str(last)]
    subprocess.run(cmd + [str(pdf), str(out / prefix)], check=True)


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)
    pdf, out = Path(args[0]), Path(args[1])
    out.mkdir(parents=True, exist_ok=True)

    if "--zoom" in args:
        i = args.index("--zoom")
        page = int(args[i + 1])
        x0, y0, x1, y1 = (float(v) for v in args[i + 2:i + 6])
        render(pdf, out, page, page, dpi=300, prefix="z")
        src = sorted(out.glob("z-*%d.png" % page))[-1]
        im = Image.open(src)
        w, h = im.size
        crop = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
        dest = out / ("zoom-%d.png" % page)
        crop.save(dest)
        src.unlink()
        print("wrote", dest, crop.size)
        return

    first = last = None
    if "--pages" in args:
        spec = args[args.index("--pages") + 1]
        first, _, last = spec.partition("-")
        first, last = int(first), int(last or first)
    render(pdf, out, first, last)
    for png in sorted(out.glob("p-*.png")):
        if png.stem.endswith(("-top", "-bottom")):
            continue
        im = Image.open(png)
        w, h = im.size
        im.crop((0, 0, w, h // 2 + 20)).save(png.with_name(png.stem + "-top.png"))
        im.crop((0, h // 2 - 20, w, h)).save(png.with_name(png.stem + "-bottom.png"))
        print("wrote", png.name, "and its two halves")


if __name__ == "__main__":
    main()
