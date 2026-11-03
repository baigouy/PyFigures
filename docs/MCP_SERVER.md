# PyFigures MCP Server

The PyFigures **Model Context Protocol (MCP) server** lets any MCP client (Claude, LM Studio…)
read and edit `.pyf` figure files through natural language — no GUI required.

> **What is MCP?**  
> MCP is an open standard (by Anthropic) that allows AI assistants to call tools
> provided by external servers. Think of it as a plugin system: the server exposes
> named functions; the AI decides which ones to call and with which arguments.

---

## Table of Contents

0. [Starting, stopping and registering the server](#starting-stopping-and-registering-the-server)
1. [Quick start — Claude Code (Claude AI)](#1-quick-start--claude-code-claude-ai)
2. [Quick start — Claude Desktop (Claude AI)](#2-quick-start--claude-desktop-claude-ai)
3. [Quick start — LM Studio (local models)](#3-quick-start--lm-studio-local-models)
4. [Quick start — any OpenAI-compatible client](#4-quick-start--any-openai-compatible-client)
5. [Available tools reference](#5-available-tools-reference)
6. [Example prompts](#6-example-prompts)
7. [Troubleshooting](#7-troubleshooting)

---

## Starting, stopping and registering the server

You do not start the server yourself for most clients: once **registered**, the
client (Claude Code, Claude Desktop, LM Studio, Codex, AnythingLLM, Cursor,
Gemini CLI…) starts `python -m pyfigures.mcp_server` when it needs the tools and
stops it when it quits. Nothing runs in between and nothing needs to start at
login. The processes the server starts (renderers, LaTeX, ffmpeg) end with it —
on Windows, macOS and Linux; all of this works the same on the three systems
(client configuration files are looked for in each system's own places).

Register or remove it in one click: **GUI → Tools → MCP server…**, or

```bash
python -m pyfigures.mcp_control status
python -m pyfigures.mcp_control register lm_studio   # claude_code, claude_desktop, codex, anythingllm, cursor, gemini_cli
python -m pyfigures.mcp_control unregister lm_studio
```

The client's configuration file is edited in place (every other entry, and in
Codex's TOML the comments, are kept; the previous file goes to
`~/.pyfigures/backups`); restart the client afterwards. Claude Code and the Code
side of Claude Desktop share `~/.claude.json`. A server switched off in the
client or with MCP Commander shows as "switched off".

Other clients: the dialog's buttons (or `snippet --format json|codex|hermes|url`)
copy the `mcpServers` JSON most clients read, the YAML of Hermes Agent
(`~/.hermes/config.yaml`; in WSL the Windows Python is started through
`/mnt/c/…`).

**HTTP server** — for clients that connect to a URL instead of starting a
program: **Start the HTTP server** in the same dialog. While it runs, the dialog
lists what to paste into each kind of client, each with a Copy button: the
address, the `claude mcp add --transport http …` command, the `mcpServers` JSON
with a `url` (Cursor, LM Studio…), AnythingLLM's and Gemini CLI's JSON, Codex's
TOML, Hermes Agent's YAML, and an `npx mcp-remote` bridge for clients that only
start programs. It can also be started when PyFigures opens (off by default; it
then stops when PyFigures closes). Nothing is started at login. From the
command line:

```bash
python -m pyfigures.mcp_control start --port 8765   # http://127.0.0.1:8765/mcp, then what to paste
python -m pyfigures.mcp_control snippet --format http
python -m pyfigures.mcp_control stop                # stops it and every process it started
```

It listens on this computer only. ChatGPT on the web or in its desktop app only
connects to servers on the public internet; use Codex (registered as above) for
OpenAI models on this computer. The MCP tool `mcp_server_info` reports this set-up
(read-only).

## 1. Quick start — Claude Code (Claude AI)

**Claude Code** is Anthropic's CLI coding assistant. This is the primary and most
capable integration.

### Install the server

```bash
pip install pyfigures          # if not already installed
pip install "mcp[cli]"         # MCP SDK for Python
```

### Register with Claude Code

Use **Tools → MCP server…** in the GUI, `python -m pyfigures.mcp_control register
claude_code`, or `claude mcp add --scope user pyfigures -- python -m
pyfigures.mcp_server`. By hand, the entry goes under `mcpServers` in
`~/.claude.json` (user scope) or in a project's `.mcp.json`:

```json
{
  "mcpServers": {
    "pyfigures": {
      "command": "python",
      "args": ["-m", "pyfigures.mcp_server"]
    }
  }
}
```

> **Windows / Conda users** — if `python` resolves to the wrong interpreter,
> use the full path:
> ```json
> {
>   "mcpServers": {
>     "pyfigures": {
>       "command": "C:\\Users\\<you>\\AppData\\Local\\miniconda3\\envs\\mon_prog\\python.exe",
>       "args": ["-m", "pyfigures.mcp_server"]
>     }
>   }
> }
> ```

### Verify

```bash
claude mcp list
# pyfigures  stdio  python -m pyfigures.mcp_server
```

### Use it

Start Claude Code in your project folder and try:

```
Add a 10 µm scale bar to all images in figure.pyf
```

```
Describe the layout of figure.pyf and add "WT" / "KO" column headers above the first row
```

---

## 2. Quick start — Claude Desktop (Claude AI)

[Claude Desktop](https://claude.ai/download) supports MCP servers via its config file.

### Edit the config

Open (or create) the file:

| OS      | Path |
|---------|------|
| macOS   | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

Add the server:

```json
{
  "mcpServers": {
    "pyfigures": {
      "command": "python",
      "args": ["-m", "pyfigures.mcp_server"]
    }
  }
}
```

Restart Claude Desktop. A hammer icon (🔨) will appear in the chat interface
when tools are available.

---

## 3. Quick start — LM Studio (local models)

[LM Studio](https://lmstudio.ai) **0.3.6+** supports MCP servers in its built-in
chat UI.

### Step 1 — install pyfigures into your Python environment

LM Studio launches the MCP server as a subprocess using your system Python (or
whichever interpreter you specify). That interpreter must have `pyfigures`
installed, otherwise the server crashes immediately with **"Plugin process exited
with code 1"**.

Install with `--no-deps` (the GUI dependencies are not needed by the server):

```bash
# activate the environment you will point LM Studio at, then:
pip install --no-deps pyfigures
pip install "mcp[cli]"
```

> **Conda users** — always use the full path to your environment's Python (see
> Step 2 below) so LM Studio cannot accidentally pick up a different interpreter.

You can verify the server starts correctly by running it manually:

```bash
python -m pyfigures.mcp_server
# should hang silently, waiting for MCP messages — Ctrl+C to stop
```

If you see `ModuleNotFoundError: No module named 'pyfigures'`, the wrong Python
is being used — use the full interpreter path in Step 2.

### Step 2 — register the MCP server in LM Studio

**In one click** — GUI **Tools → MCP server… → LM Studio: Register**, or
`python -m pyfigures.mcp_control register lm_studio` (it writes the full path of
the Python running PyFigures).

**Via the config file** — LM Studio stores its MCP config in
`~/.lmstudio/mcp.json` (Windows: `C:\Users\<you>\.lmstudio\mcp.json`).

Always use the **full path** to the Python interpreter — never just `"python"`,
because LM Studio may resolve a different system Python that doesn't have
`pyfigures` installed.

**Windows (Conda example):**

```json
{
  "mcpServers": {
    "pyfigures": {
      "command": "C:\\Users\\<you>\\AppData\\Local\\miniconda3\\envs\\<env>\\python.exe",
      "args": ["-m", "pyfigures.mcp_server"]
    }
  }
}
```

**macOS / Linux (Conda example):**

```json
{
  "mcpServers": {
    "pyfigures": {
      "command": "/Users/<you>/miniconda3/envs/<env>/bin/python",
      "args": ["-m", "pyfigures.mcp_server"]
    }
  }
}
```

To find your exact interpreter path, run this in the target environment:

```bash
# Windows
where python

# macOS / Linux
which python
```

Alternatively, register via the UI: **LM Studio → Settings → MCP Servers →
Add Server**, fill in the name (`pyfigures`), the full interpreter path as the
command, and `-m pyfigures.mcp_server` as the argument.

Restart LM Studio after saving.

### Step 3 — choose a tool-capable model

Not every model supports tool calling. Look for the **🔧 badge** in LM Studio's
model browser — without it the model will ignore tool calls entirely.

| Model | Size | Notes |
|-------|------|-------|
| **Qwen2.5-7B-Instruct** | 7B | Best overall, highly recommended |
| **Qwen2.5-14B-Instruct** | 14B | More reliable on complex multi-step edits |
| **Llama-3.1-8B-Instruct** | 8B | Good, needs Tools toggle enabled |
| **Llama-3.2-3B-Instruct** | 3B | Works for simple requests |
| **Phi-4-mini-instruct** | 3.8B | Good on limited hardware |
| Nemotron, Gemma, most omni models | any | No tool-calling template — **will not work** |

### Step 4 — start a chat

1. Load your tool-capable model.
2. Open a **New Chat**.
3. Enable the **Tools** toggle in the chat toolbar (🔧 icon).
4. Type a request, e.g.:

   ```
   Describe the layout of C:\Users\me\figures\figure1.pyf
   ```

### Limitations with local models

| Limitation | Details |
|------------|---------|
| **Context window** | Large files returned by `get_xml` may exceed smaller models' context. Prefer `describe_figure`. |
| **Tool reliability** | Measured on the requests of the paper's Figure 3 plus three revisions (November 2026, three runs each): by recipe, Muse-Glimmer 28B got 17 of 18 steps right (3.5–4 min a run) and Qwen3.8 27B 16 of 18 (7–8 min); every miss kept a third colour when asked for "magenta and green" on a three-channel image. By individual tools the same models got 2 and 1 of 6. An 8B vision model failed every step (invented pixel size, crop margins read as coordinates). Ask models for a recipe (`build_figure_from_recipe`), and always check `render_preview`, above all pixel sizes and scale bars. |
| **Multi-step plans** | May need explicit prompting: "first call describe_figure, then add scale bars". |
| **Speed** | Each tool call is a round-trip; CPU-only inference can be slow for complex edits. |

---

## 4. Quick start — any OpenAI-compatible client

Any client that speaks the MCP protocol (stdio or HTTP/SSE transport) can connect.
The server supports the standard MCP stdio transport used by all major clients.

Run the server manually for debugging:

```bash
python -m pyfigures.mcp_server
# Server starts on stdin/stdout (MCP stdio transport)
```

For clients that connect to a URL (streamable HTTP at `http://127.0.0.1:8765/mcp`,
or the older SSE transport):

```bash
python -m pyfigures.mcp_server --transport http --port 8765
python -m pyfigures.mcp_server --transport sse --port 8765
```

`python -m pyfigures.mcp_control start` does the same in the background and
`stop` ends it (see "Starting, stopping and registering the server").

### Editing the figure open in the window (live)

The tools above work on `.pyf` files. To let a client edit the figure **open in
the PyFigures window** (unsaved work included, each edit one Undo step, nothing
written to disk until you save):

1. In PyFigures choose **Tools → Share the open figure with the MCP server**
   (or start PyFigures with `python -m pyfigures --share`). The window serves its
   figure on 127.0.0.1 only, behind a random token; one window at a time.
2. Point the client at the live server (the dialog shows this configuration):

```json
{"mcpServers": {"pyfigures-live": {
  "command": "python", "args": ["-m", "pyfigures.assistant.live_mcp"]}}}
```

It starts with six tools (inspect, preview, undo/redo, and categories to find
and run every PyFigures tool on the live figure). Set
`PYFIGURES_MCP_SURFACE=all` to list every tool directly.

**Chat sidebar.** **Tools → Chat sidebar (local model)…** (or `--chat`) docks
a chat beside the figure that drives the same server with a local model or an
API model. It is the separate package `qtpy-ai-sidecar`
(`pip install pyfigures[chat]` once it is published). Its profile is read from
`PYFIGURES_SIDECAR_CONFIG` or `sidecar.json` in the live folder
(`%LOCALAPPDATA%\PyFigures\assistant` on Windows); connection settings made in
the chat itself are remembered. While no model is set there, the chat uses the
model LM Studio serves on this computer (`http://127.0.0.1:1234/v1`); without
one, it says on opening how to get a model (Model Library, LM Studio or a cloud
API). **Help → Chat & MCP Tutorial** walks through it.

---

## 5. Available tools reference

The server currently exposes **175 tools** (about a fifth of them for the poster designer).
They are grouped below by purpose. Nearly every capability in the PyFigures GUI
has an equivalent tool here.

Code layout: `pyfigures/mcp_server.py` is the entry point (`python -m
pyfigures.mcp_server`) and re-exports everything; the tools live in the
`pyfigures/mcp_tools/` package — `app` (server object), `core` (shared helpers:
XML encoding, atomic save + layout update), `structure`, `content`,
`annotations`, `overlays`, `workflow`, `qc`, `export`, `poster`, `stacks`
(montage / channel split / kymograph / orthogonal views), `upkeep` (changed
sources, copy style, alt text).

**Changed sources.** A figure re-reads its images and CSVs every time it opens,
so it silently follows its sources. Every save (GUI or MCP) writes a snapshot of
the source files (size, date, content hash) to `<figure>.sources.json`; opening
the figure in the GUI, `check_source_changes`, and every MCP edit report files
that changed since (touched-but-identical files are not reported).

**Units.** The canvas unit is the point (1/72 inch), like the fonts. Physical
sizes (mm / journal columns) map to `mm / 25.4 × 72` canvas units; the *dpi* of an
export only decides its pixel count (a Nature double column, 183 mm, is 518.7 pt
on the canvas and 2161 px in a 300-DPI export).

**Moved figures.** Source paths that no longer exist are looked up relative to
the `.pyf`'s current folder (longest matching trailing path under the `.pyf`
folder and its parents), in the GUI and in every tool — a figure saved on Linux
opens on Windows without remapping. `find_moved_files` reports what was found.

### Reading & inspection tools

| Tool | Description |
|------|-------------|
| `describe_figure(pyf_path)` | Human-readable tree: groups, images, annotations, scale bars, insets, label rows |
| `get_xml(pyf_path)` | Raw XML content of the `.pyf` file |
| `list_images(pyf_path)` | JSON list of all image paths with group/index addresses |
| `get_annotations(pyf_path)` | ALL annotations and ROIs (text, rect, ellipse, line, polygon, …) with type and index |
| `get_figure_properties(pyf_path)` | Figure-level font, background colour, default spacing |
| `list_image_properties(pyf_path, group_path, image_index)` | All XML fields on an image |
| `get_image_property(pyf_path, group_path, image_index, property_name)` | Single image field |
| `audit_figure(pyf_path)` | Inventory every panel and flag what's missing — a quick QC pass |
| `figure_review_brief(pyf_path, journal, column)` | **Pre-submission reviewer brief**: all mechanical checks + caption + a visual-critique rubric, for an AI/human referee (pair with render_preview + simulate_color_blindness) |

### Creating tools

| Tool | Description |
|------|-------------|
| `create_figure(pyf_path, ...)` | Create a new empty `.pyf` file |
| `add_group(pyf_path, ...)` | Add a row/column group |
| `add_image(pyf_path, group_path, filename, ..., page)` | Add an image panel. A PDF (`page=N` picks a page of a multi-page PDF; rendered at 600 dpi unless `pip install pyfigures[pdf]` is installed, which keeps it vector) or an SVG file is a **vector panel**, kept as vectors in PDF/SVG exports, clip paths included (an SVG export embeds the panel's own SVG source, so its text stays editable) |
| `add_equation(pyf_path, group_path, latex, font_size, color, fontset, label, ..., engine, preamble, font)` | Add a **LaTeX equation** as a vector panel. `latex` is the formula or a `.tex` file. `engine="mathtext"` (default: Matplotlib, no TeX needed; `fontset="cm"` gives the LaTeX look) or `engine="latex"` (the computer's TeX Live / MiKTeX / MacTeX: full LaTeX, any environment, packages from `preamble`; `font="Arial"` sets text and maths letters, digits and Greek in that installed font with XeLaTeX). Written as an SVG in `equations/` next to the figure, so it opens anywhere; editable in the GUI (right-click → Edit equation…). `$…$` in any label text is typeset as maths too |
| `update_latex_panels(pyf_path, force)` | Recompile the panels made from `.tex` documents whose `.tex` changed since they were compiled (`force=True`: all of them), keeping which figure/table each one shows. Returns the panels updated and any that failed. GUI: right-click → Recompile from .tex, and an offer when the figure is opened |
| `install_latex(check_only)` | **Install LaTeX** for PyFigures: downloads TinyTeX (a small TeX Live, ~75 MB; ~400 MB on disk) into the user's folder (no admin rights, PATH unchanged) with every package PyFigures uses; packages a document needs later are added automatically. `check_only=True` only reports which LaTeX tools are found. GUI: Help → Install LaTeX for PyFigures… |
| `scan_folder(folder, pattern)` | Scan a folder for image files and return layout suggestions as JSON |
| `inspect_ome_zarr(path_or_url)` | Describe an **OME-Zarr** image (local `.zarr` folder or http(s) URL, e.g. the IDR) without reading pixels: axes, pyramid levels with pixel sizes in µm, channel names/colours, and the level read by default. `add_image` accepts the same path/URL; append `#level=N` to read another level. Needs `pip install pyfigures[zarr]` |
| `inspect_omero_image(image_url)` | Describe an image on an **OMERO** server from its OMERO.web link (`…/webclient/img_detail/ID/`, `…/webclient/?show=image-ID`, `…/iviewer/?images=ID`): name, X/Y/Z/T/C sizes, pixel size in µm, channels, and the planes `add_image` would read (`#z=0-9&t=0&c=0,2` selects planes). Pixels come from OMERO.web's renderer: 256 levels per channel over its data range (exact for 8-bit), or raw in the image's own type (16-bit, float) when omero-py is installed (`pip install pyfigures[omero]`) and a login is set; `raw_reader` in the result says which. Private data: set `OMERO_USERNAME` / `OMERO_PASSWORD` in the server's environment (never stored in figures). No omero-py / Ice needed |
| `create_figure_from_folder(pyf_path, folder, ...)` | Build a whole figure automatically from a folder of images |
| `draft_figure(folder, out_pyf, plot_kind, journal, px_to_unit, scale_bar_units, ...)` | **Draft a complete figure in one call**: image grid + CSV data-plot panels (with stats) + scale bars + A/B/C letters + journal size + caption stub |
| `recipe_reference()` | The recipe grammar in one reply: annotated example plus every accepted key per panel kind, journals, exports and checks (generated from the code, so always current) — what a model reads before writing a recipe |
| `build_figure_from_recipe(recipe_path, recipe_text)` | **Build a figure from a YAML/JSON recipe** — often the simplest route for a language model: write the whole figure as one recipe, build it in one call, check `render_preview`, edit and rebuild. With `recipe_text` the recipe is given inline (checked, saved to `recipe_path`, then built), so no file-writing tool is needed; `recipe_text` can also be a JSON object with the same keys (no YAML indentation to get right; saved as YAML for a `.yaml` path); invalid values are refused before anything is built. Rows of `image` / `glob` / `plot` panels with LUTs, crops, scale bars, lettering, drawings (rect, ellipse, circle, square, line, polygon, points), insets, journal size and caption; `checks` run before exporting (a failure means nothing is exported), `consolidate` bundles the source files, `template` + `fill` fills a template, `properties` sets stored panel fields, exports include `ledger` and `colorblind`. Reproducible and git-diffable (byte-identical rebuilds); also `python -m pyfigures.recipe build fig.yaml [--render png]` and GUI File → Build figure from recipe…. Full guide: `docs/RECIPES.md`; example: `docs/recipe_example.yaml` |
| `index_figures(root_dir, index_path, with_thumbnails, thumb_dpi)` | Scan a folder tree of `.pyf` files into a searchable **library index** (panels, labels, captions; incremental; optional thumbnails) |
| `search_figures(query, index_path, limit)` | Keyword-search the library index by panel filename / label / caption to find and reuse a past figure |
| `auto_configure_images(pyf_path, lut_preset, ...)` | Auto-assign LUTs / channels / normalisation across all panels |

### Layout & editing tools

| Tool | Description |
|------|-------------|
| `resize_figure(pyf_path, ...)` | Resize figure to a target physical width — supports mm, cm, inches, pixels, and named journal presets |
| `list_journal_presets()` | List the built-in journal size presets (single / 1.5 / double column) |
| `recompute_layout(pyf_path)` | Re-run the PyFigures layout engine on all top-level groups |
| `templatify_figure(pyf_path)` | Convert every image panel into an empty template slot (GUI: Template menu) |
| `set_spacing(pyf_path, group_path, spacing)` | Set pixel gap between panels |
| `set_orientation(pyf_path, group_path, orientation)` | Switch group to `X` (row) or `Y` (column) |
| `reorder_children(pyf_path, group_path, new_order)` | Reorder panels or groups |
| `move_image(pyf_path, ...)` | Move an image to a different position |
| `stack_with_image(pyf_path, src_group_path, src_image_index, target_group_path, target_image_index)` | Stack an image with another inside its row: A \| B + C → A \| (B / C) (GUI drop choice "Stack with it (column in the row)") |
| `set_size(pyf_path, group_path, image_index, width, height)` | Resize a panel |
| `layout_canvas(pyf_path, ...)` | Apply a full canvas layout |
| `set_image_filename(pyf_path, group_path, image_index, filename)` | Change the file a panel points to |
| `set_image_property(pyf_path, group_path, image_index, property_name, value)` | Set any Image2D field |
| `add_placeholder_grid(pyf_path, rows, columns, aspect_ratio, spacing)` | Add rows of empty placeholder panels (template slots) to fill later — a layout before the images exist, instead of fake images (GUI: Insert → Empty panel grid…) |
| `fill_template(pyf_path, group_path, image_index, filename)` | Fill a template slot |
| `batch_fill_templates(pyf_path, group_path, filenames)` | Fill all template slots at once |
| `clone_image(pyf_path, ...)` | Duplicate a panel |
| `remap_paths(pyf_path, old_prefix, new_prefix, ...)` | Bulk path remapping (e.g. Linux → Windows), including paths baked into channel-merge / data-plot panel scripts |
| `find_moved_files(pyf_path, apply)` | Report source files found at a new location relative to the `.pyf` (figure moved to another folder / disk / OS) and those still missing; `apply=True` writes the found paths |
| `set_figure_properties(pyf_path, ...)` | Set global font, letter colours, default spacing, and `page_background` — the colour of the whole figure behind the panels (the gaps between them); `"none"` = transparent (default), `"white"` keeps separators white in any viewer |
| `set_label_background(pyf_path, color="black", group_path=None, include_letters=True)` | Filled box behind panel letters, labels, time stamps and channel names so they read on any image (`"none"` removes). Skips data plots and scale-bar legends |

### Annotation & ROI tools

| Tool | Description |
|------|-------------|
| `add_annotation(pyf_path, group_path, image_index, text, placement)` | Add one floating text label |
| `add_corner_labels(pyf_path, group_path, image_index, top_left, top_right, bottom_left, bottom_right)` | Add stacked text labels to any/all corners in one call |
| `set_annotation_text(pyf_path, group_path, image_index, annotation_index, html_text)` | Edit annotation text (supports HTML); `annotation_index` = the `text_index` `get_annotations` reports |
| `style_annotation(pyf_path, group_path, ...)` | Restyle an existing text label (font, size, colour, weight, `background` box, `vertical_align` superscript/subscript, …), or only one word of it: `match` (+ `occurrence` when it occurs several times — otherwise the error asks which). GUI: double-click the text → Edit text, select the word. |
| `set_roi_properties(pyf_path, group_path, image_index, annotation_index, ...)` | Change an existing ROI, keeping the rest: outline `color`, `fill_color` (`"none"` removes it), `stroke`, `opacity`, `line_style` (solid/dashed/dotted/dash-dot), geometry in raw image pixels (`x`/`y`/`width`/`height`, `x1`…`y2`, `points`, `move_by`), arrowheads on/off. GUI: double-click the image → Edit Image, select the ROI. |
| `tidy_text(pyf_path)` | Apply conservative typography fixes (×, °, units, ranges, −) to every text label |
| `remove_annotation(pyf_path, group_path, image_index, annotation_index)` | Remove any annotation/ROI by index (ScaleBars and insets are protected) |
| `add_roi_rect(pyf_path, group_path, image_index, x, y, width, height, ...)` | Overlay a rectangular ROI (highlight box) |
| `add_roi_ellipse(pyf_path, group_path, image_index, x, y, width, height, ...)` | Overlay an ellipse or circle ROI |
| `add_roi_line(pyf_path, group_path, image_index, x1, y1, x2, y2, ...)` | Overlay a line or arrow (the arrowhead's point is exactly (x2, y2)) |
| `restyle_texts(pyf_path, target, font_family, font_size, color, bold, italic)` | Restyle a family of texts at once, keeping their words: `target` = `texts` (labels on panels, not letters), `letters`, `label_rows`, `scale_bars` or `all`. GUI: Annotations → Text style…; recipe: `text_style:`. |
| `add_arrow(pyf_path, group_path, image_index, tip_x, tip_y, from_direction, length, color, stroke, head, both_ends, label, style)` | **Point an arrow at a feature**: give the pixel it must point at and the side it comes from (`"nw"`, `"top left"`, degrees). The tip stays exactly on that pixel at any figure size / zoom / export DPI; the head keeps a constant size on the page (1 pt line, 8 pt head by default) and the tail is kept inside the image. `style="arrowhead"`: the head alone, larger (no line), as in papers; `get_annotations` reports `kind` `arrow` / `arrowhead` / `line`. GUI: Annotations → Add arrow pointing at a feature… (Style), or the image editor's Arrowhead tool. |
| `add_roi_polygon(pyf_path, group_path, image_index, points, ...)` | Overlay a polygon, open polyline, or freehand shape |
| `add_significance_bracket(pyf_path, group_path, image_index, x1, x2, y, label, ...)` | Add a stats bracket (bar + end whiskers + centred label like `*` / `n.s.` / `p<0.001`) |
| `add_significance_bracket_from_data(pyf_path, group_path, image_index, x1, x2, y, values_a, values_b, ...)` | Same, but **computes** the stars from a two-group test (auto Welch t / Mann-Whitney) and records the test + p-value for the Methods section |

Common ROI parameters: `color` (name/hex/int), `fill_color` (null = transparent), `stroke` (line width px), `opacity` (0–1).  
`add_roi_polygon` accepts `style="polygon"` (closed), `"polyline"` (open), or `"freehand"`.  
`points` can be flat `[x0,y0,x1,y1,…]` or paired `[[x0,y0],[x1,y1],…]`.

### Scale bar tools

| Tool | Description |
|------|-------------|
| `get_scale_bar(pyf_path, group_path, image_index)` | Read scale bar settings |
| `set_scale_bar(pyf_path, group_path, image_index, bar_width_in_units, ...)` | Add/update scale bar on one image (`bar_color` is drawn — stored as `bar_color`; files without it draw white) |
| `remove_scale_bar(pyf_path, group_path, image_index)` | Remove scale bar |
| `set_scale_bar_all(pyf_path, bar_width_in_units, ...)` | Apply the same scale bar to every image |

### Inset / picture-in-picture tools

| Tool | Description |
|------|-------------|
| `add_inset(pyf_path, group_path, image_index, inset_filename, ...)` | Overlay a second image on a panel |
| `add_zoom_callout(pyf_path, group_path, image_index, source_x, source_y, source_w, source_h, ...)` | Zoom/magnified-detail callout: ROI box + magnified inset + leader lines (inset flush in its corner, leaders on its corners). GUI: Annotations → Add zoom callout to selected panel… |
| `list_insets(pyf_path, group_path, image_index)` | List all insets on a panel |
| `remove_inset(pyf_path, group_path, image_index, inset_index)` | Remove an inset |
| `set_inset_property(pyf_path, group_path, image_index, inset_index, property_name, value)` | Edit any inset field |

### Stack tools (several views of one stack — opt-in)

A stack added with `add_image` shows **one** image (a frame / slice, or a Z
projection via `configure_image(projection="max")`). These tools are for when the
figure should show more of it. GUI: Insert → Stack views.

| Tool | Description |
|------|-------------|
| `add_stack_montage(pyf_path, stack_path, axis, frames, columns, parent_group_path, projection, z_range, z_slice, channel, lut, interval, unit, stamps, ...)` | Several frames of a time-lapse (`axis="t"`) or Z series (`"z"`) side by side with stamps ("0 min, 2 min…", "0 µm, 0.5 µm…"). `frames`: N evenly spaced (default 6), `"all"`, `"::5"`, or a list. `columns`: default one row up to 6 frames, then rows of at most 6 (short last row padded with empty panels). `z_range=[first, last)` limits the Z projection; `z_slice` picks the slice when `projection="none"`. Interval / Z step from the file (ImageJ, LSM, OME). Native panels (no script); one panel letter for the whole montage. `crop={"bottom": 24}` crops every frame |
| `add_channel_split(pyf_path, stack_path \| channel_files, names, colors, gray, include_merge, crop, ...)` | The channel-split row: each channel (grayscale with its name in the channel colour, or tinted) then the merge. `crop={"bottom": 24}` crops every panel (e.g. text burned into the image); in the GUI, a cropped source panel's crop is offered for every new panel |
| `add_kymograph(pyf_path, group_path, image_index, x1, y1, x2, y2, line_width, channel, projection, frame_height, ...)` | Kymograph (position along a line × time, time downwards) from the time stack in a panel; draws the line on the source; keeps the source's pixel size so a scale bar measures distance |
| `add_orthogonal_views(pyf_path, group_path, image_index, x, y, z, time_point, channel, colors, z_scale, gap, crosshair, ...)` | XY + YZ (right) + XZ (below) cut through a voxel of a Z stack, Z scaled to true proportions from the voxel size; crosshair lines are editable annotations |

### Row/column label tools

| Tool | Description |
|------|-------------|
| `add_label_row(pyf_path, group_path, labels, position, ...)` | Add a row of text labels above/below a group |
| `add_side_label(pyf_path, group_path, label, position, ...)` | Add a label to the left/right (or top/bottom) of a group |
| `list_label_rows(pyf_path)` | List all label-row groups in the figure |
| `remove_label_row(pyf_path, group_path)` | Remove a label-row group |

### Image display tools

| Tool | Description |
|------|-------------|
| `transform_image(pyf_path, group_path, image_index, ...)` | Rotate, flip (H/V), crop edges, set opacity or fill colour |
| `preview_panel_source(pyf_path, group_path, image_index, brighten)` | One panel's whole source, uncropped, with pixel rulers and its current crop as a dashed box (contrast stretched for the preview only): read crop values off it before `transform_image` (read-only). Live chat: `preview_panel(panel_ref)`; `open_annotation_editor(panel_ref, tab)` opens the editor on a tab (`crop`/`rotate`, `text`, `scale`, `script`, `export`, `layers`) |
| `set_figure_colors(pyf_path, colors, single_channel)` | Recolour the whole figure in one call ("use magenta and green"): channel *i* of every multi-channel image, merge and channel split takes colour *i* (split labels follow); single-channel images become gray (`single_channel="keep"` leaves them); colour photographs are kept; plots take the colours only when they have that many groups, else Okabe–Ito; `["colorblind"]` = magenta/green + Okabe–Ito on every plot. Recipe: top-level `colors`. GUI: Annotations → Figure colours… |
| `set_lut(pyf_path, group_path, image_index, luts, ...)` | Set colour LUTs per channel; optional intensity normalisation. Names are case-insensitive (`matplotlib_viridis` works), as people write them (`viridis`, `inverted gray`, `reversed viridis`); unknown names are rejected with suggestions. Inverted LUTs: `<NAME>_INVERTED` (GRAY_INVERTED: dark on white), `MATPLOTLIB_<name>_r`. A plotting-script panel is refused (change its script's `cmap`) |
| `invert_lut(pyf_path, group_path, image_index, channels=None)` | Invert the panel's current LUTs (Fiji's Invert LUT; again restores them): GRAY ↔ GRAY_INVERTED, viridis ↔ viridis_r. GUI: Set LUT(s) → Invert |
| `preview_luts(luts)` | Image of the LUTs' colour ramps, to compare before choosing (read-only). GUI: ramps in the Set LUT(s) dialog |
| `configure_image(pyf_path, group_path, image_index, ...)` | Set active channels, Z-projection mode, Z range, series index, normalisation |
| `add_channel_merge(pyf_path, group_path, channel_files, colors, mode, ..., normalization)` | Overlay 2–4 single-channel images into one pseudo-coloured composite panel. `normalization="per_channel"` (min–max stretch, disclosed in the adjustment ledger) or `"none"` (raw intensities) |
| `add_lut_calibration_bar(pyf_path, group_path, ..., image_index=None)` | Add a LUT/intensity calibration colour bar. With a panel (`image_index`, or `panel_ref` live) it goes right after that panel and, without `lut`, uses the panel's LUT or its script's colour map. GUI: Insert → LUT colour bar… with the panel selected |

`configure_image` parameter overview:

| Parameter | Values | Effect |
|-----------|--------|--------|
| `channels` | `[true, false, true]` | Show/hide individual channels |
| `projection` | `"max"` / `"min"` / `"avg"` / `"none"` | Z-projection mode (`"none"` clears it) |
| `projection_z_start` | int (−1 to clear) | First Z slice for projection |
| `projection_z_end` | int (−1 to clear) | Last Z slice (exclusive) for projection |
| `serie_to_open` | int (−1 to clear) | Series index for multi-series files (.lif, .czi) |
| `normalization` | JSON dict string | Intensity normalisation (see table below) |
| `clear_normalization` | `true` | Remove normalisation, revert to auto-scaling |

Normalisation dict examples:

| Dict | Effect |
|------|--------|
| `'{"per_channel": true}'` | Auto-scale each channel independently |
| `'{"range": "display"}'` | Scale to per-frame min/max |
| `'{"range": "custom", "min_value": 200, "max_value": 3500}'` | Fixed 16-bit window |
| `'{"ignore_hot_spots": 0.01}'` | Remove top 1% hot-spots before scaling |

### Scripted image tools

| Tool | Description |
|------|-------------|
| `add_scripted_image(pyf_path, group_path, script, label, ...)` | **Add a new matplotlib/numpy panel in one step** — preferred over add_image + set_script. Scripts can also call `latex(code)` (returns a vector panel from LaTeX code), or be LaTeX code themselves |
| `add_latex_code(pyf_path, group_path, code, preamble, label, label_placement)` | Add a **LaTeX code panel**: TikZ / pgfplots picture, tabular, maths or a whole document, compiled into a vector panel; the code stays editable (GUI right-click → Edit LaTeX code…) and the PDF is kept in `equations/labels` so the figure opens without TeX. Compile errors are returned at once |
| `get_script(pyf_path, group_path, image_index)` | Read the Python script on a panel |
| `set_script(pyf_path, group_path, image_index, script)` | Replace the script on an existing panel |

### Data-plot & statistics tools

Render statistical charts straight from a CSV of measurements, with automatic,
correctly-chosen significance tests. These use the **`staplot`** package (a soft
dependency — `pip install staplot`); without it a data-plot panel shows an
install hint instead of failing. The chosen test and every p-value are recorded
in a `<figure>.stats.json` sidecar and surface in `export_adjustment_ledger`'s
Methods output.

| Tool | Description |
|------|-------------|
| `add_data_plot(pyf_path, group_path, csv_path, kind, error, annotate_stats, stats_mode, ...)` | Add a **live** plot panel (`bar` / `box` / `violin` / `scatter` / `grouped`) from a CSV; re-renders when the CSV changes. bar/box/violin auto-add significance brackets (Welch t / Mann-Whitney for 2 groups; ANOVA+Tukey / Kruskal+Dunn for >2); scatter shows correlation r/R²/p; grouped runs two-way ANOVA. `latex=True` typesets the plot's text with LaTeX (sans-serif; siunitx in labels) |

CSV layout: **wide** (one column per group, rows = replicates) or **long**
(`group,value`); `grouped` needs `factor_a,factor_b,value`.
`stats_mode` = `auto` (pick parametric vs non-parametric by a normality check),
`parametric`, or `nonparametric` — forces the test family for group comparisons.

### Figure caption / legend tools

The caption lives in a `<figure>.caption.json` sidecar next to the `.pyf` — kept
out of the figure artwork so it can't corrupt the XML. Consolidate/move the pair
together.

| Tool | Description |
|------|-------------|
| `set_figure_caption(pyf_path, caption, title)` | Store the figure's legend text (+ optional short title). Empty caption clears it |
| `get_figure_caption(pyf_path)` | Return the stored caption/title as JSON |
| `export_caption(pyf_path, out_path, fmt)` | Write the caption to a `.txt` / `.md` file for manuscript submission |

### QC & journal-compliance tools

| Tool | Description |
|------|-------------|
| `check_resolution(pyf_path, min_dpi, journal, column)` | Flag panels below a target print DPI at the figure's physical width |
| `check_scale_consistency(pyf_path, tolerance)` | Flag panels whose **displayed physical scale** differs (a µm feature occupies different on-figure pixels per panel) so they can't be honestly compared by eye; recommends the on-figure width to fix each |
| `enforce_min_font_size(pyf_path, min_pt, ...)` | Bump every label up to a minimum point size |
| `check_journal_compliance(pyf_path, journal, ...)` | Report width / DPI / font issues against a journal's rules |
| `apply_journal_guidelines(pyf_path, journal, ...)` | Bundle: resize + min-font + resolution fixes for a journal in one call |
| `list_journal_presets()` | List the built-in journal size presets |

### Image-integrity & provenance tools

| Tool | Description |
|------|-------------|
| `check_image_integrity(pyf_path, ...)` | Screen panels for integrity red flags: exact file reuse, near-duplicates, cloned regions |
| `export_adjustment_ledger(pyf_path)` | Per-panel record of every pixel-affecting adjustment + ready-to-paste Methods text |

### Accessibility & colour tools

| Tool | Description |
|------|-------------|
| `simulate_color_blindness(pyf_path, cvd_type, ...)` | Render the figure as a colour-blind reader would see it (returns an image) |
| `generate_alt_text(pyf_path, save)` | Draft alt text (screen-reader description) from the figure's content: panel letters, micrograph colours, merges, montages, channel splits, chart type + compared groups + recorded statistics, kymographs, scale bars, arrows. Returns a short sentence (≤ 250 chars) and a panel-by-panel description. GUI: File → Alt text (accessibility)… |
| `set_alt_text(pyf_path, long, short)` | Store the reviewed alt text in `<figure>.alttext.json` |

### Journal styles from a journal's own guidelines

For a journal without a built-in preset (or to follow its current page): the
user pastes the figure-guidelines text of the journal's web page; the model
extracts the rules into a style; PyFigures checks that every rule quotes the
pasted text and that its number is written there with its unit (cm / inches →
mm, ppi → dpi) and refuses the draft otherwise. Styles saved through MCP are
drafts; a person marks them reviewed in **QC → Journal styles…** (the editor:
paste, extract with a local model or paste a chat model's reply, correct rules
— an edited value becomes a `manual` rule —, save new versions). Built-in
presets are never changed; every save is a new version in
`~/.pyfigures/journal_styles/`.

| Tool | Description |
|------|-------------|
| `journal_info(journal)` | Is the journal available? Built in → its column widths (only those its page gives: single / 1.5 / double / triple), the page and what it says; imported → its widths and rules; otherwise `not_available`, close names, and the steps to import it from the journal's pasted page. Call it before sizing a figure |
| `prepare_journal_style_import(pasted_text, journal, stage, source_url, article_type)` | Instructions + JSON schema for the host model; nothing is saved |
| `save_journal_style(style_json, pasted_text, journal, stage, ...)` | Check the model's JSON against the pasted text and save a new draft version; the error names the rule to fix. Returns `use_as`, the name to pass as `journal=` |
| `validate_journal_style(style_json)` | Check a complete style without saving |
| `list_journal_styles()` / `get_journal_style(journal, stage)` | Saved styles (latest versions) / one style with its rules and quotes |
| `extract_journal_style(pasted_text, journal, model, stage, source_url, base_url, save)` | Extraction by a local model already loaded in LM Studio (or any OpenAI-compatible server); nothing is loaded or started |

A saved style is accepted wherever a journal is: `resize_figure`,
`check_journal_compliance` (which then also uses the style's minimum font size
and photograph DPI, and lists all its rules so the unchecked ones can be
checked by hand), `check_resolution`, `apply_journal_guidelines`, recipes'
`journal:` and the GUI's journal dialogs. Use its title, or `custom:<title>`
when the title is also a built-in name; columns are `single` / `1.5` /
`double` or a width rule's own label (`"3 columns"`). Command line:
`python -m pyfigures.journal_styles prompt|extract|import|validate|save|list|show`.

### "Show me how" tools (teach the user in the open PyFigures window)

When the user wants to learn an operation, or a model cannot do a long task
reliably, these tools open a short guide in the user's PyFigures window: the
real menus are outlined one level at a time in a floating, closable bubble and
the user does the clicks. Showing a guide never edits the figure
(`operation_executed` is always false); the guide watches for the user's
result (a split row appears, the LUTs change…) and reports `completed`.

| Tool | Description |
|------|-------------|
| `list_how_to_guides()` | The guides: id, title, summary, and `do_it_tool` (the tool that does the same operation directly) |
| `show_me_how(operation, pyf_path)` | Open a guide by id (`split_channels`, `crop_image`, `set_lut`, `zoom_inset`, `add_scale_bars`, `panel_letters`, `add_data_plot`, `channel_merge`, `journal_check`, `apply_journal`, `check_resolution`, `export_pptx`, `figure_caption`, `presubmission_review`, `colour_bar`, `colour_blind_preview`) or by the user's words ("how do I crop?"; an ambiguous request returns candidates). `pyf_path` picks the window when several are open. No window open → `gui_unavailable` plus the steps as text |
| `guidance_status(pyf_path)` | `guidance_shown` (with the current step), `completed`, `cancelled`, `guidance_closed` or `no_guide` |
| `close_guidance(pyf_path)` | Close the guide; the figure is not changed |
| `explain_how(operation)` | The same authored steps as text, no GUI needed |

The same guides are in the GUI under **Help → Show me how…**, and on the
command line: `python -m pyfigures.guides list | explain <op> | show <op> |
status | close`. The MCP server reaches a window through a local folder
(`~/.pyfigures/gui_sessions/`) that the window opens at launch; a request must
carry that window's random token and can only name a guide from the registry
(`pyfigures/guides.py`), never code or screen coordinates. There is no recipe
key: guides are interactive by nature.

### Consistency & upkeep tools

| Tool | Description |
|------|-------------|
| `check_source_changes(pyf_path, accept)` | List source images / CSVs changed or missing since the figure was last saved; `accept=True` makes the current files the reference. GUI: QC → Check for changed source files… (and a notice when a figure opens) |
| `copy_style(source_pyf, target_pyf, aspects, dry_run)` | Give a figure the look of another (e.g. an accepted one): `fonts`, `letters` (size/weight/colour/corner/case), `scale_bars` (colour, corner, label style), `spacing` (per nesting level), `plots` (chart font size, line widths). Content untouched. GUI: File → Copy style from another figure… |
| `list_history(pyf_path, last)` | Every MCP call made on the figure, newest last: tool, arguments, status, whether it changed the figure, whether it was undone. GUI: Tools → MCP call history / undo…; command line: `python -m pyfigures.history fig.pyf` |
| `undo_last(pyf_path, steps, force)` | Put the figure (`.pyf` and sidecars) back as it was before the last *steps* changing MCP calls; refused when the figure was changed since outside the server (GUI…) unless `force=True`. GUI: the same dialog; command line: `python -m pyfigures.history fig.pyf --undo 2` |

| `mcp_server_info()` | The Python running the server, the number of tools, which MCP clients have it registered and whether the HTTP server runs. Read-only. GUI: Tools → MCP server…; command line: `python -m pyfigures.mcp_control status` |
| `list_bug_recordings(folder=None)` | The bug recordings the user made in the GUI (Help → Debug → Start recording a bug…), newest first: folder, date, steps, Python errors, what went wrong. Recordings stay in the user's own folder, never in a repository. Command line: `python -m pyfigures.gui.bug_recorder list` |
| `read_bug_recording(path)` | One recording step by step: menu actions, right-click / drop-menu choices, drops, dialogs with their values, file pickers, double-clicks and drags, the figure's rows after each step, errors with tracebacks, the steps marked wrong, what went wrong and what was expected, screenshot paths. `python -m pyfigures.gui.bug_recorder make-test <folder> <tests/recordings/name>` turns it into a regression test (replayed by tests/test_recordings.py). |

**Call history.** Every tool call that reaches the server and names a figure
(any `.pyf` argument, or a recipe's `output`) is appended to
`<figure>.history/log.jsonl` beside it, with the figure as it was before each
changing call (the last 100 are kept). Calls made from Python — the GUI, a
recipe's internal steps — are not logged one by one; a recipe build is one
logged call.

### Typography & font tools

| Tool | Description |
|------|-------------|
| `list_fonts(pyf_path)` | Report the figure's font situation, including PyFigures' bundled portable fonts |
| `list_colors(query)` | Colour names for image channels (`set_figure_colors`) and for drawings (outlines, text, arrows, ROIs); with a query, whether that colour works for each |
| `tidy_text(pyf_path)` | Conservative typography auto-fixes across all labels (also listed under annotations) |

### Rendering & export tools

| Tool | Description |
|------|-------------|
| `export_figure(pyf_path, out_path, dpi)` | Render the figure to a final image file — the shippable deliverable |
| `render_preview(pyf_path, dpi, max_dimension)` | Render to a PNG and return it as a viewable image |
| `export_latex(pyf_path, out_path, image_format, with_caption)` | 'PDF + LaTeX': text-free vector graphic + `\input`-able LaTeX label overlay; `with_caption` wraps it in a `figure` float using the stored caption |
| `export_pptx(pyf_path, out_path)` | **Editable PowerPoint** (.pptx): one slide the size of the figure, one group per panel — pictures plus native text boxes (letters, labels, scale-bar text) and shapes (scale bars, ROIs, arrows, brackets, vector plots); crops and rotations kept. `$…$` maths in labels becomes native PowerPoint equations (Unicode text in the Illustrator script). Text inside data plots (ticks, axis titles, stars) is editable too; text inside imported SVG/PDF graphics stays outlines. GUI: Export As → PowerPoint (editable)… |
| `export_vectorcraft(pyf_path, out_path)` | **VectorCraft document** (.vectorcraft, one self-contained file) for VectorCraft, the open-source Illustrator replacement: one layer, one clip group per panel, embedded images, live point type and vector paths; verified with VectorCraft's own reader. GUI: Export As → VectorCraft (editable)… |
| `export_deckcraft(pyf_path, out_path)` | **DeckCraft deck** (.deckcraft) for DeckCraft, the open-source PowerPoint replacement: one slide the size of the figure, one group per panel, pictures, editable text boxes and freeform shapes; verified with DeckCraft's own reader. DeckCraft also opens the `export_pptx` file. GUI: Export As → DeckCraft slide (editable)… |
| `export_illustrator_script(pyf_path, out_path)` | **Adobe Illustrator script** (.jsx + `<stem>_assets` PNG folder): run it in Illustrator (File → Scripts → Other Script…) to rebuild the figure with one group per panel, live text (ArialMT…) and vector paths. GUI: Export As → Adobe Illustrator script (.jsx)… |
| `export_print_ready(pyf_path, out_path, color_mode, dpi)` | High-DPI (optionally CMYK) TIFF for a journal's printed version |
| `export_video(pyf_path, out_path, frame_mode, bg_color)` | Export an animated figure (movies / time stacks) to `.mp4`, `.mov`, `.mkv`, `.webm` or `.avi`. With PyAV (`pip install av`, bundles ffmpeg) mp4/mov/mkv are H.264 and webm is VP9 — `.mp4` plays everywhere including on a Mac; without it OpenCV's MPEG-4 is used and the result carries a WARNING. Returns the path, size and `codec` |
| `consolidate_figure(pyf_path, out_pyf, download_remote=False)` | Save a self-contained copy with every referenced image bundled alongside. Remote images (web links, OME-Zarr URLs, OMERO links) stay links unless `download_remote=True` (local OME-Zarr of what the panel shows, or the file itself); failures are listed in `not_downloaded` |
| `export_source_data(pyf_path, out_dir, dpi, image_format)` | Assemble a journal **Source Data bundle**: rendered figure + each panel's source image/CSV/script + caption + statistics + a Methods paragraph + a per-panel manifest |
| `diff_figures(old_pyf, new_pyf)` | Compare two figure versions — panels added/removed/moved/resized, scale-bar/label/adjustment/pixel-size/caption changes — as structured JSON (revision rounds) |
| `export_figure_diff(old_pyf, new_pyf, out_html, dpi)` | **Visual diff**: self-contained HTML with both renders side by side, a pixel-difference overlay (changed pixels tinted red) and the change list |

### Review-workflow tools

| Tool | Description |
|------|-------------|
| `export_review(pyf_path, out_html, dpi)` | Export a self-contained HTML review page for a co-author |
| `list_review_comments(pyf_path)` | List the review comments stored in the figure's sidecar |
| `import_review_comments(pyf_path, review_html)` | Pull comments from a reviewed HTML page back into the sidecar |

### Other tools

| Tool | Description |
|------|-------------|
| `remove_image(pyf_path, group_path, image_index)` | Delete an image panel |
| `remove_group(pyf_path, group_path)` | Delete a group |
| `write_xml(pyf_path, xml_content)` | Raw XML write (advanced / fallback) |

### Poster / collage designer tools

A separate tool for posters and photo-album pages — free rotation/
positioning instead of tight scientific packing, saved as `.pyfposter`
(single page) or `.pyfalbum` (multi-page photo album — front cover, interior
spreads, back cover). See [docs/poster.md](poster.md). Never reads or
writes `.pyf` files.

Every tool below except the page-management ones and `list_poster_layouts`
accepts an optional `page: int` (0-based) to target one page of a multi-page
album; omit it for a plain single-page poster, or to target page 0 of an album.

| Tool | Description |
|------|-------------|
| `create_poster(poster_path, page_preset, page_width_mm, page_height_mm)` | Create a new, empty poster page (default preset `A4`) |
| `create_album(album_path, page_preset, page_width_mm, page_height_mm)` | Create a new, empty photo album (`.pyfalbum`, added when the path has no extension; must not exist yet): front cover (page 0), one spread (page 1), back cover (page 2) — fill it with the poster tools' `page` argument; pages added later are spreads between the covers, and covers can't be removed/moved/duplicated/re-kinded. An existing poster is never converted into an album |
| `add_poster_page(poster_path, kind, width_mm, height_mm, index)` | Add a page — `kind` is `spread` (default, two pages as one continuous canvas, double-width), `cover_front`/`cover_back`, or `single`; turns the document into a `.pyfalbum` the moment it has more than one page |
| `list_poster_pages(poster_path)` | List every page: index/kind/width_mm/height_mm/shape_count/has_background |
| `remove_poster_page(poster_path, page)` / `duplicate_poster_page(poster_path, page)` | Delete or copy one page (errors removing the last remaining page) |
| `move_poster_page(poster_path, from_index, to_index)` | Reorder pages |
| `set_poster_page_kind(poster_path, page, kind)` | Change a page's kind after the fact (size/content untouched) |
| `add_poster_image(poster_path, image_path, x_mm, y_mm, width_mm, height_mm, theta, frame, caption, page)` | Add a photo, freely positioned/rotated (rotation grows the box, never crops); `frame` is `none`/`simple`/`polaroid` |
| `add_poster_text(poster_path, html, style, x_mm, y_mm, width_mm, height_mm, theta, page)` | Add a freely positioned/rotated text box (title/caption); `html` is plain text or simple HTML for formatting (omit for the style's placeholder wording); `style` is `h1`/`h2`/`h3`/`body`(default)/`caption` — a Markdown-heading-like size *as a fraction of the page height*, so it scales with page size; overridden by width_mm/height_mm if given |
| `set_poster_background(poster_path, image_path, zoom, pan_x, pan_y, page)` / `clear_poster_background(poster_path, page)` | Set or remove the full-page background image; always covers the page (no gaps), `zoom`>=1.0 and `pan_x`/`pan_y` (0..1, 0.5=centered) set its crop/position |
| `adjust_poster_background(poster_path, zoom, pan_x, pan_y, reset, page)` | Re-crop/reposition an existing background without replacing it; `reset=True` centers it at zoom 1.0 |
| `list_poster_images(poster_path, page)` | Page size, background, and every image's geometry/frame/caption/`is_template`/`group_id`/crop fractions |
| `set_poster_image_frame(poster_path, index, frame, caption, page)` | Change one image's frame/caption after the fact |
| `remove_poster_image(poster_path, index, page)` | Delete one image |
| `arrange_poster_scatter(poster_path, indices, seed, margin_mm, max_rotation_deg, fit_to_page, page)` | "Photos thrown on a table": random position + tilt |
| `arrange_poster_arc(poster_path, center_x_mm, center_y_mm, radius_mm, indices, start_angle_deg, end_angle_deg, face, fit_to_page, page)` | Fan images along an arc, like a spread hand of photographs |
| `arrange_poster_grid(poster_path, indices, columns, margin_mm, gap_mm, fit_to_page, page)` | Tidy rows/columns, resized to fit, rotation reset |
| `align_poster_shapes(poster_path, mode, indices, page)` | Align shapes to each other — `mode` is `left`/`right`/`top`/`bottom`/`center_h`/`center_v`, using the targeted group's own bounding box as the target; needs 2+ shapes (omit `indices` for every shape on the page) |
| `distribute_poster_shapes(poster_path, axis, indices, page)` | Evenly space shapes' centers along `axis` (`x`/`y`) between the two outermost, which stay put; needs 3+ shapes |
| `list_poster_layouts()` | List pre-designed page layouts (name/label/description/slot_count) — pick a slide layout, PowerPoint-style |
| `apply_poster_layout(poster_path, layout_name, indices, margin_mm, repeat, group, page)` | Fill a named layout's slots with the photos already on the page, one call; more photos than slots repeats the pattern in bands down the page (`repeat=True` default); placed images are grouped by default (`group=True`) so they drag as one block |
| `sketch_poster_layout(poster_path, layout_name, margin_mm, group, page)` | Add a named layout's slots as empty placeholders (no photos needed yet) — the poster analogue of `templatify_figure` |
| `fill_poster_template_slot(poster_path, index, image_path, page)` | Fill one empty template slot by index with a real photo, fit inside the slot's box — the poster analogue of `fill_template` |
| `ungroup_poster_images(poster_path, index, page)` | Break apart the layout group image *index* belongs to, so its members move independently again |
| `render_poster(poster_path, out_path, dpi, page)` | Render one page to PNG/TIFF/JPEG/SVG/PDF |
| `render_poster_album(poster_path, out_path, dpi)` | Render every page as one multi-page PDF (a spread becomes one double-width PDF page) — the whole photo album in one file |
| `preview_poster(poster_path, dpi, max_dimension, page)` | Render one page to a PNG and return it as a viewable image |
| `export_poster_print_ready(poster_path, out_path, format, color_mode, dpi, page)` | Print-ready export of one page: `format` `tiff`/`eps` (raster, `color_mode` `cmyk`/`rgb`) or `pdf`/`svg` (vector, always RGB) |
| `export_poster_album_print_ready(poster_path, out_path, format, color_mode, dpi)` | Print-ready export of every page; `pdf` writes one multi-page file, `tiff`/`eps`/`svg` write a folder (one file per page + manifest.json) |
| `export_poster_source_data(poster_path, out_dir, dpi)` | Consolidate the document into a self-contained folder: portable copy + every image/background file copied and renamed by page; any photo flattened from a `.pyf` gets that figure's own Source Data bundle nested alongside it |
| `export_poster_web(poster_path, out_path, dpi, quality)` | Export as a single self-contained `.html` "photo book": every page embedded as a base64 JPEG, with a click/arrow-key/swipe page-flip viewer — a shareable way to send a photo album to anyone with just a browser, no app install needed |
| `build_poster_from_recipe(recipe_path)` | Build a whole poster / photo album from a YAML/JSON recipe (pages, backgrounds, photos or globs, arrangement per page, text; optional PDF/PNG render and HTML photo book) — same recipe as the poster GUI's *Build from recipe…* and `python -m pyfigures.poster.poster_headless build`. See docs/poster.md |

All three `arrange_poster_*` tools default `fit_to_page=True`: a result that
would hang off the page is shrunk/recentered as a whole group to fit; one
that already fits is left untouched. Pass `fit_to_page=False` for the raw,
unclamped geometry.

---

## 6. Example prompts

```
Describe the layout of /data/figure1.pyf
```

```
Add a 10 µm white scale bar at the bottom-right of every image in figure1.pyf.
The pixel size is 0.065 µm/px.
```

```
Add column headers "WT", "KO", and "Rescue" above group 0 in figure1.pyf
```

```
Add a vertical label "Treated" to the left of group 1 in figure1.pyf
```

```
Add a picture-in-picture inset from /data/detail.tif to image 0 in group 0 of
figure1.pyf. Place it in the top-right corner at 25% of the parent image width,
with a yellow 3 px border.
```

```
Remap all image paths in figure1.pyf from /home/alice/data to C:\Users\alice\data
```

```
Create a new figure at /data/new_figure.pyf with a 3-image horizontal row,
then add images /data/img1.tif, /data/img2.tif, /data/img3.tif.
Add "A", "B", "C" corner labels and a 10 µm scale bar to each.
```

```
Merge /data/dapi.tif, /data/gfp.tif and /data/rfp.tif into a single composite
panel in figure1.pyf, colouring them blue, green and red.
```

```
Add a significance bracket over the first panel of figure1.pyf spanning x=40
to x=180 at y=20, labelled "**".
```

```
Add a box-plot panel to figure1.pyf from counts.csv (kind=box, y-axis
"cells / field", label "D") and let it pick and draw the significance brackets
automatically.
```

```
Set the caption of figure1.pyf to "Confluent MDCK cells at 63×; scale bar 10 µm."
with title "Figure 1", then export 'PDF + LaTeX' to /out/figure1 with the
caption included.
```

```
Check figure1.pyf against Nature's guidelines, then apply them, and screen the
panels for image-integrity issues (duplicated or cloned regions).
```

```
Draft a figure from the folder /data/exp1 (bar charts for the CSVs), sized to
Nature double column, with 10 µm scale bars at 0.1 µm/px, and save it as
/data/exp1/Figure1.pyf.
```

---

## 7. Troubleshooting

### "Plugin process exited with code 1" (LM Studio)

The MCP server subprocess crashed on startup. Almost always this means the
Python interpreter used by LM Studio does not have `pyfigures` installed.

**Fix:**

```bash
# 1. Find the interpreter LM Studio is actually using (run in a terminal):
#    Windows:
where python
#    macOS / Linux:
which python

# 2. Install into that exact interpreter:
/full/path/to/python -m pip install --no-deps pyfigures
/full/path/to/python -m pip install "mcp[cli]"

# 3. Verify the server starts cleanly:
/full/path/to/python -m pyfigures.mcp_server
# → should hang silently (waiting for MCP input). Ctrl+C to stop.
```

Then update the MCP config to use that **full interpreter path** instead of
just `"python"`:

```json
{
  "mcpServers": {
    "pyfigures": {
      "command": "/full/path/to/python",
      "args": ["-m", "pyfigures.mcp_server"]
    }
  }
}
```

### "No module named pyfigures"

Same root cause as above — the wrong Python interpreter is being used.
Install with `--no-deps` (avoids pulling in GUI dependencies not needed by
the server) and use the full interpreter path in the MCP config:

```bash
pip install --no-deps pyfigures
pip install "mcp[cli]"
```

### Tools not appearing in LM Studio

1. Confirm LM Studio version is **0.3.6 or later**.
2. Make sure the **Tools** toggle is enabled in the chat UI.
3. Check the LM Studio logs (Help → Show Logs) for MCP connection errors.
4. Restart LM Studio after adding/editing the MCP config.

### Model calls wrong tool / passes wrong arguments

Switch to a larger or more capable tool-calling model (7B+). Some models require
explicit prompting, e.g.:
> "Use the describe_figure tool on /path/to/figure.pyf and then …"

### Scale bar appears wrong size after opening in PyFigures

Make sure `px_to_unit` (pixels per physical unit) is set correctly.  
Example: if 1 pixel = 0.065 µm, pass `px_to_unit=0.065`.  
You can check the current value with:
```
get_image_property("figure.pyf", [0], 0, "px_to_unit_conversion_factor")
```

### File not saved / changes not visible

All tools that modify a figure save the file immediately. Reopen (or reload) the
`.pyf` file in the PyFigures GUI to see changes.
