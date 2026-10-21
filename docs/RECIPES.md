# PyFigures recipes — the complete guide

A **recipe** is a short text file (YAML or JSON) that describes a figure: which
images and data go in which row, how they look, and what size the figure must be.
PyFigures reads it and builds a normal `.pyf` figure — the same file you get when
you build a figure by hand, so you can open it in the GUI and keep polishing it.

```yaml
output: Figure1.pyf
journal: nature
rows:
  - [wt.tif, mutant.tif]
  - - {plot: counts.csv, kind: box, ylabel: "cells / field"}
```

That's a complete, valid recipe: two micrographs on top, a box plot with
statistics below, lettered A–C, sized for a Nature single column.

**Why recipes?**

- **Reproducible** — rebuilding the same recipe gives the same figure, byte for byte.
- **Re-runnable** — new data? Rebuild. Plots and their statistics are recomputed.
- **Diff-able** — a recipe is 10–30 lines of text: put it in git next to your analysis.
- **Fast** — the layout, lettering, sizing and caption stub are automatic.

Contents

1. [Running a recipe](#1-running-a-recipe)
2. [File structure](#2-file-structure)
3. [Figure-level keys](#3-figure-level-keys)
4. [Rows and panels](#4-rows-and-panels)
5. [`defaults`](#5-defaults)
6. [Image panels — `image`](#6-image-panels--image)
7. [Many images at once — `glob`](#7-many-images-at-once--glob)
8. [Data plots — `plot`](#8-data-plots--plot)
9. [Stacks: one image by default](#9-stacks-one-image-by-default)
10. [Time / Z montage — `montage`](#10-time--z-montage--montage)
11. [Channel split — `split`](#11-channel-split--split)
12. [Arrows — `arrows`](#12-arrows--arrows)
13. [Kymograph — `kymograph`](#13-kymograph--kymograph)
14. [Orthogonal views — `orthogonal`](#14-orthogonal-views--orthogonal)
15. [Text, corner labels, ROIs and brackets](#15-text-corner-labels-rois-and-brackets)
16. [Insets and zoom callouts](#16-insets-and-zoom-callouts)
17. [Rotation, flips, channels and display range](#17-rotation-flips-channels-and-display-range)
18. [More panel kinds — `merge`, `colorbar`, `script`, `equation`](#18-more-panel-kinds--merge-colorbar-script-equation)
19. [Row options — columns, spacing, label rows, side labels](#19-row-options--columns-spacing-label-rows-side-labels)
20. [Finishing — size, fonts, metadata, alt text, style, exports, checks, templates](#20-finishing--size-fonts-metadata-alt-text-style-exports-checks-templates)
21. [Scale bars and crops](#21-scale-bars-and-crops)
22. [Labels, letters and backgrounds](#22-labels-letters-and-backgrounds)
23. [Reference tables](#23-reference-tables) — LUTs, colours, journals, placements
24. [Errors and validation](#24-errors-and-validation)
25. [Cookbook](#25-cookbook)
26. [Same features in the GUI and the MCP server](#26-same-features-in-the-gui-and-the-mcp-server)
27. [Tips and gotchas](#27-tips-and-gotchas)

---

## 1. Running a recipe

Three equivalent ways:

| Where | How |
|---|---|
| **Command line** | `python -m pyfigures.recipe build fig1.yaml` |
| **GUI** | *File → Build figure from recipe…* — builds, then opens the figure |
| **MCP server** | `build_figure_from_recipe("fig1.yaml")` |

Command-line options:

```bash
python -m pyfigures.recipe build fig1.yaml                 # build the .pyf
python -m pyfigures.recipe build fig1.yaml --render png    # + export fig1.png next to it
python -m pyfigures.recipe build fig1.yaml fig2.yaml fig3.yaml --render pdf
```

- `--render EXT` also exports each built figure (`png`, `tif`, `jpg`, `svg`,
  `pdf`) next to its `.pyf`, at 300 DPI.
- The command prints a JSON summary per recipe (rows, panels, lettered panels,
  journal, warnings).
- It **exits with status 1** if any recipe fails — including a failed
  `--render` export — so it works as a Makefile target or a pipeline step. The
  other recipes of the same command are still built.
- Rebuilding replaces the figure's statistics record and alt text, so the
  Methods text only ever lists the tests of the panels now in the recipe.

```make
figures/Figure1.pyf: fig1.yaml data/*.tif data/counts.csv
	python -m pyfigures.recipe build fig1.yaml --render pdf
```

YAML needs PyYAML (`pip install pyyaml`); a `.json` recipe needs nothing.

---

## 2. File structure

```yaml
# ── figure-level keys ─────────────────────────────
output: figures/Figure1.pyf      # required
journal: nature
column: double
title: "Figure 1"
caption: "…"
letter_panels: true
spacing: 3
background: white
label_background: black

defaults:                         # ── applied to every panel that doesn't override
  px_to_unit: 0.1
  scale_bar: {units: 10, unit: "µm"}

rows:                             # ── the figure, top to bottom
  - - {image: a.tif, lut: green}          # row 1, panel 1
    - {image: b.tif, lut: magenta}        # row 1, panel 2
  - - {plot: counts.csv, kind: bar}       # row 2
```

YAML reminders:

- Indentation is meaningful — use spaces, never tabs.
- `- - {…}` starts a new row whose first panel is `{…}`; a following `- {…}`
  at the inner indentation adds a panel to that same row.
- A panel can be written inline `{image: a.tif, lut: red}` or as a block:

  ```yaml
  - - image: a.tif
      lut: red              # aligned with "image"
      crop: {left: 20}
  ```
- Quote text containing `:` or `#`, and anything that YAML might read as a
  number or boolean you want kept as text (`"1.5"`, `"yes"`).
- `#` starts a comment.

The same recipe as JSON:

```json
{"output": "figures/Figure1.pyf", "journal": "nature", "column": "double",
 "rows": [[{"image": "a.tif", "lut": "green"}, {"image": "b.tif", "lut": "magenta"}],
          [{"plot": "counts.csv", "kind": "bar"}]]}
```

**Paths.** Every path (`output`, images, CSVs, globs) is relative to the recipe
file's folder, unless absolute. `~` is expanded. Folders for `output` are
created as needed. Forward slashes work on every OS.

---

## 3. Figure-level keys

| Key | Default | What it does |
|---|---|---|
| `output` | — **required** | The `.pyf` to write (must end in `.pyf`). Overwritten on rebuild. |
| `rows` | — | The figure as a list of rows (see §4). Give `rows`, `panels` **or** `layout`. |
| `panels` | — | A flat list of panels, cut into rows of `columns` panels; with `layout`, a mapping *id: panel*. |
| `columns` | all in one row | Panels per row when using `panels`. |
| `layout` | — | The whole layout as one formula, e.g. `"(a,b,c)/(d,e,f)"` or `"(a,(b/c))/d"` (see §4b). |
| `journal` | none | Size the figure for a journal (see §23). Omit to keep the natural size. |
| `column` | `single` | One of the sizes that journal gives: `single`, `1.5`, `double`, `triple` (also `1 column`, `2 columns`, `3 columns`, `full width`; `half page` = an estimate, only for journals giving just a full width). |
| `letter_panels` | `true` | Add A, B, C… to the top-left corner of each panel. Must be an unquoted `true`/`false` (`"false"` in quotes is refused, not read as yes). |
| `title` | `"Figure"` | Title stored with the caption. |
| `caption` | auto stub | Figure legend. Omitted → a stub listing the panels — `(A) wt; (B) ko; (C) data plot. [Describe …]` — to complete. Stored in `<figure>.caption.json`; export it with the caption tools. |
| `spacing` | `3` | Gap between panels and between rows (points; a whole number ≥ 0). Also used inside montages and channel splits. |
| `background` | none (transparent) | Colour of the whole figure behind the panels — i.e. of every gap between them. `white` keeps separators white in any viewer; `black` for dark figures. See §22. |
| `label_background` | none | Filled box behind every label (letters, labels, time stamps, channel names), e.g. `black`. See §22. |
| `defaults` | none | Options applied to all panels (§5). |
| `width_mm` / `width_cm` / `width_in` / `width_px` | none | An explicit figure width instead of a `journal` (give one, never with `journal`). §20. |
| `dpi` | `300` | Resolution used for the size in physical units. |
| `letter_placement` | `top left` | Corner of the panel letters. |
| `font` | none | Figure font: a family name, or a mapping with `family`, `size`, `italic`. §20. |
| `min_font_pt` | none | Raise every smaller text to this size (journal minimum). |
| `colors` | none | Recolour the whole figure: channel *i* of every multi-channel image, merge and channel split takes colour *i* — `colors: [magenta, green]` turns a red/green/blue figure magenta/green/blue. Single-channel panels outside a split become gray; RGB colour photographs (bright background) are left alone. A plot with exactly as many groups as colours takes them; other plots take the colour-blind-safe Okabe–Ito palette. `colors: [colorblind]` = magenta/green channels + Okabe–Ito for every plot. MCP `set_figure_colors`; GUI Annotations → Figure colours…. |
| `fit_height` | `shrink` | When the figure is taller than the journal's maximum height (Nature 247 mm, PLOS 222.3 mm, PNAS 225 mm, or an imported style's height rule) or `max_height_mm`: `shrink` narrows it until it fits, `column` uses the widest journal column it fits in, `off` keeps the width. The build warning lists the other choices. |
| `max_height_mm` | none | A maximum figure height of your own (overrides the journal's). |
| `tidy_text` | `false` | Typography clean-up of every label (`2*3`→`2×3`, `37 degrees C`→`37 °C`, `10µm`→`10 µm`, `10-20`→`10–20`). |
| `auto_configure` | `false` | Read pixel sizes / channel counts from the files' metadata: LUT preset + scale bars. Explicit panel settings still win. §20. |
| `alt_text` | none | `auto` (drafted from the panels) or the alt text itself. |
| `copy_style_from` | none | Another `.pyf` whose look (fonts, letters, scale bars, spacing, plots) is copied; `copy_style_aspects` limits what. |
| `exports` | none | Files to write after building: `[pdf, png, svg, tif, jpg, latex, print, video, source_data, review, caption, ledger, colorblind, pptx, illustrator, vectorcraft, deckcraft]`. §20. |
| `allow_scripts` | `false` | Must be `true` for `script:` panels (they run Python code). §18. |
| `checks` | none | Checks run after the build — `integrity`, `scale`, `scale_bars`, `labels`, `resolution`, `journal`; a failing one stops the build before the exports. §20. |
| `consolidate` | `false` | `true`: copy every source file into `<figure>.files/` and link the figure to the copies; or a `.pyf` path to write that self-contained copy elsewhere. §20. |
| `download_remote` | `false` | With `consolidate`: also save remote images (web links, OME-Zarr URLs, OMERO links) into the bundle instead of keeping their links. §20. |
| `template` + `fill` | none | Build from a template `.pyf` (instead of `rows`): `fill` lists the image files (or globs) for its slots, in order. §20. |

Multi-line captions — use YAML's folded style:

```yaml
caption: >
  (A–B) WT and KO guts stained for actin (63×). (C) Cells per field;
  one-way ANOVA with Tukey HSD. Scale bars, 10 µm.
```

---

## 4. Rows and panels

Each row is scaled to the **full figure width**, with all its panels at a
**common height** (keeping each panel's aspect ratio). Rows are stacked top to
bottom, `spacing` apart.

Every panel is a mapping with **exactly one** *kind* key naming its source:

| Kind key | Source | Makes |
|---|---|---|
| `image` | an image file | one panel |
| `glob` | a file pattern | one panel per matching file |
| `plot` | a CSV of measurements | one chart panel with statistics |
| `montage` | a time-lapse or Z stack | one panel per chosen frame (a sub-row) |
| `split` | a multi-channel image, or a list of channel files | one panel per channel + merge |
| `merge` | a list of single-channel files | one colour overlay panel (§18) |
| `colorbar` | a LUT name | a calibration bar for that LUT (§18) |
| `script` | Python code | a generated panel, e.g. a matplotlib model (§18) |
| `equation` | LaTeX mathematics | a typeset equation, as a vector panel (§18) |
| `tex` | LaTeX code | a TikZ / pgfplots picture, a table or a document, compiled into a vector panel (§18) |

A row can also be a mapping with its own options (§19):

```yaml
rows:
  - panels: [wt.tif, ko.tif]
    labels: [WT, KO]          # a label row above the panels
    side_label: "Day 1"
  - orientation: Y            # a column instead of a row
    panels: [a.tif, b.tif]
```

**Shorthand:** a bare file name is an image panel with no options, so a row of
plain images can be written `- [wt.tif, ko.tif]` (same as
`- [{image: wt.tif}, {image: ko.tif}]`).

**Flat list shortcut** — the same grid without writing rows:

```yaml
output: grid.pyf
columns: 3
panels:
  - {image: a.tif}
  - {image: b.tif}
  - {image: c.tif}
  - {image: d.tif}      # → second row
```

Any image PyFigures opens can be used — TIFF / OME-TIFF / ImageJ hyperstacks,
PNG, JPG and the microscopy formats of your install. For multi-series files,
pick the series with `series` in `montage` / `split`, or in the GUI.

---

## 4b. Layout formulas — `layout`

Instead of `rows`, the whole layout fits on one line; each panel is then
defined once, under `panels:` (a mapping *id: panel*):

```yaml
output: fig2.pyf
layout: "(split, plot) / [wt, ko / rescue, ctrl]"
panels:
  split: {split: cells.tif, names: [DNA, actin], crop: {bottom: 20}}
  plot:  {plot: counts.csv, kind: box, annotate_stats: true}
  wt: wt.tif
  ko: ko.tif
  rescue: {image: rescue.tif, lut: green, scale_bar: {units: 10, unit: um}}
  ctrl: ctrl.tif
```

| Symbol | Meaning |
|---|---|
| `,` or `\|` | side by side |
| `/` | stacked; `,` binds tighter, so `a,b/c,d` is the row `a,b` over the row `c,d` |
| `( )` | a group, nested to any depth; a group spans the rows / columns it holds: `(a,(b/c))/d` puts `a` beside `b` over `c` (a panel two rows high) |
| `[ ]` | a grid: every cell is centre-cropped to the grid's most common aspect ratio, so rows have equal heights and columns line up (the build lists each crop). Plain groups keep each image's own aspect ratio, without cropping |

Spaces are only for reading: `a|b|c / d|e|f` = `(a,b,c)/(d,e,f)`.

**Ids, not positions.** A name in the formula is a panel id from `panels:`
(any panel kind, with all its keys), a file name (`a.png`, when it has no
`, / ( ) [ ] |` or spaces), or the name of exactly one file next to the recipe
(`a` → `a.png`; two candidates such as `a.png` and `a.tif` are an error, never
a guess). Panel letters follow the formula's reading order and are
regenerated on every build; an id always keeps its source and settings.
Errors are reported before anything is built: an id placed twice, an id in
`panels:` missing from the formula, an unknown id, unbalanced brackets (the
message points at the character).

`python -m pyfigures.layout_formula "(a,(b/c))/d"` prints how a formula is
read. The parenthesised comma/slash notation is inspired by
[Griphus](https://www.systaxon.ufes.br/gri/) (Systaxon, UFES), which builds
figure plates from formulas such as `((1/5),(2/(3,4)/6))`.

**Layout pictures.** `layout` can also be drawn, one line per row of panel
ids separated by spaces; repeating an id makes the panel span several cells:

```yaml
layout: |
  a a b
  a a c
  d e f
```

Every line needs the same number of cells. A single line of several ids
(`layout: "split image plot"`) is one row.

---

## 5. `defaults`

Keys in `defaults` apply to every panel **for which they make sense**; a panel's
own value always wins.

Allowed in `defaults`:

| For images / globs | For plots |
|---|---|
| `lut`, `crop`, `scale_bar`, `px_to_unit`, `projection`, `rotate`, `flip`, `channels`, `z_range`, `display_range` | `kind`, `error`, `ylabel`, `xlabel`, `stats_mode`, `annotate_stats`, `only_significant` |

`lut` and `projection` also reach `montage` panels, and `projection` reaches
`split` panels. `scale_bar` and `px_to_unit` reach montages and splits too: the
bar goes on their **last** panel only (one bar per series, not one per frame).
Per-panel-only keys (`label`, `title`, `arrows`, `kymograph`, `orthogonal`,
`text`, `corner_labels`, `rois`, `inset`, `zoom`, `brackets`) are refused in
`defaults` (and on a `glob`, where they would repeat on every match).

```yaml
defaults:
  lut: gray
  px_to_unit: 0.108          # µm per pixel for the whole figure
  scale_bar: {units: 10, unit: "µm"}
  kind: box                  # all plots are box plots
  ylabel: "intensity (a.u.)"
rows:
  - - {image: ctrl.tif}
    - {image: drug.tif, scale_bar: {units: 5}}      # overrides the bar length
  - - {plot: ctrl_vs_drug.csv}
```

---

## 6. Image panels — `image`

```yaml
- - image: cells.tif
    lut: [green, magenta]
    projection: max
    crop: {left: 20, right: 20, top: 0, bottom: 10}
    px_to_unit: 0.1
    scale_bar: {units: 10, unit: "µm", color: white, placement: bottom right}
    label: WT
    arrows: [{at: [412, 230], from: ne}]
    kymograph: {line: [40, 150, 200, 150]}
    orthogonal: {at: [200, 180]}
```

| Key | Values | Meaning |
|---|---|---|
| `image` | path or URL | The image file — or an http(s) URL, or an **OME-Zarr** image: a local `.zarr` folder or a URL such as `https://…/image.zarr` (needs `pip install pyfigures[zarr]`). OME-Zarr reads the largest pyramid level within 512 MB / 8192 px, with the pixel size and channel colours of the file; add `#level=N` to the path to choose a level. An image on an **OMERO** server is given by its OMERO.web link (`https://…/webclient/img_detail/1234/`; add `#z=0-9&t=0` to choose planes; private servers need `OMERO_USERNAME` / `OMERO_PASSWORD` in the environment). A **PDF** (e.g. a plot from Matplotlib, pgfplots or gnuplot; needs `pip install pyfigures[pdf]`) or an **SVG** file is a vector panel and stays vector in PDF/SVG exports, clipping included. |
| `page` | 1, 2, … | For a multi-page PDF: the page to show (default: the first). |
| `lut` | a name, or a list with one entry per channel | Colour look-up table(s), e.g. `gray`, `green`, `[red, green, blue]`, `MATPLOTLIB_magma`. `null` in a list leaves that channel as is. Case-insensitive. See §23. |
| `projection` | `max`, `min`, `avg`, `none` | How a Z stack is shown as one image. Without it a Z stack shows its **first slice**. |
| `crop` | `{left, right, top, bottom}` | Pixels removed from each edge of the raw image (non-negative integers; give only the sides you need). |
| `px_to_unit` | number | Pixel size in physical units (e.g. `0.1` = 0.1 µm/px). Needed for correct scale bars. |
| `scale_bar` | mapping | See §21. |
| `label` | text | A label in the top-left corner, stacked **under** the panel letter (white, like the letters). May be rich text: `"<i>unc-5</i>"`, `"H<sub>2</sub>O"`; text without tags is shown as written (`"p < 0.05"`, `"WT & KO"`). A single letter (`"D"`) is treated as the panel's letter. |
| `arrows` | list | Arrows pointing at features (§12). |
| `kymograph` | mapping | Adds a kymograph panel after this one (§13). |
| `orthogonal` | mapping | Adds an orthogonal-views panel after this one (§14). |
| `text`, `corner_labels`, `rois`, `brackets` | | Text, labels, shapes and significance brackets drawn on the panel (§15). |
| `inset`, `zoom` | | A second image inset in a corner; a magnified region with leader lines (§16). |
| `rotate`, `flip`, `channels`, `z_range`, `display_range` | | Rotation, mirroring, visible channels, Z slices projected, fixed intensity window (§17). |
| `properties` | mapping | Escape hatch: any stored panel field by name, e.g. `{border_size: 3, border_color: "0xFF0000", opacity: 0.5}`. Names are checked against the panel's real fields (a typo is an error); the file, the code (`custom_loading_script`) and the layout fields (`x`, `y`, `width`, …) can't be set this way. Use the dedicated keys when there is one. |

Options are applied in this order: kymograph / orthogonal views (added right
after the panel) → `auto_configure` → projection, channels, Z range, display
range → LUT → crop, rotation, flip → scale bar → text → corner labels → ROIs →
arrows → brackets → insets → zoom callouts → `properties`.

---

## 7. Many images at once — `glob`

```yaml
- - {glob: "replicates/rep*.tif", lut: gray, crop: {top: 10}}
```

Adds one panel per matching file, **sorted by name**, all in the same row with
the same options. Accepts the image keys except the per-image ones (`label`,
`arrows`, `kymograph`, `orthogonal`). Wildcards: `*` (any text), `?` (one
character), `[0-9]` (a range). A glob that matches nothing is an error.

Tip: to get replicates on several rows, use one `glob` row per group
(`"ctrl_*.tif"`, `"drug_*.tif"`).

---

## 8. Data plots — `plot`

```yaml
- - plot: data/counts.csv
    kind: box
    error: sem
    ylabel: "cells / field"
    xlabel: ""
    title: ""
    stats_mode: auto
    annotate_stats: true
    only_significant: true
    label: ""
```

A plot panel is **live**: it is re-rendered from the CSV whenever the figure is
opened, so a rebuild or a re-open picks up new data. Requires the `staplot`
package (bundled with PyFigures installs; otherwise the panel shows an install
hint instead of failing).

| Key | Values (default) | Meaning |
|---|---|---|
| `plot` | path to a CSV | The data (formats below). |
| `kind` | `bar` (default), `box`, `violin`, `scatter`, `grouped` | Chart type. |
| `error` | `sem` (default), `sd`, `ci95`, `none` | Error bars for `bar` / `grouped`. |
| `ylabel`, `xlabel`, `title` | text | Axis labels / title. |
| `stats_mode` | `auto` (default), `parametric`, `nonparametric` | Test family. `auto` picks by a normality check. |
| `annotate_stats` | `true` (default) | Compare groups and draw significance brackets. |
| `only_significant` | `true` (default) | Draw brackets only for p < 0.05 (all comparisons are still recorded). |
| `label` | text | Corner label on the chart. |
| `colors` | list | One colour per group, in the CSV's order (`[magenta, green]`, `#rrggbb`). |

CSV formats:

- `bar`, `box`, `violin`, `scatter` — **wide** (one column per group, one row
  per replicate; columns may have different lengths) or **long** (2 columns:
  group, value).
- `grouped` — **long** with 3 columns: factor A, factor B, value.

```text
WT,KO,Rescue          group,value          genotype,treatment,value
10,20,12              WT,10                WT,ctrl,10
11,22,13              WT,11                WT,drug,14
12,21,                KO,20                KO,ctrl,20
```

Statistics used: 2 groups → Welch t-test / Mann–Whitney; > 2 groups → ANOVA +
Tukey / Kruskal–Wallis + Dunn; `scatter` → correlation (r, R², p) in the legend;
`grouped` → two-way ANOVA printed under the axes. The chosen tests and every
p-value go to `<figure>.stats.json` — ready for the Methods section (the
adjustment-ledger export turns it into a paragraph).

Charts have white backgrounds, so their letters are black.

---

## 9. Stacks: one image by default

A time-lapse, Z stack or multi-channel file placed with `image:` becomes **one
panel**, because that's what most figures want:

- a **Z stack** shows its first slice — add `projection: max` (or `avg`, `min`)
  to show a projection instead;
- a **time series** shows its first time point;
- **channels** are all shown, merged with their LUTs (set them with `lut:`).

Showing several views of a stack is **opt-in**, with the dedicated panel kinds
and options below: `montage` (frames side by side), `split` (channels side by
side), `kymograph` and `orthogonal`.

Physical sizes (pixel size, Z step, time interval) are read from the file
metadata when present — ImageJ TIFF, OME-TIFF, LSM, and the Bio-Formats readers.

---

## 10. Time / Z montage — `montage`

```yaml
- - montage: embryo.tif
    axis: t
    frames: 5
    columns: 5
    projection: max
    channel: 1
    lut: gray
    interval: 2
    unit: min
    stamps: true
    stamp_format: "{value:g} {unit}"
    stamp_placement: top right
    stamp_color: white
    time_zero: 0
    series: 0
```

Shows several frames of **one** stack side by side, with time (or depth)
stamps: `0 min, 2 min, 4 min…`. The montage is a single figure panel: it gets
one letter.

| Key | Values (default) | Meaning |
|---|---|---|
| `montage` | path | The stack. |
| `axis` | `t` (default) or `z` (also `time`, `depth`) | Which axis to lay out. |
| `frames` | (6 evenly spaced) | Which frames — see below. Frame numbers start at **0**. |
| `columns` | all in one row | Wrap into rows of this many frames. |
| `projection` | `max` (default), `min`, `avg`, `none` | For a time montage of a 3-D stack: how each time point's Z is shown (`none` = first slice). |
| `channel` | channel number (from 0) | Show only this channel. Default: all channels. |
| `lut` | name or list per channel | Colours. |
| `interval` | number | Time (or Z step) per frame; overrides the file's value. |
| `unit` | text, e.g. `s`, `min`, `h`, `µm` | Unit for the stamps; overrides the file's. |
| `stamps` | `true` (default) | Add the stamps. |
| `stamp_format` | Python format, e.g. `"t = {value:g} {unit}"` | Stamp text. `{value}` and `{unit}` are replaced. |
| `stamp_placement` | `top right` (default) | Corner of the stamp (the letter takes top left). |
| `stamp_color` | `white` (default) | Stamp colour. |
| `time_zero` | frame number | Frame whose stamp reads 0 (default: the first frame shown) — e.g. the frame of drug addition, so earlier frames read negative. |
| `series` | number | Series of a multi-series file (.lif, .czi…). |
| `scale_bar`, `px_to_unit` | as for images (§21) | Scale bar on the **last** frame (also taken from `defaults`). |

`frames` forms:

| Written | Frames shown (for a 17-frame stack) |
|---|---|
| *(omitted)* | 6 evenly spaced, first and last included: 0, 3, 6, 10, 13, 16 |
| `5` | 5 evenly spaced: 0, 4, 8, 12, 16 |
| `all` | every frame |
| `"0:10:2"` | 0, 2, 4, 6, 8 (Python slice: start, stop excluded, step) |
| `"::5"` | every 5th frame: 0, 5, 10, 15 |
| `[0, 5, 9]` | exactly those |

Without a time interval in the file and no `interval:`, stamps read
`frame 1, frame 2…`. For a Z montage the step defaults to the voxel depth.

A montage can share a row with other panels: it is placed as a sub-group
inside the row.

---

## 11. Channel split — `split`

```yaml
- - split: cells.tif                      # one multi-channel image…
    names: [DAPI, GFP, RFP]
    colors: [blue, green, magenta]
    gray: true
    merge: true
    merge_label: Merge
    projection: max
    frame: 0
    series: 0
    label_placement: top right

- - split: [dapi.tif, gfp.tif, rfp.tif]   # …or one file per channel
    names: [DAPI, GFP, RFP]
```

The classic channel row: each channel on its own panel, then the merge. One
figure panel → one letter.

| Key | Values (default) | Meaning |
|---|---|---|
| `split` | a path, or a list of paths | One multi-channel image/stack, **or** one single-channel file per channel (≥ 2). |
| `names` | list of text (`Ch1`, `Ch2`…) | Channel names written on the panels. |
| `colors` | list (2 ch: green, magenta; 3 ch: red, green, blue; 4 ch: + gray) | Channel colours in the merge: `gray`, `red`, `green`, `blue`, `cyan`, `magenta`, `yellow`. |
| `gray` | `true` (default) | Single channels in **grayscale** with their name in the channel colour — the most legible and colour-blind-safe choice. `false` tints each panel in its colour. |
| `merge` | `true` (default) | Add the merge panel at the end. |
| `merge_label` | `Merge` | Label of the merge (`""` = none). |
| `projection` | `max` (default), `min`, `avg`, `none` | Z projection for 3-D stacks (same for every panel). |
| `frame` | `0` | Time point for time series (must exist in the stack). |
| `series` | number | Series of a multi-series file. |
| `label_placement` | `top right` (default) | Corner for the channel names. |
| `scale_bar`, `px_to_unit` | as for images (§21) | Scale bar on the **last** panel (the merge, if any; also taken from `defaults`). |

The numbers of `names` and `colors` must match the number of channels.

---

## 12. Arrows — `arrows`

```yaml
- - image: embryo.tif
    arrows:
      - {at: [412, 230], from: ne}
      - {at: [120, 150], from: s, color: yellow, head: large, label: "nucleus"}
      - {at: [300, 80], from: 30, length: 60, stroke: 1.5, both_ends: true}
```

You give **where the arrow points** — the tip — not a line. The tip sits
exactly on that pixel, and stays there at any panel size, zoom or export
resolution: the arrowhead keeps a constant size on the page and grows
backwards from the tip.

| Key | Values (default) | Meaning |
|---|---|---|
| `at` | `[x, y]` — **required** | The tip, in image pixels of the raw image (0, 0 = top-left corner; same numbers as Fiji's cursor readout). |
| `from` | `top left` / `nw` (default) | Side the arrow comes from: `n`, `ne`, `e`, `se`, `s`, `sw`, `w`, `nw`, or words (`top`, `bottom right`, `left`, `above`, `below`…), or an angle in degrees (0 = from the right, 90 = from above, counter-clockwise). |
| `length` | 20 % of the image's shorter side | Shaft length in image pixels. Shortened automatically to stay inside the image. |
| `color` | `white` | Name, `#rrggbb` or number. |
| `stroke` | `1.0` | Line width in points on the page. |
| `head` | `normal` | `small`, `normal` or `large`. A normal head is 8× the stroke long (8 pt ≈ 2.8 mm at 1 pt). |
| `both_ends` | `false` | Heads at both ends. |
| `label` | text | Text placed just beyond the tail. |

If the panel ends up so small on the page that the arrow would be mostly
arrowhead, the build prints a warning — use a longer `length`, a `small` head,
or a bigger panel.

---

## 13. Kymograph — `kymograph`

```yaml
- - image: movie.tif
    projection: max
    kymograph:
      line: [40, 150, 200, 150]
      width: 3
      channel: 0
      projection: max
      frame_height: 2
      cmap: gray
      mark_line: true
      line_color: yellow
      label: kymo
```

Adds, right after the image, a panel showing **position along a line vs time**
(time runs downwards). The source must be a **time series**.

| Key | Values (default) | Meaning |
|---|---|---|
| `line` | `[x1, y1, x2, y2]` — **required** | The line, in image pixels. |
| `width` | `3` | Pixels averaged across the line (odd numbers centre on it). |
| `channel` | `0` | Channel for multi-channel stacks. |
| `projection` | `max` (default), `avg`, `min` | How a 3-D stack's Z is collapsed at each time point. |
| `frame_height` | automatic | Rows per time point (frames are repeated, not interpolated). Default: the kymograph comes out about half as tall as wide. |
| `cmap` | `gray` | Matplotlib colour map, e.g. `magma`, `viridis`. |
| `mark_line` | `true` | Draw the sampled line on the source image. |
| `line_color` | `yellow` | Colour of that line. |
| `label` | text | Label on the kymograph. |

The kymograph keeps the source's pixel size horizontally, so a scale bar on it
measures distance along the line. The time per frame is reported in the build
output.

---

## 14. Orthogonal views — `orthogonal`

```yaml
- - image: zstack.tif
    lut: [green, magenta]
    orthogonal:
      at: [200, 180]
      z: 12
      time_point: 0
      channel: 1
      colors: [green, magenta]
      z_scale: 3.2
      gap: 4
      background: white
      crosshair: true
      crosshair_color: yellow
      label: ortho
```

Adds, right after the image, the classic three-view panel: **XY** top-left,
**YZ** on its right, **XZ** below, cut through voxel (x, y). The source must be
a **Z stack**.

| Key | Values (default) | Meaning |
|---|---|---|
| `at` | `[x, y]` — **required** | The voxel the side views cut through (image pixels). |
| `z` | maximum projection | XY slice shown; also marked in the side views. |
| `time_point` | `0` | Frame used for a time series. |
| `channel` | all channels | Show one channel in grayscale. |
| `colors` | green+magenta / RGB | Channel tints when all channels are shown. |
| `z_scale` | from the file's voxel size | Z step ÷ pixel size, so the side views have true proportions. **Required** if the file has no voxel depth. |
| `gap` | `4` | Pixels between the views. |
| `background` | `white` | Colour of the gaps / empty corner. |
| `crosshair` | `true` | Thin lines marking the cut (editable afterwards). |
| `crosshair_color` | `yellow` | Their colour. |
| `label` | text | Label on the composite. |

The composite keeps the XY pixel size, so one scale bar is correct for all
three views.

---

## 15. Text, corner labels, ROIs and brackets

Everything here is drawn **on** an image panel, in its raw-pixel coordinates
(0, 0 = top-left corner of the uncropped image), and stays editable in the GUI.

```yaml
- - image: cells.tif
    text: ["WT", {text: "n = 12", placement: bottom right}]
    corner_labels: {top_right: ["*"], bottom_left: [DAPI, GFP]}
    rois:
      - {rect: [40, 60, 120, 80], color: cyan}
      - {ellipse: [300, 200, 50, 50], color: yellow, stroke: 3}
      - {line: [10, 10, 90, 60], arrow: true}
      - {polygon: [[5, 5], [80, 10], [40, 70]], fill: red, opacity: 0.5}
      - {circle: [200, 150, 30], color: magenta}         # centre + radius
      - {square: [400, 100, 40]}                          # centre + side
      - {points: [[50, 300], [80, 310], [120, 290]], color: red, size: 8}
    brackets: [{x1: 40, x2: 200, y: 30, label: "**"}]
```

| Key | Values (default) | Meaning |
|---|---|---|
| `text` | a text, a mapping `{text, placement}`, or a list of them | Text on the panel; `placement` is a corner (default `bottom left`, so it does not sit on the letter). Plain text is white; rich text (`<i>…</i>`) is kept as written. |
| `corner_labels` | `top_left`, `top_right`, `bottom_left`, `bottom_right` → a text or a list | Labels stacked from each corner inward (two labels in one corner sit one under the other). |
| `rois` | list of shapes | Each has **one** of `rect: [x, y, w, h]`, `ellipse: [x, y, w, h]`, `line: [x1, y1, x2, y2]`, `polygon: [[x, y], …]`, `circle: [cx, cy, radius]`, `square: [cx, cy, side]`, `point: [x, y]`, `points: [[x, y], …]`, plus optional `color` (`yellow`), `fill` (none), `stroke` (2), `opacity` (1). A line takes `arrow: true` / `both_ends: true` (or use `arrows`, §12, for an arrow whose tip sits exactly on a point); a polygon `style: polyline` for an open path. Points are filled discs (fill = `color` unless given) of diameter `size` (6 px), each an editable ellipse in the GUI. |
| `brackets` | list of `{x1, x2, y}` | Significance brackets from `x1` to `x2` at height `y`, with `label` (`*`), `color` (`black`), `stroke`, `font_pt`, `tick`, `label_gap`, `whiskers` (`down`/`up`). |

To draw a bracket *from the data* (with the test run for you), use a `plot`
panel — its brackets are automatic (§8).

---

## 16. Insets and zoom callouts

```yaml
- - image: tissue.tif
    inset: {image: detail.tif, placement: top right, size: 0.3}
    zoom: {box: [300, 220, 120, 120], corner: bottom right, size: 0.4, color: yellow}
```

**`inset`** — another image shown in a corner of this one (or a list of them).

| Key | Default | Meaning |
|---|---|---|
| `image` | **required** | The inset's file. |
| `placement` | `top right` | Corner. |
| `size` | `0.25` | Inset width as a fraction of the panel width. |
| `border` | `3` | Frame thickness in px (`0` = none). |
| `border_color` | `white` | Frame colour. |

**`zoom`** — the micrograph staple: a box around a region, a magnified view of
that region in a corner, and leader lines joining them (or a list of them).

| Key | Default | Meaning |
|---|---|---|
| `box` | **required** | `[x, y, w, h]` of the region, in raw pixels. |
| `corner` | `top right` | Where the magnified view goes. |
| `size` | `0.4` | Magnified view width as a fraction of the panel width (0 < size ≤ 1; `inset_fraction` is accepted too). |
| `color` / `line_color` | `yellow` | Box and leader-line colours. |
| `stroke` | `1.5` | Line width. |
| `connectors` | `2` | Leader lines: 0, 1 or 2. |
| `border` | `2` | Frame of the magnified view. |
| `image` | the panel itself | A different file to magnify (e.g. a higher-resolution acquisition). |

---

## 17. Rotation, flips, channels and display range

```yaml
- - image: stack.tif
    rotate: 12               # degrees
    flip: h                  # h, v, hv (= both)
    channels: [true, false, true]   # hide channel 2
    projection: max
    z_range: [3, 18]         # slices 3..17 in the projection
    display_range: [200, 3500]      # fixed intensity window (raw values)
```

| Key | Values | Meaning |
|---|---|---|
| `rotate` | degrees | Rotation of the image inside its panel. |
| `flip` | `h`, `v`, `hv` / `both` | Mirror left↔right, top↔bottom, or both. |
| `channels` | list of `true`/`false` | Which channels are shown, one entry per channel. |
| `z_range` | `[first, last)` | Slices included in the projection (first included, last excluded, from 0). |
| `display_range` | `[min, max]` | Fixed black / white points in raw intensities — the same window on every panel makes intensities comparable. Recorded in the adjustment ledger. |

All five also work in `defaults`.

---

## 18. More panel kinds — `merge`, `colorbar`, `script`, `equation`

**`merge`** — overlay single-channel files into one colour image:

```yaml
- - merge: [c1_dapi.tif, c2_gfp.tif, c3_rfp.tif]
    colors: [blue, green, magenta]
    label: Merge
```

| Key | Default | Meaning |
|---|---|---|
| `colors` | gray / green+magenta / red+green+blue | One colour per file. |
| `mode` | `sum` | `sum` (classic additive merge) or `max` (no saturation where channels overlap). |
| `normalization` | `per_channel` | `per_channel` stretches each channel to its own range; `none` keeps raw intensities (to compare merges). |
| `label`, `label_placement` | none, `top left` | Panel label. |
| `scale_bar`, `px_to_unit` | | As for images. |

(For each channel **and** the merge side by side, use `split` with a list of
files — §11.)

**`colorbar`** — the calibration bar of a LUT, as its own panel (usually next
to the pseudo-coloured image). The recipe gives it no panel letter of its own.

```yaml
- - {image: ratio.tif, lut: MATPLOTLIB_viridis}
  - {colorbar: MATPLOTLIB_viridis, vmin: 0.2, vmax: 1.8, label: "FRET ratio"}
```

Keys: `vmin` (0), `vmax` (255), `label`, `orientation` (`vertical` /
`horizontal`), `ticks`, `tick_labels`, `panel_label`.

**`script`** — a panel drawn by Python code, e.g. a matplotlib model or a
schematic. The code must set `self.img` to a NumPy image:

```yaml
allow_scripts: true          # required: a script panel runs Python code
rows:
  - - script: |
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(3, 2), dpi=150)
        ax.plot([0, 1, 2], [0, 1, 4])
        fig.canvas.draw()
        self.img = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()
        plt.close(fig)
      label: Model
```

The script is stored in the `.pyf` and re-runs when the figure is opened.
Without `allow_scripts: true` a recipe with a `script:` panel is refused — a
recipe someone sends you should never run code without you saying so.

**`equation`** — LaTeX mathematics typeset as a vector panel (by Matplotlib's
mathtext, a LaTeX maths subset: no TeX installation needed). Without `$…$` the
whole text is a formula; with `$…$`, text outside the dollars is plain text.

```yaml
- - {image: cell.tif}
  - {equation: '\Delta F/F_0 = \frac{F - F_0}{F_0}', font_size: 10, label: Model}
```

Keys: `font_size` (pt, 12), `color` (`black`), `fontset` (`cm` = Computer
Modern, the LaTeX look; `stix`, `stixsans`, `dejavusans`, `dejavuserif`),
`label`, `engine` (`mathtext`, the default, or `latex`), `preamble` (for
`engine: latex`; default `\usepackage{amsmath,amssymb,bm,siunitx}`), `font`
(for `engine: latex`: an installed font such as `Arial` for the text and the
maths letters, digits and Greek, to match the figure; needs XeLaTeX). The
equation is written as an SVG in an `equations` folder next to the figure; like
any panel it is scaled with its row. Quote the formula with single quotes in
YAML so that backslashes are kept. A formula that cannot be typeset is reported
before anything is built.

**Full LaTeX** — `engine: latex` typesets with the computer's LaTeX installation
(TeX Live, MiKTeX or MacTeX, with `dvisvgm`): any environment and any package.
The SVG is saved, so the figure opens on computers without TeX. The value can
also be a `.tex` file (its document body is used):

```yaml
- - {equation: '\begin{aligned} D &= \SI{0.12}{\micro\metre\squared\per\second} \\ \bm{F} &= -\nabla U \end{aligned}', engine: latex}
  - {equation: maxwell.tex, engine: latex, preamble: '\usepackage{physics}'}
  - {equation: '\alpha v = \SI{3}{\micro\metre\per\second}', engine: latex, font: Arial}
```

**Maths in labels** — in any `label`, `annotations` text or text row, `$…$` is
typeset as maths (`\$` is a literal dollar), on screen and in every export: by
LaTeX itself when it is installed (full LaTeX; the formulas are kept in
`equations/labels/` next to the figure, so it looks the same on computers
without TeX), in the label's own font when XeLaTeX is installed, else by
Matplotlib's mathtext in the label's own font. The `pptx` export turns them into
native PowerPoint equations, the `illustrator` export into Unicode text.

**Data plots typeset by LaTeX** — `latex: true` on a `plot:` panel typesets its
axis labels, ticks and title with LaTeX (sans-serif):

```yaml
- - {plot: diffusion.csv, latex: true, ylabel: '$D$ (\si{\micro\metre\squared\per\second})'}
```

**LaTeX documents** — `image: plot.tex` (or `equation: plot.tex`) with a whole
document (`\documentclass…`: a TikZ / pgfplots picture, a figure with
`\includegraphics`, a table) compiles its first figure/table environment (else
its first TikZ picture, else its body; caption left out) with its own preamble,
in its own folder, into a cropped vector PDF panel kept in `latex/` next to the
figure. Needs `pdflatex` (TeX Live, MiKTeX or MacTeX). `page: 2` picks the
second figure/table (or TikZ picture, when the document has no figure or
table environment). The panel remembers its `.tex`: the GUI offers to recompile
it when the `.tex` changed, and the MCP tool `update_latex_panels` does it.

```yaml
- - {image: paper.tex, page: 2}
```

**LaTeX code panels** — `tex:` holds LaTeX code itself: a TikZ / pgfplots
picture, a tabular, maths, or a whole document (`\documentclass…`). A snippet
gets amsmath, amssymb, bm, siunitx, graphicx, booktabs, xcolor, tikz and
pgfplots; `preamble:` adds more. The compiled PDF is kept in
`equations/labels/` next to the figure. Keys: `label`, `preamble`.

```yaml
- - tex: |
      \begin{tikzpicture}
        \begin{axis}[width=6cm, xlabel={$t$ (s)}]
          \addplot[blue, thick, domain=0:5] {exp(-x)};
        \end{axis}
      \end{tikzpicture}
    label: A
```

---

## 19. Row options — columns, spacing, label rows, side labels

Write a row as a mapping to give it options; `panels` holds its panels.

```yaml
rows:
  - panels: [wt.tif, ko.tif, rescue.tif]
    labels: [WT, KO, Rescue]      # one per panel, or one text spanning the row
    labels_position: above        # above (default) / below
    side_label: "Day 1"           # a label at the side of the row
    side_label_position: left     # left (default) / right / top / bottom
  - orientation: Y                # Y = a column (panels stacked), X = a row
    spacing: 8                    # this row's gap, instead of the figure's
    panels: [a.tif, b.tif]
```

| Key | Default | Meaning |
|---|---|---|
| `panels` | **required** | The panels, as in a plain row. |
| `orientation` | `X` | `X` / `row` / `horizontal`, or `Y` / `column` / `vertical`. |
| `spacing` | the figure's `spacing` | Gap inside this row. |
| `labels` | none | Column headers: a list (one per panel) or one text across the row. |
| `labels_position` | `above` | `above` or `below`. |
| `labels_orientation` | `horizontal` | `horizontal`, `vertical`, `vertical_flipped`. |
| `side_label` | none | A label at the side of the row (e.g. a condition name). |
| `side_label_position` | `left` | `left`, `right`, `top`, `bottom`. A label sits at an end of its row: for a column (`orientation: Y`), `left` / `top` put it above and `right` / `bottom` below. Side labels and label rows are dark text (white on a dark `background` / `label_background`). |

---

## 20. Finishing — size, fonts, metadata, alt text, style, exports, checks, templates

```yaml
width_mm: 120               # or width_cm / width_in / width_px (or journal:)
dpi: 300
font: {family: Arial, size: 8}
min_font_pt: 6
tidy_text: true
letter_placement: top left
auto_configure: {lut_preset: fluorescence, scale_bar_width: 10, unit: "µm"}
alt_text: auto
copy_style_from: published/Figure1.pyf
copy_style_aspects: [fonts, letters, scale_bars]
exports: [pdf, png, {format: tif, dpi: 600}, source_data]
```

**Size.** `journal` (+ `column`) or **one** explicit width. `width_px` is a
whole number of pixels; the physical widths use `dpi`.

**`auto_configure`** reads each file's metadata: channel count → LUT preset
(`fluorescence`: 1 ch gray, 2 green+red, 3 blue+green+red…; `rgb`; `gray`;
`none`), and pixel size (ImageJ TIFFs) → a scale bar of `scale_bar_width`
`unit` at `placement`. `true` uses the defaults; `first_image_only: true`
configures one image per row. It runs **before** the per-panel settings, so a
panel's own `lut` / `scale_bar` always wins.

**`copy_style_from`** gives the figure the look of another one (e.g. one the
journal already accepted). `copy_style_aspects` picks among `fonts`, `letters`,
`scale_bars`, `spacing`, `plots` (default: all).

**`exports`** — written next to the `.pyf` (same name) after the build; give
`{format: …, path: …}` to choose the file, `dpi` for resolution.

| Format | File | Notes |
|---|---|---|
| `pdf`, `svg` | `fig.pdf`, `fig.svg` | Vector, fonts embedded. |
| `png`, `tif` (`tiff`), `jpg` (`jpeg`) | `fig.png`, … | Raster at `dpi` (300). |
| `latex` | `fig_latex.pdf` + `.pdf_tex` | Labels typeset by LaTeX; `with_caption: true` wraps it in a figure float. |
| `print` | `fig_print.tif` | Print-ready TIFF, `color_mode: cmyk` (default) or `rgb`. |
| `video` | `fig.mp4` | Animates the time-lapse and video panels; `frame_mode: freeze` / `blank`. H.264 (plays in QuickTime, Safari, PowerPoint, browsers) when PyAV is installed (`pip install av` or `pip install pyfigures[video]` — it bundles ffmpeg, nothing else to install); `path: fig.webm` gives VP9, `.mov` / `.mkv` H.264. |
| `source_data` | `fig_source_data/` | Folder with the panels' source data and a manifest. |
| `review` | `fig_review.html` | Click-to-comment page for co-authors. |
| `caption` | `fig_caption.txt` | The caption as text. |
| `ledger` | `fig_ledger.json` | Every pixel-affecting adjustment per panel (crop, rotation, display range, LUT, projection, scripts) + a Methods paragraph — the disclosure journals ask for. |
| `colorblind` | `fig_colorblind.png` | The figure as a colour-blind reader sees it; `cvd_type: deuteranopia` (default), `protanopia` or `tritanopia`. |
| `pptx` | `fig.pptx` | Editable PowerPoint slide: one group per panel, pictures + native text boxes and shapes (letters, labels, scale bars, ROIs, arrows). |
| `illustrator` (`jsx`) | `fig.jsx` + `fig_assets/` | Adobe Illustrator script that rebuilds the figure with live text and vector paths (File → Scripts → Other Script…). Keep the assets folder next to it. |
| `vectorcraft` | `fig.vectorcraft` | Native document for [VectorCraft](https://github.com/storytold/vectorcraft), the open-source Illustrator replacement (File → Open): one clip group per panel, live text, vector paths, images embedded — one file, nothing beside it. VectorCraft also opens the `svg` and `pdf` exports. |
| `deckcraft` | `fig.deckcraft` | Native deck for [DeckCraft](https://github.com/storytold/deckcraft), the open-source PowerPoint replacement (File → Open): one slide the size of the figure, one group per panel, editable text and shapes. DeckCraft also opens the `pptx` export. |

The build summary lists the files written under `exports`.

### Checks — `checks`

```yaml
journal: nature
checks:
  - integrity                              # duplicated / flipped / cloned panels
  - scale                                  # same displayed µm per pixel everywhere
  - scale_bars                             # every micrograph has a scale bar (a montage / split counts once, plots are not counted)
  - labels                                 # every image panel has a letter or label
  - {check: resolution, min_dpi: 300}      # at the printed size
  - {check: journal, fail: false}          # width, fonts, resolution: report only
```

The checks run after everything else and **before the exports**: if one fails,
the build stops with an error listing what failed (the `.pyf` is still saved,
so you can open it and look), nothing is exported, and the command line exits
with status 1 — so a Makefile / CI run fails loudly. `fail: false` turns a check
into a warning. The build summary's `checks` gives each result.

| Check | Fails when | Options |
|---|---|---|
| `integrity` | two panels are the same image (also flipped, rotated or inverted), or a region is copy-pasted inside a panel, or a panel can't be read. A screening aid: a hit can be legitimate. | `hamming_threshold` (6; lower = stricter), `min_clones` (3) |
| `scale` | panels show the same physical length at different sizes (pixel sizes needed) | `tolerance` (0.05 = 5 %) |
| `scale_bars` | an image panel has no scale bar | — |
| `labels` | an image panel has no letter or text label | — |
| `resolution` | a panel prints below `min_dpi` at the figure's size | `min_dpi` (300) |
| `journal` | the width, smallest font, font family or resolution break the journal's rules (uses the recipe's `journal` / width, `dpi`, `min_font_pt`) | `min_font_pt` (7), `min_dpi` (300), `require_sans_serif` (true) |

`resolution` and `journal` need the printed size: a `journal`, or `width_mm` /
`width_cm` / `width_in`.

### Self-contained copy — `consolidate`

`consolidate: true` copies every image the figure uses into `fig.files/` next to
`fig.pyf` and links the figure to those copies, so the folder can be zipped,
shared or archived. `consolidate: share/fig.pyf` writes the self-contained copy
there instead and leaves `output` linked to the originals. It runs last (after
the exports). Same as File → Save And Consolidate.

Remote images (web links, OME-Zarr on a server, OMERO links) stay links unless
`download_remote: true`: then an OMERO image or remote OME-Zarr is saved as a
local OME-Zarr of exactly what the panel shows (raw pixels with omero-py,
channel colours, windows, pixel size) and any other link as the file itself.
Private OMERO images need `OMERO_USERNAME` / `OMERO_PASSWORD`. An image that
cannot be downloaded stays a link and is listed in the build's warnings.

```yaml
consolidate: true
download_remote: true
```

### Templates — `template` + `fill`

```yaml
output: Figure2.pyf
template: templates/two_by_three.pyf       # a .pyf with empty template slots
fill: [wt_1.tif, wt_2.tif, "ko_*.tif"]      # files or globs, in slot order
exports: [pdf]
```

A template is a figure whose panels are empty slots (File → Convert figure
to template in the GUI). The slots are filled in reading order and keep their
size, crop, LUT, scale bar and labels. `template` replaces `rows` / `panels`;
everything in this section (size, fonts, caption, checks, exports…) still
applies. Letters are not added again (the template has its own) unless you set
`letter_panels: true`. More files than slots is an error; fewer leaves the rest
empty with a warning.

---

## 21. Scale bars and crops

### Scale bars

```yaml
scale_bar: {units: 10, unit: "µm", color: white, placement: bottom right, label: "10 µm"}
px_to_unit: 0.1
```

| Key | Values (default) | Meaning |
|---|---|---|
| `units` | number — **required** | Bar length in physical units. |
| `unit` | `µm` | Unit written in the auto label (`nm`, `mm`, `px`…). |
| `color` | `white` | Colour of the bar **and** its label. |
| `placement` | `bottom right` | `bottom right`, `bottom left`, `top right`, `top left`. |
| `label` | `"<units> <unit>"` | Custom text (`""` = bar only — then state the size in the caption). |
| `px_to_unit` | | The pixel size may also be given here; it is the panel's `px_to_unit`. |

The bar's length on screen is `units ÷ px_to_unit` pixels of the raw image, so
give **`px_to_unit`** (the pixel size, in the same unit) — usually once, in
`defaults`. Montage, split, kymograph and orthogonal panels read the pixel size
from the file automatically (a `px_to_unit` you give overrides it). A
`scale_bar` on a montage or split — set on the panel or in `defaults` — is drawn
once, on the last panel (for a split, the merge: all panels share one scale);
`scale_bar_panels: all` puts one on every panel — use it only when asked for a
bar on each panel. A `crop` on a montage, split or merge applies to every panel
it makes — e.g. `{split: hela.png, names: [Lamp1, Mito, DNA], crop: {bottom: 24}}`
removes text burned into the image's bottom rows from all channels and the merge.

A common convention: scale bar on one panel per row, same length everywhere,
and "Scale bars, 10 µm." in the caption.

### Crops

```yaml
crop: {left: 20, right: 20, top: 5, bottom: 0}
```

Pixels removed from each edge of the **raw** image, before display. Integers,
≥ 0; give only the sides you need. Cropping doesn't touch the file on disk and
is recorded in the adjustment ledger.

Coordinates for `arrows`, `kymograph` and `orthogonal` are always in the
**uncropped** raw image.

---

## 22. Labels, letters and backgrounds

**Letters.** With `letter_panels: true` (default) each panel gets A, B, C… in
its top-left corner, in reading order. A montage or channel split counts as one
panel (one letter on its first frame). Letters are white on images and black on
charts.

**Labels share the corner.** A panel `label` also goes top-left; PyFigures
stacks everything in the same corner, so it sits **under** the letter rather
than on top of it:

```
A
WT
```

Stamps and channel names default to the top-right corner.

**Label background** — a filled box behind every label, so text reads on any
image (bright spots, white cells…):

```yaml
label_background: black      # boxes behind letters, labels, stamps, channel names
```

Any colour works (`black`, `"#202020"`, `white` with dark text…). Charts are
left alone (their labels already sit on white); scale-bar legends are not
boxed.

**Figure background** — the colour behind all panels, i.e. of every gap
between them and between rows:

```yaml
background: white
```

| `background` | PNG / TIFF | JPG | SVG / PDF |
|---|---|---|---|
| *(omitted)* / `none` | gaps **transparent** | white | transparent |
| `white` | white | white | white |
| `black` | black | black | black |

Transparent is fine on a white journal page, but some viewers and slide
programs show transparency as black or as a checkerboard — set `white` to be
safe, or `black` for dark, image-heavy figures (videos, fluorescence).

---

## 23. Reference tables

### LUTs (colour look-up tables)

Case-insensitive.

- **Basic:** `GRAY`, `RED`, `GREEN`, `BLUE`, `CYAN`, `MAGENTA`, `YELLOW`,
  `ORANGE`, `PURPLE`, `DEFAULT`.
- **Fiji-style:** `AFM_HOT`, `RED_HOT`, `GREEN_HOT`, `BLUE_HOT`, `OCEAN`,
  `HI_LO`, `DNA`, `RAINBOW_1`, `RAINBOW_2`, `RAINBOW_3`, `RAINBOW_LIGHT`,
  `BLUE_WHITE_RED`, `GREEN_FIRE_BLUE`, …
- **Matplotlib:** `MATPLOTLIB_<name>` for any matplotlib colour map —
  `MATPLOTLIB_viridis`, `MATPLOTLIB_magma`, `MATPLOTLIB_inferno`,
  `MATPLOTLIB_plasma`, `MATPLOTLIB_coolwarm`, … Add `_r` for reversed
  (`MATPLOTLIB_magma_r`).

Colour-blind-safe pairs: green + magenta, or gray single channels with a merge.

### Colours

Wherever a colour is asked (`color`, `stamp_color`, `line_color`,
`crosshair_color`, `background`, `label_background`):

- names: `white`, `black`, `red`, `green`, `blue`, `yellow`, `cyan`, `magenta`,
  `gray`/`grey`, `orange`, `pink`, `purple`, `lime`;
- hex: `"#ff8000"`, `"#f80"` (quote them — `#` starts a YAML comment);
- a number: `16777215` (= white).

`split` / `orthogonal` channel `colors` accept the channel colours only: `gray`,
`red`, `green`, `blue`, `cyan`, `magenta`, `yellow`.

### Corners (placements)

`top left`, `top right`, `bottom left`, `bottom right`.

### Journals

`journal:` name (case-insensitive) and the resulting width in mm:

Only the sizes each journal's own page states (pages read in October 2026); a
journal offers just those columns (`—` = not given by the journal):

| Journal | single | 1.5 | double | triple | Also accepted | The page says |
|---|---|---|---|---|---|---|
| `nature` | 89 | 136 | 183 | — | | 89 / 183 mm; column-and-a-half 120–136 mm |
| `nature communications` | 88 | — | 180 | — | ncomms | 88 / 180 mm |
| `nature methods` | — | — | 180 | — | nature cell biology, nature medicine | maximum width 180 mm |
| `science` | 57 | — | 121 | 184 | | 1 / 2 / 3 columns: 5.7 / 12.1 / 18.4 cm |
| `cell` | 85 | 114 | 174 | — | cell reports, current biology, developmental cell | 8.5 / 11.4 / 17.4 cm (two-column formats) |
| `plos` | 132 | — | 190.5 | — | plos biology, plos genetics, plos one | text column 132 mm, full page 190.5 mm |
| `embo` | 87 | — | 180 | — | the embo journal | between 87 and 180 mm |
| `jcb` | 85 | — | 175 | — | journal of cell biology | 85 mm; maximum 175 mm |
| `pnas` | 87 | 114 | 178 | — | | 8.7 / 11.4 / 17.8 cm |

`column:` also accepts `1 column`, `2 columns`, `3 columns` and `full width`
(the widest the journal has). For a journal whose page gives only a full width
(Nature Methods, Medicine, Cell Biology: 180 mm), `column: half page` gives an
**estimated** half page, (full − 5 mm) / 2 = 87.5 mm: the result, the reports and
the GUI picker say it is an estimate, not the journal's rule. Journals with their
own column sizes refuse `half page` and list them. `journal_info` (MCP) or
`python -m pyfigures.journal_styles info <journal>` tells whether a journal is
available and its sizes. Elsevier, Springer, Wiley (publisher-wide) and eLife
(its page gives upload minimums, not column widths) have no preset: import the
journal's page (below).

Always check the journal's current author guidelines. After building, the MCP
tools `check_journal_compliance`, `check_resolution` and
`enforce_min_font_size` (or the GUI's QC menu) verify fonts and DPI.

**Other journals: import their guidelines.** Paste the figure-guidelines text
of a journal's page into **QC → Journal styles…** (or give it to the MCP server:
`prepare_journal_style_import` then `save_journal_style`); a model extracts the
rules, each quoting the text, and you review them. The saved style is then a
journal name like the built-ins: `journal: Journal of Fly Figures` (or
`journal: "custom:PNAS"` when the title is also a built-in), with
`column: single | 1.5 | double` or one of the style's own width labels
(`column: 3 columns`). See `python -m pyfigures.journal_styles --help`.

---

## 24. Errors and validation

The whole recipe is checked **before anything is built**. Every problem names
where it is:

```text
ERROR in fig1.yaml: row 2, panel 1: unknown key(s) for a image panel: ['lutt']
  (allowed: ['arrows', 'crop', 'kymograph', 'label', 'lut', ...])
ERROR in fig1.yaml: row 1, panel 3: file not found: C:\data\ko_actin.tif
ERROR in fig1.yaml: row 3, panel 1: glob 'reps/rep*.tif' matched no files
ERROR in fig1.yaml: row 1, panel 1: arrow 1 'at' must be a list of 2 numbers (image pixels)
```

Checked up front: unknown keys (typos), missing files (images, insets, zoom
images, merge channels, `copy_style_from`), empty globs, `crop` values, the shape
of `scale_bar`, `arrows`, `kymograph`, `orthogonal`, `rois`, `brackets`,
`inset`, `zoom`, `text`, `corner_labels`, `rotate` / `flip` / `channels` /
`z_range` / `display_range`, row options (and one label per panel), colours,
one width only, export formats, `script` panels without `allow_scripts: true`,
`rows` vs `panels`, the `.pyf` extension, check names and options (and a print
size for `resolution` / `journal`), `consolidate`, the `template` file and the
`fill` files, `properties` names and values.

`checks` that fail stop the build after it is saved and before the exports
(§20); the error lists every failed check.

Checked while building (still stops with a clear error): values a tool
refuses — a stack without a time axis for `montage: …, axis: t`, a single-channel
image in `split`, an arrow tip outside the image, a kymograph on a non-time
series, orthogonal views without voxel depth or `z_scale`, an unknown journal.

Non-fatal problems (e.g. "the arrow would be mostly head at this size") are
listed under `warnings` in the build summary.

---

## 25. Cookbook

### Two conditions, replicates and quantification

```yaml
output: figures/Figure2.pyf
journal: cell
column: double
background: white
defaults:
  lut: gray
  px_to_unit: 0.108
  scale_bar: {units: 10, unit: "µm"}
rows:
  - - {image: data/wt.tif, label: WT}
    - {image: data/ko.tif, label: KO}
  - - {glob: "data/wt_rep*.tif"}
  - - {glob: "data/ko_rep*.tif"}
  - - {plot: data/area.csv, kind: violin, ylabel: "cell area (µm²)"}
    - {plot: data/counts.csv, kind: bar, error: sd, ylabel: "cells / field"}
caption: >
  (A–B) … (C–D) Replicates. (E) Cell area; (F) cells per field.
  Scale bars, 10 µm.
```

### Time-lapse figure

```yaml
output: timelapse.pyf
journal: nature
column: double
label_background: black
rows:
  - - montage: movies/embryo.tif
      axis: t
      frames: "0:60:10"
      interval: 30
      unit: s
      time_zero: 20              # drug added at frame 20
  - - image: movies/embryo.tif
      projection: max
      arrows: [{at: [240, 310], from: nw, label: "cleavage furrow"}]
      kymograph: {line: [180, 310, 300, 310], width: 5, cmap: magma}
```

### Immunostaining channel row + orthogonal view

```yaml
output: staining.pyf
journal: elife
column: double
rows:
  - - split: confocal/cells.czi
      names: [DAPI, Tubulin, Actin]
      colors: [blue, green, magenta]
  - - image: confocal/cells.czi
      projection: max
      lut: [blue, green, magenta]
      orthogonal: {at: [512, 400], z: 18}
```

### Separate channel files

```yaml
rows:
  - - split: [c1_dapi.tif, c2_gfp.tif, c3_rfp.tif]
      names: [DAPI, GFP, RFP]
      colors: [blue, green, red]
      gray: false                 # tinted panels instead of gray
```

### Several figures from one command

```bash
python -m pyfigures.recipe build fig1.yaml fig2.yaml supp1.yaml --render pdf
```

### Regenerate a figure after new data

Change nothing — rebuild. Plots and their statistics are recomputed from the
CSVs; images are re-read. Keep hand-made GUI tweaks in a copy of the `.pyf`, or
fold them back into the recipe (most have a recipe key).

---

## 26. Same features in the GUI and the MCP server

Everything a recipe does can also be done in the GUI and through the MCP
server, and edited afterwards in either.

| Recipe | GUI | MCP tool |
|---|---|---|
| building the recipe | File → Build figure from recipe… | `build_figure_from_recipe` |
| `journal` / `column` | QC → Apply journal guidelines…; size box in the toolbar | `resize_figure`, `apply_journal_guidelines` |
| `spacing` | "Y Spacing" in the toolbar; right-click a group → Change space between elements | `set_spacing`, `set_figure_properties(default_spacing=)` |
| `background` | "Background" button in the toolbar | `set_figure_properties(page_background=)` |
| `label_background` | right-click → Text & lettering ▶ → Change background (non-Letter text); Annotations → Panel letters (A, B, C…) for the letters | `set_label_background`, `style_annotation(background=)` |
| `letter_panels` | "Auto Lettering" in the toolbar | `add_corner_labels` |
| `caption`, `title` | File → Figure caption / legend… | `set_figure_caption` |
| `lut` | right-click → Appearance ▶ → Set LUT(s); Edit Image | `set_lut` |
| `projection` | Edit Image (double-click the panel) | `configure_image` |
| `crop` | Edit Image | `transform_image` |
| `scale_bar`, `px_to_unit` | Annotations → Add scale bar to all panels…; Edit Image | `set_scale_bar`, `set_scale_bar_all` |
| `label` | Edit Image (text tool) | `add_annotation`, `set_annotation_text` |
| `plot` | Insert → Data plot from CSV… | `add_data_plot` |
| `montage` | Insert → Stack views → Montage of frames (time / Z)… | `add_stack_montage` |
| `split` | Insert → Stack views → Channel split (each channel + merge)… | `add_channel_split` |
| `arrows` | Annotations → Add arrow pointing at a feature… | `add_arrow` |
| `kymograph` | Insert → Stack views → Kymograph along a line… | `add_kymograph` |
| `orthogonal` | Insert → Stack views → Orthogonal views (XZ / YZ)… | `add_orthogonal_views` |

| `text`, `corner_labels` | Edit Image → text tool; right-click → Add labels ▶ | `add_annotation`, `add_corner_labels` |
| `rois` | Edit Image → Annotations tab (rectangle, ellipse, line, arrow, polygon…) | `add_roi_rect`, `add_roi_ellipse`, `add_roi_line`, `add_roi_polygon` |
| `brackets` | Edit Image → Signif. bracket | `add_significance_bracket` |
| `inset` | Edit Image → Rect ROI → Inset | `add_inset` |
| `zoom` | Annotations → Add zoom callout to selected panel… | `add_zoom_callout` |
| `rotate`, `flip` | Edit Image → Rotate + Crop | `transform_image` |
| `channels`, `z_range`, `display_range` | Edit Image → File Infos + Scale | `configure_image` |
| `merge` | Insert → Multi-channel merge… | `add_channel_merge` |
| `colorbar` | Insert → LUT colour bar… | `add_lut_calibration_bar` |
| `script` | Edit Image → Script tab (on an empty image) | `add_scripted_image`, `set_script` |
| `equation` | Insert → Add equation (LaTeX)…; right-click → Edit equation… | `add_equation` |
| `tex` | Insert → Add LaTeX code panel…; right-click → Edit LaTeX code… | `add_latex_code` |
| row `orientation`, `spacing` | drop → To column; right-click → Change space between elements | `add_group`, `set_orientation`, `set_spacing` |
| row `labels`, `side_label` | right-click → Add labels ▶ | `add_label_row`, `add_side_label` |
| `width_*`, `dpi` | Figure width box in the toolbar | `resize_figure` |
| `font`, `letter_placement` | Annotations → Panel letters (A, B, C…) | `set_figure_properties`, `style_annotation` |
| `min_font_pt`, `tidy_text` | QC → Enforce minimum font size…; Annotations → Tidy text typography… | `enforce_min_font_size`, `tidy_text` |
| `auto_configure` | — | `auto_configure_images` |
| `alt_text` | File → Alt text (accessibility)… | `generate_alt_text`, `set_alt_text` |
| `copy_style_from` | File → Copy style from another figure… | `copy_style` |
| `exports` | File → Export As ▶, File → Review comments → Export for review…, QC → Adjustment provenance ledger (Methods)…, QC → Preview figure under colour-blindness… | `export_figure`, `export_latex`, `export_print_ready`, `export_video`, `export_source_data`, `export_review`, `export_caption`, `export_adjustment_ledger`, `simulate_color_blindness`, `export_pptx`, `export_illustrator_script`, `export_vectorcraft`, `export_deckcraft` |
| `checks` | QC → Check image integrity…, Check scale-bar consistency…, Audit figure (missing scale bars / labels), Check print resolution…, Check journal compliance…, Pre-submission review (all checks)… | `check_image_integrity`, `check_scale_consistency`, `audit_figure`, `check_resolution`, `check_journal_compliance` |
| `consolidate` | File → Save And Consolidate... | `consolidate_figure` |
| `template`, `fill` | File → Convert figure to template; drop images on the slots | `templatify_figure`, `fill_template`, `batch_fill_templates` |
| `properties` | Edit Image | `set_image_property` |

Not in recipes — use the GUI or MCP on the built figure: freehand drawings,
per-label fonts and manual panel positions.

---

## 27. Tips and gotchas

- **A panel alone in a row becomes as wide as the whole figure.** Pair a plot
  with images or another plot, or give it a row only if you want it big.
- **Z stacks without `projection:` show the first slice**, not the projection.
- **Frame and channel numbers start at 0**, pixel coordinates at the top-left
  corner (0, 0).
- **`column: 1.5`** works unquoted.
- **Quote hex colours** (`"#202020"`) — an unquoted `#` starts a comment.
- **YAML block keys must line up** under the kind key:

  ```text
  - - image: a.tif
      lut: red          # ✓ aligned with "image"
  - - image: a.tif
    lut: red            # ✗ YAML error: "expected <block end>, but found '?'"
  ```
- **Rebuilding overwrites `output`.** If you polish the figure by hand in the
  GUI, save it under another name (or put the change in the recipe).
- **Each save records the source files** (`<figure>.sources.json`); if an image
  changes on disk later, the GUI warns when you open the figure, and
  *QC → Check for changed source files* lists what changed.
- **See the result without the GUI:** `--render png`, or the MCP
  `render_preview`.
- A worked example with every key: [`recipe_example.yaml`](recipe_example.yaml).
