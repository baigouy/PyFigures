# Portable fonts

Drop redistributable `.ttf` / `.otf` font files here and PyFigures registers
them automatically at startup (via `QFontDatabase.addApplicationFont`), on
**every** operating system — no system install needed. Fonts placed here travel
with the app, so figures render identically on any machine, and exported PDFs
embed them.

## Getting a portable Helvetica / Arial

Helvetica and Arial themselves are proprietary and cannot be shipped. Use a
freely redistributable, metric-compatible clone instead — visually and
metrically equivalent for publication:

| You want   | Drop-in clone            | License        |
|------------|--------------------------|----------------|
| Helvetica  | **TeX Gyre Heros**       | GUST (permissive) |
| Helvetica  | Nimbus Sans              | AFPL / GPL     |
| Arial      | **Arimo**                | Apache-2.0     |
| Arial      | Liberation Sans          | OFL / GPL+FE   |

Download the `.ttf`/`.otf` files and copy them into this folder. On next launch
they appear in the font picker, and requesting "Helvetica"/"Arial" resolves to
them automatically (see `portable_fonts.py`).

If none is present, PyFigures falls back to **DejaVu Sans** (bundled with
matplotlib, always available) so text is never lost to a random system font —
though DejaVu is not Helvetica-metric.
