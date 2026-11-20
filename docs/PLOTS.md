# Plots and tables in PyFigures

Measurements belong in the same figure as the images. PyFigures draws **data plots with
their statistics**, **seaborn plots** and **table panels** from your tables, and keeps them
**live**: edit the table, reopen the figure, and the plot and its tests follow.

Everything here can be done three ways, with the same options:

| | Where |
|---|---|
| **GUI** | Insert → *Data plot from a table…*, *Seaborn plot from a table…*, *Table panel…*; right-click a plot → *Plot settings…*, *Show plot code…*; right-click a table → *Table settings…* |
| **Chat** (Tools → Chat sidebar) | say it in words: "make it half violins", "one plot per day", "compare everything to WT" |
| **MCP / recipes** | `add_data_plot` / `edit_data_plot`, `add_seaborn_plot` / `edit_seaborn_plot`, `add_table_panel` / `edit_table_panel`; `plot:`, `seaborn:`, `table:` panels in a recipe ([RECIPES.md](RECIPES.md)) |

Help → *▶ Plots & Tables Tutorial* walks through it with sample tables.

---

## 1. Tables

A table can be:

- **CSV / TSV / TXT**: separator and decimal comma found by themselves (French or German
  Excel exports read as such);
- **Excel** (`.xlsx`, `.xlsm`, old `.xls`): pick the sheet (`sheet="growth"`, or its number from 1);
- **SQLite** database, whatever its name (recognised by its header): a table, a view, or an
  SQL query (`sheet="SELECT genotype, area FROM cells WHERE day = 3"`).

What is cleaned up for you, and said in the reply:

- **lines above the table** (an instrument's header, a title, notes in a sheet) are found and
  skipped; `skip_rows=3` skips a given number, `skip_rows=0` none;
- a **row of units** under the header goes into the column names: `area` + `µm²` →
  `area (µm²)`, which then labels the axis;
- blank margin rows / columns, numbers typed as text, empty / NA / typo cells (left out group
  by group, never filled in).

**Tidy tables** (one row per measurement: genotype, sex, day, area…) need no reshaping:

- `columns=["genotype", "area"]`: the group column and the value column;
- `columns=["genotype", "sex", "area"]`: x, the split / colour factor, the value (split
  violins, grouped bars, time courses);
- `where="day == 14"`: only those rows (a pandas query on any column:
  `"sex == 'male' and area > 100"`; backquotes around names with spaces).

**Looking at a table** (chat / MCP, read-only):

| Tool | Gives |
|---|---|
| `describe_table` | sheets or tables, each column's type, missing cells, range or levels, the first rows, the plots that fit |
| `list_factor_columns` | the columns that can split, colour or facet the data (text, or numbers with a few repeated values), with their levels |
| `summarize_table` | n, mean, SD, SEM, median, min, max per group, with a row filter; `out_path` saves it as CSV / Excel |

---

## 2. Data plots (with statistics)

| `kind` | What it shows | Test |
|---|---|---|
| `auto` (default) | the plot that shows the data best: grouped for two factors, scatter for an x / y series, else bars (under 5 points per group), box (5-19), violin (20+) | as below |
| `bar`, `box`, `violin` | groups side by side | 2 groups: Welch t / Mann-Whitney; more: ANOVA + Tukey / Kruskal + Dunn (chosen by a normality check, or `stats_mode`) |
| `split_violin` | two conditions (e.g. female / male) as the two halves of each violin, a legend naming them | each pair of halves tested (stars); two-way ANOVA recorded |
| `paired` | repeated measures (one row per subject): a line per subject, the mean ± SD beside | paired t / Wilcoxon; RM-ANOVA / Friedman + paired post-hoc |
| `line` | a time course / dose response: mean ± error of each group across x (spaced as numbers when they read as numbers) | the groups compared at each x (a star over it); two-way ANOVA recorded |
| `grouped` | bars by two factors | the colour groups compared within each x level (brackets with stars; Tukey / Dunn within the level); two-way ANOVA recorded |
| `scatter` | y against x, a regression line | Pearson correlation |

### Options (all optional; `edit_data_plot` changes any of them later)

**Violins and points**

- `violin_side="left"` / `"right"`: half violins, the points on the open side (a raincloud);
- `violin_inner="box"` (a mini box plot) / `"lines"` / `"none"`;
- `show_points=False`; `point_style="swarm"` (side by side, never overlapping) / `"line"` / `"jitter"`;
- `show_mean=True`: a mean marker on box / violin plots.

**Statistics**

- `control="WT"`: every group compared with WT only (Dunnett's test after a one-way ANOVA,
  or Mann-Whitney against it with Bonferroni);
- `pairs=[["WT", "mutA"]]`: brackets only for these pairs (the p-values stay those of the
  whole test);
- `only_significant` (default: brackets for p < 0.05 only), `stats_mode="parametric"` /
  `"nonparametric"`, `annotate_stats=False` (no test);
- `p_format="p"`: the p-values written on the brackets instead of stars;
- `stats_text=True` (two-factor plots): the two-way ANOVA also written under the axes. Off by
  default: a figure shows stars, the ANOVA belongs in the legend text (it is in the stats
  record and in *Show plot code…*);
- `show_n=True`: the n of each group under its name;
- `normalize="WT"`: every value as a % of WT's mean ("% of WT" on the y axis; the tests are
  unchanged by the scaling);
- `error="sd"` (default, as journals prefer) / `"sem"` / `"ci95"` / `"none"`.

**Facets**

- `facet="day"`: one plot per day side by side, each with its own test, one y axis;
- `facet_row="sex"`: a grid; `facet_ncols`: facets per row; the `title` goes over all of them.

**Labels, colours, layout**

- the axis labels come from the table when none is given (the value column on y, the factor
  on x and as the legend title); `ylabel=""` removes one, `"auto"` brings it back;
- `rename={"mutA": "mutant A"}`: the names shown (the table is unchanged);
- `colors=["#000000", ...]` in the groups' order, or by name `{"WT": "black", "mutA": "#d55e00"}`;
- `element_colors={"points": "black", "median": "red", "edges": "none", "brackets": "grey"}`:
  parts of the plot (also `error_bars`, `whiskers`, `outliers`, `inner`, `fit`, `mean`,
  `reference`, `axes`, `background`);
- `hlines=[1.0]` or `[{"y": 100, "label": "control"}]`: reference lines;
- `order=[...]`, `ylim=[0, null]`, `log_y`, `xtick_rotation=45`, `legend="outside"`;
- `aspect`, `width`, `height`; `font_scale=1.3` (every text 30 % bigger; the plot's text is
  7 pt on the printed page by default).
- Text: `font_pt` / `font_family` set the whole plot's text; `text_pt={"title": 9}` and
  `text_font={"ticks": "Arial"}` give one part its own size on the page or font. The parts
  are `title`, `axis_labels`, `ticks` (tick labels: group names, numbers) and `legend`; a part
  set to `null` follows the whole plot again. In the panel editor: the publication style tab,
  *Parts of the text*.

Colours are colour-blind safe by default (the Wong palette), and every series also gets its
own marker shape.

---

## 3. The statistics, in the legend and as code

A figure shows **stars**; the tests themselves go in the legend. File → *Figure caption / legend…* →
**Insert statistics** (chat / MCP: `add_statistics_to_caption`; `caption_statistics` only reads it)
adds a paragraph such as:

> Statistics: (g) n = 10 per group; one-way ANOVA followed by Tukey's HSD test (F = 23.3, p < 0.0001).
> (h) mean ± SD; two-way ANOVA (genotype p < 0.0001; treatment p < 0.0001; genotype × treatment
> p = 0.02); stars: the genotype groups compared within each treatment level (one-way ANOVA followed
> by Tukey's HSD test). \*p < 0.05, \*\*p < 0.01, \*\*\*p < 0.001, \*\*\*\*p < 0.0001.

Edit it as you like: PyFigures remembers what it inserted, updates it when the data change only while
you have not touched it, and otherwise just tells you (in `get_figure_caption`) that the plots'
statistics changed.


Right-click a plot → **Show plot code…** (chat / MCP: `data_plot_code`) gives a script with
two parts:

1. it redraws the plot with staplot;
2. it reads the table **with pandas exactly as the plot did** (separator, decimal comma,
   sheet or SQL query, lines skipped, columns and rows kept) and reruns **every test with
   scipy / statsmodels alone**: the t-test, ANOVA + Tukey, Kruskal + Dunn's z (written out),
   Dunnett, paired tests, two-way ANOVA (`anova_lm`), each facet separately.

Copy it or save it as a `.py` file, for a reviewer or the supplementary material. A seaborn
plot gives its seaborn code; a table panel the pandas code of its rows or summary. The tests
and p-values are also recorded beside the figure for the Methods section (QC → *Adjustment
provenance ledger*).

---

## 4. Seaborn plots

Any seaborn function (`catplot`, `relplot`, `displot`, `lmplot`, `histplot`, `ecdfplot`,
`violinplot`, `heatmap`…) with **facets like ggplot2** (`col=`, `row=`, `col_wrap=`). No
statistics brackets: use data plots for tested comparisons.

Common requests:

- split violins: `function="violinplot"` (or `catplot`, `kind="violin"`), `hue="sex"`,
  `options={"split": true}`;
- a cumulative histogram: `function="histplot"`, `options={"cumulative": true, "element":
  "step", "fill": false}`, or `function="ecdfplot"`;
- a colour per group: `palette={"female": "#d55e00", "male": "#0072b2"}`;
- `legend="outside"` / `"top"` / `"inside"` / `"none"`; `xlim` / `ylim`; `title`;
- `rename={"weight_g": "weight (g)", "mutA": "mutant A"}` for column or value names;
- `where="day == 14"`, `skip_rows`, `sheet` as for data plots.

---

## 5. Table panels

Insert → **Table panel…** (`add_table_panel`, a `table:` recipe panel) draws a table in the
figure, booktabs style, in the same 7 pt as the plots:

- the raw rows: `columns`, `where`, `max_rows` (the rest is said under the table);
- or a summary per group: `by=["genotype", "sex"]`, `value="area"`, `stats=["n",
  "mean±sd", "median [iqr]"]` (also `mean`, `sd`, `sem`, `median`, `min`, `max`,
  `mean±sem`), `decimals`.

Right-click it → **Table settings…** (`edit_table_panel`) to change it.

---

## 6. Asking the chat

Say what you want; the chat knows these options. For example:

- "make it half violins", "put a box plot inside the violins", "remove the point cloud"
- "split by sex", "one plot per day", "only day 14"
- "compare everything to WT", "only show WT vs mutA", "show the p values, not stars", "add the n"
- "normalise to control", "make the medians red", "colour WT in black"
- "what columns does this table have?", "which columns can I facet by?",
  "mean area per genotype and sex?"
- "add a table of mean ± SD per genotype", "show me the code of this plot"

---

## 7. Sample files

`demo_figures/plots_playground/make_samples.py` writes test tables (wide and tidy CSVs, a
French Excel export, Excel workbooks with a title above the table, an SQLite database with
tables and a view, a plate-reader export, a before / after table) and recipes `01`-`09`
that use every feature above.
