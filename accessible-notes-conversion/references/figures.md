# Redrawing figures

Read this before writing or revising a `make_figures_*.py` script. Most of an
author's review comments on a converted document are about figures, and
nearly all of them are about geometry that a careful first pass would have
caught: a curve bending the wrong way, a label sitting on a line, an arrow
stopping short of the thing it points at, a lot of empty space.

## Contents

1. Start from the original, zoomed in
2. The drawing script
3. Geometry: compute it, do not place it by eye
4. Labels
5. Symbols the fonts get wrong
6. Plots
7. Diagrams of equipment
8. Three-dimensional sketches
9. Look at every figure you change
10. Writing the caption and alt text

## 1. Start from the original, zoomed in

Render the page and zoom into the sketch before drawing anything:

```
python3 <skill>/scripts/render_pages.py originals/03.pdf work/03 --pages 4
python3 <skill>/scripts/render_pages.py originals/03.pdf work/03 --zoom 4 0.05 0.40 0.60 0.75
```

Write down, before coding, what the sketch actually shows, and keep it as a
file, `work/<doc>/fig<NN>.txt`, one numbered item a line. These are exactly
the details that get lost, and a list in the head is gone by the time the
render is ready to check:

- how many there are of everything that repeats: curves, isotherms, ticks,
  hatched faces, arrows
- which way each curve bends (concave or convex, rising or falling), and
  where each curve starts and ends
- which way each axis arrow points, read from the arrow in the original
- where each label sits relative to its curve and to any wall: inside or
  outside a container, above or below a line
- where each arrow starts and ends, and what it runs beside
- which lines are dashed, and what is hatched
- what is open and what is closed (an inlet drawn as a gap in a wall is
  open, a vessel drawn without a lid is open)
- every mark on a letter, over it or under it.

Hand sketches are rough. Keep the author's intent and make it exact: two
arrows meant to be equal are equal, a label meant to be on a line is on it,
a curve meant to cross another crosses it. Making a sketch exact is not the
same as tidying it. Do not move what the original places deliberately to
where it would be neater.

These have each come back from an author as corrections:

- **Hatching marks a whole face.** In a sketch of a solid, the hatched
  region is the cut face, out to its edges. It is not a band along one
  edge.
- **An axis direction comes from the original,** not from the projection
  code. Draw the arrow from the same transform as the data, then check it
  against the sketch, since the two can disagree.
- **A family of curves starts where the original starts it.** Hyperbolas
  drawn from the axis start at the axis, and curves whose ends are
  staggered end staggered.
- **A thing drawn beside another is not that thing.** An arrow beside a
  piston rod is not drawn on the rod, and a water line that stops at a
  cylinder wall does not cross the cylinder.
- **A label outside a container stays outside.** A label inside a wall
  reads as naming what is inside.
- **The convenient primitive decides nothing.** `rect()` closes all four
  sides, and a straight `line()` crosses everything in its way. Draw what
  the original draws, even when that needs a path.
- **Marks on letters are notation.** A line under V and a bar over it mean
  different things. Keep the original's mark and check the project's
  conventions for what it stands for.

## 2. The drawing script

One script per document, `scripts/figures/make_figures_<NN>.py`, one function per figure,
each ending in `write("fig_<doc>_<NN>_<name>.svg", width, height, body)`.
Build on `figlib.py`:

| Helper | Draws |
|---|---|
| `txt(x, y, s, size, anchor)` | a label in the mini-syntax `*italic*`, `~sub~`, `^sup^` |
| `line`, `path`, `rect`, `ellipse` | strokes, in `INK` by default, `dash="5 4"` for dashed |
| `arrow`, `dbl_arrow`, `arrow_head` | arrows with a filled head |
| `hatch`, `hatch_poly` | hatching in `FAINT` for walls and solids |
| `piston`, `cylinder`, `slab`, `engine`, `wavy` | common apparatus |
| `label(x, y, segs)` | a label whose segments carry drawn accents |
| `dotted(x, y, "W")` | a capital with a rate dot, drawn |
| `state(cx, cy, n)` | a state number in a drawn circle |
| `place_label(geo, placed, x, y, s)` | a label put in the clearest gap near a point |
| `dot_accent`, `hat_accent`, `tilde_accent`, `bar_accent`, `vec_accent` | a single accent |

Keep the description out of the script. The caption and alt text live in the
Markdown so a figure can be redrawn without touching them.

Size the viewBox to the drawing. A figure with a large empty margin is
printed smaller than it needs to be, which is its own accessibility problem.
When the author asks for a figure to be more compact, move the parts closer,
then shrink the viewBox to fit with a small margin (8 to 12 px).

## 3. Geometry: compute it, do not place it by eye

Derive every coordinate from the geometry it depends on.

- **Curves come from equations.** An isotherm is `P = k / V`, an adiabat
  `P = k / V^γ`. A curve that is only a shape gets a simple closed form (a
  parabola, an exponential) chosen to bend the right way. Then say in the
  caption that it is a sketch. Check the sign of the second derivative
  against the original: "concave" and "convex" are the most common
  corrections.
- **Centre the data in the plotting area.** Map the data box onto the middle
  of the axes with a linear transform (`sx = lambda v: x0 + (v - v0) * kx`),
  and choose the constants so the curves sit between the axes with room on
  every side rather than crowding one corner.
- **Arrows start and end on objects.** Compute the end points from the shape
  they touch: the centre of mass of a block, the edge of a circle
  (`cx + r * cos θ`), the wall of a pipe. An arrow meant to "start at the
  centre" starts at the computed centre. Arrows meant to be equal get one
  length variable.
- **Intersections are solved.** A point where two curves cross, or where a
  tangent touches, is computed (bisection is enough) and then used for the
  marker, the label and any line through it.
- **Things that line up share a coordinate.** Labels meant to be
  horizontally aligned use one `y`. A label "centred on the arrow" uses the
  arrow's mid `x` with `anchor="middle"`.

## 4. Labels

- Put a label next to what it names, close but clear of every stroke. A
  label 4 to 8 px from its curve reads as belonging to it. Further than
  about 20 px it needs a leader line.
- Put a label where it does not widen the figure. A label hanging off the
  left end of an arrow extends the viewBox. Moving it below the arrow near
  its start keeps the figure narrow.
- In a dense plot use `place_label`. Sample every curve you draw into a list
  of points (one every few pixels), keep the boxes of labels already placed,
  and let it search:

  ```python
  geo, placed = [], []
  pts = [(sx(v), sy(k / v)) for v in vs]
  geo += pts
  svg, box = place_label(geo, placed, x1, y1, "*T*~1~")
  placed.append(box); b.append(svg)
  ```

- A legend or annotation that has to go inside a plot goes in the emptiest
  region, and must not cross any curve. Two stacked annotations share a left
  edge and a normal line spacing.
- State numbers: `state(cx, cy, 1)`, never a circled-digit character, which
  vanishes from the PDF.

## 5. Symbols the fonts get wrong

Combining accents do not compose in either renderer (cairosvg for the PDF,
browsers for the web), so a label typed with one shows a dotted circle.

- Precomposed letters are fine: Ã, Ṽ, Ĥ, Ŝ, ṁ, Ṡ, Ṅ.
- No precomposed form exists for Q̇, V̂, H̃. Use
  `label(x, y, [("*Q*", "dot"), ("~in~", None)])`.
- A lone dotted capital (Ẇ): `dotted(x, y, "W")`. The precomposed glyph's dot
  is faint and off-centre.
- Circled digits, primes, and other rare symbols: draw them, or use a plain
  alternative ("state 1", `*x*'` is fine as an ASCII apostrophe in the
  mini-syntax).

## 6. Plots

- Axes are arrows from a common origin, labelled at their far ends.
- Tick marks, when the original has a scale: major ticks with numbers, minor
  ticks as short unlabelled strokes (every 1 unit, say, when majors are every
  5). Compute tick positions from the same transform as the data.
- Isolines and families of curves (several isotherms, V = constant lines)
  are each labelled once, near an end, on the side away from the others.
- A process path on a diagram carries arrow heads along the curve in the
  direction of the process. Check each direction against the original.
- Where the original plots data from a table, draw from the transcribed
  table, not by tracing the plot.

## 7. Diagrams of equipment

- Openings are gaps: an inlet or outlet is a break in the outline, not a
  line across it.
- A control volume is a dashed outline a little inside or outside the solid
  one, at a constant offset, and any smaller control surfaces at the inlets
  sit inside it.
- Connections are drawn as the original draws them. A shaft is a line. A
  pipe or tube is two parallel lines. Lines that cross a component are drawn
  across it.
- Valves are two opposed triangles meeting at a point; a knob is a stem from
  that point to a partial circle. Keep such symbols small relative to the
  pipes.

## 8. Three-dimensional sketches

Build surfaces as flat patches in three dimensions, project them with an
oblique projection, and draw back to front. Decide which edges are hidden by
comparing depth along the view vector, and dash those. Orientation matters:
check which surface is "more horizontal" and which "more vertical" in the
original, and that shared edges (the line where two surfaces meet) are
computed from both, not drawn separately.

## 9. Look at every figure you change

Render and look before handing a figure back. The contact sheet puts several
figures on one image, and `--original` sets the original beside the figure
that follows it, at the same height:

```
python3 <skill>/scripts/contact_sheet.py work/sheet.png \
    --original originals/03.pdf 4 0.05 0.40 0.60 0.75 figures/fig_c03_02_*.svg \
    --original work/03/zoom-6.png figures/fig_c03_05_*.svg
```

Pair every figure that redraws something in an original. Compare the two
images item by item against the inventory from section 1: count the curves,
read each arrow's direction, check what is open, where each label sits and
what is hatched. A redraw looked at alone gets compared with a memory of the
sketch, and that is where a reversed axis or a closed lid gets through.

cairosvg renders the sheet, which is also what the PDF build uses, so what
you see is what the PDF will show. Check each item the author raised, then
look for the usual faults: label on a line, arrow short of its target, curve
off-centre, wrong curvature, empty margins, a missing glyph (a box or a
dotted circle). Send the sheet with the reply so the author can judge
without building anything.

Then run `python3 scripts/figures_audit.py`. A renamed figure leaves its old file
behind, and the audit catches it.

## 10. Writing the caption and alt text

The caption is the long description and is visible to every reader. Start
with a bold short title, then describe everything that carries meaning: the
axes and what they measure, each curve and its shape and label, each arrow
and what it indicates, what is dashed and why. Describe the figure as drawn,
in the order a sighted reader would take it in. Use inline mathematics for
symbols, since it is read properly by a screen reader.

The `alt` attribute is one sentence saying what the figure is. It does not
repeat the caption.

When a figure changes, update the caption in the same edit: a moved label,
a reversed arrow or a changed curvature makes the old description wrong.

A caption written only from the redraw repeats the redraw's mistakes, so
read it against the original too. Every count, direction and position it
states should match the inventory from section 1. Where the caption and the
original disagree, the drawing is wrong as well.
