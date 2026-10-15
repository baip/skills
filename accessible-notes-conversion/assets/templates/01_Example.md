---
title: "Example Lecture — {{TITLE}}"
docheading: "Example Lecture"
lang: en
runningfoot: "{{SHORT}} — Example Lecture"
description: "{{SHORT}} Example lecture notes: a worked sample that exercises every part of the pipeline. Replace it with the first real document."
subtitle: "{{TITLE}}."
---

## Typed text and a display equation

This paragraph stands for typed text in the original. Inline mathematics is
LaTeX between single dollar signs, such as $P\tilde{V} = RT$, and a display
equation sits in an `eq` block:

::: eq
$$\mathrm{d}\tilde{H} = \left(\frac{\partial \tilde{H}}{\partial T}\right)_{P} \mathrm{d}T + \left(\frac{\partial \tilde{H}}{\partial P}\right)_{T} \mathrm{d}P$$
:::

Sums, products and integrals keep their limits as the original writes them:

::: eq
$$U = \sum_{i=1}^{N} n_{i} \tilde{U}_{i}, \qquad S(T) = \int_{0}^{T} \frac{C_{P}}{T'} \mathrm{d}T'$$
:::

## A hand annotation, typeset with a spoken form

In the original the last term is struck through and marked zero. The
equation shows both marks and carries a sentence for a screen reader:

::: {.eq alt="d U equals delta Q plus delta W, plus the enthalpy H tilde times d n, where the last term is struck out and marked zero."}
$$\mathrm{d}U = δQ + δW + \underbrace{\cancel{\tilde{H} \, \mathrm{d}n}}_{0}$$
:::

## A figure and a table

The curve in [](#fig-e01-01) is drawn from its equation rather than traced.

![**A falling isotherm.** Pressure is on the vertical axis and volume on the horizontal axis. A single convex curve, $PV$ constant, falls from the upper left to the lower right, and a dot marks the state $(V_{1}, P_{1})$ on it.](../figures/fig_e01_01_isotherm.svg){#fig-e01-01 width=360 alt="A pressure-volume diagram with one falling convex isotherm and a marked state V sub 1, P sub 1."}

| State | $T$ | $P$ |
|:------|:----|:----|
| 1     | $T_{1}$ | $P_{1}$ |
| $\vdots$ | $\vdots$ | $\vdots$ |
| $N$   | $T_{N}$ | $P_{N}$ |
