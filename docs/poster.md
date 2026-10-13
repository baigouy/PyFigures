# Poster / collage designer

PyFigures' main editor exists to pack scientific figure panels tightly and
precisely: images are trimmed, aligned and sized to exact physical
dimensions, with minimal wasted space. That is the wrong tool for a
**poster** or a **decorative collage / photo-album page**, where images
should be free to sit at an angle, overlap, and breathe on a page — not be
cropped or auto-packed. The poster designer is a second, separate tool
built for that job. It lives under `Tools > Poster / collage designer…`
(or `python -m pyfigures.poster`).

**Photo albums have their own designer**, `Tools > Photo album designer…`
(or `python -m pyfigures.album`): the same canvas and tools, but every
document is a photo book — front cover, two-page spreads, back cover (see
"Photo album designer" below). The poster designer cannot turn a poster
into a photo album, and each designer refuses to open the other's files.

## What it is (and isn't)

- It is a **free-placement canvas**: images are dragged anywhere on a fixed
  page and can be rotated to any angle. Nothing is auto-trimmed or
  auto-packed.
- Rotating an image **grows its bounding box instead of cropping it** — the
  whole image stays visible, tilted, rather than being clipped back to its
  original rectangle. This is the opposite of (and unrelated to) the main
  editor's rotation, which crops.
- It supports a **full-page background image** (e.g. a texture or backdrop
  photo): always covers the page edge-to-edge (no gaps) and is never rotated,
  but is **draggable to reposition/crop** and **scroll-wheel zoomable** to
  crop in tighter, like a draggable version of a CSS "cover" background.
  Click the empty page (with no image on top) to select it, drag to pan,
  scroll to zoom; *Reset background position* puts it back to centered/no-zoom.
- While dragging, edges/centers of the moving shape are compared against
  every other shape and the page; getting close to lining up shows a guide
  line and gently eases the shape onto it — like Figma/PowerPoint "smart
  guides", but the pull is graded rather than a hard grab: right at the edge
  of the catch radius it's barely noticeable, and only ramps up to an exact
  snap once you're already nearly on the line, so it assists without
  fighting free hand-placement. Hold **Alt** while dragging to switch it off
  entirely for that drag.
- It saves to its own file format, **`.pyfposter`**, completely separate
  from `.pyf`. The main editor's Open dialog never sees `.pyfposter` files,
  and the poster designer never *opens* a `.pyf` as an editable figure — the
  two tools don't share files, state, or classes, only the same install. The
  one bridge is one-directional: drop a `.pyf` onto the poster page (or pick
  one from *Add image…*) and it's flattened to a plain photo (see "Bringing
  in a finished figure" below) — from that point on it's just an image, with
  no ongoing link back to the source figure.
- A document isn't limited to one page: the **Pages** panel (see "Multiple
  pages" below) adds pages, covers and two-page spreads — saved as
  **`.pyfalbum`** instead of `.pyfposter` the moment it grows past one plain
  page. Every tool above (images, text, arrange, align/distribute, frames…)
  works exactly the same on any page, in the poster and the photo album
  designer alike.
- It isn't aimed at scientific precision (no scale bars, no journal-size
  presets, no per-panel scripting) — for that, use the main figure editor.
- Its toolbar deliberately looks and behaves like the main editor's: the same
  qtawesome icon set (tinted for light/dark theme the same way), the same
  zoom buttons/shortcuts (`Ctrl +`/`Ctrl -`/`Ctrl 0`, no percentage readout,
  same 10%-per-click step), and the same dark page-mat background — so
  switching between the two tools doesn't feel like switching apps.

## Step by step

**1. Open the tool.** `Tools > Poster / collage designer…` opens a
standalone window; the main figure editor stays exactly as it was.

**2. Pick a page size.** The toolbar's *Page* dropdown offers A0–A4
(portrait), defaulting to **A4**. *Zoom+* / *Zoom−* / reset (also `Ctrl +` /
`Ctrl -` / `Ctrl 0`) change on-screen magnification only, not the page size —
the same controls and shortcuts as the main editor's canvas.

**3. Add images.** *Add image…* drops a photo at the center of the page at
a sensible default size. Drag it to move; drag the small circular handle
above a selected image to rotate it around its own center. Rotating never
crops — the image's box grows to fit. A selected image also shows four
small square handles at its corners:

- Drag a corner to **resize** the box — the aspect ratio is always kept
  (same rule the main editor uses for its panels); there's no free/distorted
  stretch.
- Hold **Ctrl** while dragging a corner to **crop** instead: the box shrinks
  from that corner but the visible content keeps the same on-page scale —
  you're trimming the photo's edge away, not squeezing the whole image
  smaller (drag a cropped corner back out to reveal more of the photo again,
  up to its original size). The box's aspect ratio is kept here too — the
  box can end up smaller than the original, just never a different shape;
  cropping changes how much of the *photo* is visible, not the box's
  proportions.
- Once an image has been cropped, hold **Ctrl** and drag the image's *body*
  (not a corner) to slide the crop window over the photo — which part of it
  shows through the fixed box, same idea as the background's pan. This only
  does something on an axis that's actually been cropped; an image with no
  crop yet has nothing to pan into.

A selected image shows these as small text hints right under it — "Ctrl+drag
a corner to crop" always, plus "Ctrl+drag the image to reposition the crop"
once it actually has a crop to reposition — so neither behavior depends on
remembering this doc.

The opposite corner never moves during a resize or crop drag. You can also
drag image files (or a whole folder of them) straight from your file browser
onto the page — dropping a single image pops up a small menu asking **"Add
to page"** or **"Set as background"** (nothing happens until you choose);
dropping several at once pops up a menu at the drop point asking how to arrange them
(Scatter / Fan / Grid / choose a layout… / just add them centered), same
idea as the main editor's drag-and-drop menu. Dismissing either menu (Esc,
click elsewhere) adds nothing.

**3b. Add text.** *Add text…* drops a body-sized text box at the center of
the page and immediately opens a rich-text editor (the same one the main
editor uses for its own text annotations — bold/italic/underline, font,
foreground/background color, Greek letters). Double-click any text box later
to reopen that editor and keep editing it. A text box moves, rotates, and
resizes exactly like an image (drag a corner — the box, font included, scales
up or down together; there's no reflow/wrap, so short titles work best), but
has no frame/crop/photo underneath it.

The small dropdown arrow on *Add text…* offers Markdown-style size presets —
**Heading 1** (title-sized) down through **Heading 2**, **Heading 3**, **Body
text**, and **Caption** (smallest). Each is a target box height as a
*fraction of the page height*, not a fixed point size, so "Heading 1" on an
A0 poster comes out proportionally as big as "Heading 1" on an A4 page —
adapted to the document instead of something you have to eyeball and set by
hand each time. The rich-text editor also has a "Size preset" dropdown at
the top so you can bump an already-added text box between these levels
without retyping it.

**4. Set a background (optional).** *Set background…* fills the whole page
with an image (cropped to cover, never rotated); *Clear background* removes
it. The background is locked and ignored by drag/click hit-testing.

**5. Arrange.** Drag shapes near each other's edges/centers, or the page's
edges/center, to feel the guide lines gently ease you into place (the pull
is graded, not a hard grab — see above). Hold Alt to move freely without any
pull for that drag. *Bring to front* / *Send to back* change stacking order;
*Delete selected* removes the current image. The toolbar's *Scatter* / *Fan*
/ *Grid* buttons apply an automatic arrangement to every image on the page in
one click (see "Automatic arrangements" below) — a fast starting point you
can then hand-tweak by dragging. *Layout* opens a gallery of pre-designed
page layouts to fill instead (see "Layout gallery" below).

**5b. Align and distribute multiple shapes.** **Shift+click** several
images/text boxes to select them together (shown with a solid green outline
around each); Shift+click a selected one again to drop it back out.
Shift-clicking builds an ad hoc selection purely for the two toolbar buttons
below — it's separate from a layout group (the loose dash-dot outline from
*Layout*/*Sketch*), which always moves as one block; dragging a Shift-click
selection moves all of it together too, but nothing else about the shapes is
tied together.

- **Align** (needs 2+ selected) — left/right/top/bottom edges, or horizontal/
  vertical center, all using the *selection's own overall bounding box* as
  the target (e.g. "Align left" moves everyone's left edge onto the
  leftmost shape's left edge) — same idea as PowerPoint/Illustrator's align
  panel.
- **Distribute** (needs 3+ selected) — evenly spaces the selected shapes'
  centers horizontally or vertically between the two outermost ones, which
  stay put.

Clicking a shape without Shift (or clicking the empty page) drops back to a
plain single selection.

**6. Save your work.** *Save* / *Save As…* write a `.pyfposter` file (XML,
human-readable) so you can come back and keep editing — or a `.pyfalbum` if
the document has grown past one plain page (see below); which one is picked
automatically, based on the document, not something you choose by hand.

**7. Export.** *Export image / PDF…* renders the **current page only** to
PNG/JPEG/PDF/SVG at a chosen DPI. *Export whole document (PDF)…* instead
renders **every page** as one multi-page PDF (front cover through back
cover for an album) — that's the one to use for a document with more than
one page; it works on a plain one-page document too (a one-page "book").

For sending a photo album to a print shop or archiving/handing it off, see
**Print-ready export** and **Consolidation (source-data bundle)** below.

## Undo / Redo

Ctrl+Z undoes, Ctrl+Shift+Z or Ctrl+Y redoes — same as the main scientific-
figure editor, and the toolbar's Undo/Redo buttons grey out automatically
whenever there's nothing to undo/redo. It covers every kind of edit
uniformly: moving/resizing/rotating/cropping a shape, adding/deleting/
grouping, Align/Distribute, adding or removing a page, editing text — there's no separate list of "undoable" actions to keep
in sync as new edit kinds get added, because it works differently from a
typical per-action undo stack: each checkpoint is a full snapshot of the
whole document (every page, every shape) written to a private temp folder,
not a diff or a recorded command. Undo/redo just swaps in the previous/next
snapshot wholesale.

A drop-and-arrange gesture (several images added and auto-arranged at once)
still undoes/redoes as a single step, not one step per image — the several
primitive edits it performs internally are grouped into one checkpoint.

Undo history is private to one open document and reset by File > New or
Open — it isn't saved into the `.pyfposter`/`.pyfalbum` file, so reopening a
document always starts with a clean (empty) history, same as the main
editor.

## Multiple pages

A poster document starts as a single page. The **Pages** panel on the left
(dock — drag it out or hide it like any other Qt dock) is where you turn it
into a multi-page document instead:

- **+ Page** adds a page right after the current one — a dropdown offers
  **Spread** (two physical pages designed as *one continuous canvas*, so a
  photo or text box can freely cross the middle — shown as a light dashed
  "gutter" guide line purely as a heads-up for where the physical fold falls;
  it never constrains where you place things), **Front cover** / **Back
  cover** (a single physical page — same tools as any other page, there's no
  separate cover editor), or **Plain page** (another single page, no
  special role).
- **Duplicate** copies the current page (background + every shape,
  independently re-created — not a live/shared reference) right after it —
  a quick way to reuse a spread's layout as a starting point for the next one.
- **Delete** removes the current page (a document always keeps at least
  one — the button is a no-op on the last remaining page).
- **▲ Move up** / **▼ Move down** reorder pages.
- Clicking a page in the list switches to it, with a small thumbnail preview
  and a label like "2. Spread (420×297mm)".

A **Spread**'s width defaults to double a single page's width (e.g. 420mm for
an A4-based document) — the two-pages-side-by-side layout a real photobook
prints as — but nothing stops you from resizing it afterwards like any other
page. The moment a document has more than one page (or its one page is a
cover/spread), *Save*/*Save As…* switch from `.pyfposter` to `.pyfalbum`
automatically; loading either format back just works (`Open…` accepts both,
except photo albums, which open in the photo album designer).

## Photo album designer

A real photo album is more regimented than a multi-page poster: a front
cover, a back cover, and every page between them a pair (a spread), never a
lone single page. The **photo album designer** — `Tools > Photo album
designer…` in the figure editor, or `python -m pyfigures.album` — is a
separate window that enforces exactly that structure:

- Every document (at start and after *New*) is a blank album: a pinned
  front cover, one interior spread and a pinned back cover.
- **+ Page** only adds **Spreads**, just before the back cover; Duplicate/
  Delete/Move up/Move down are disabled while a cover page is selected — the
  covers stay put and every interior page stays a two-page spread.
- Albums are saved as `.pyfalbum`. *Open…* and *Build from recipe…* only
  take photo albums (recipes with `album: true`); a poster or a plain
  multi-page document is refused with a pointer to the poster designer, and
  the poster designer likewise refuses photo albums. There is no switch
  between the two in either window.
- Its tutorial is *Help > Photo Album Tutorial* in the figure editor (or the
  Tutorial button in its toolbar).
- In the standalone app it has its own launcher: **PyFigures Album.exe**
  next to PyFigures.exe on Windows, **PyFigures Album.app** next to
  PyFigures.app on macOS (it opens PyFigures.app in album mode, so keep the
  two side by side). `PyFigures --album` / `python -m pyfigures --album` do
  the same from a terminal (`--poster` opens the poster designer).

## Print-ready export

*Print-ready export…* is for sending a poster or photo album to an actual
print shop, as opposed to *Export image / PDF…* / *Export whole document
(PDF)…* (screen/proof-quality, always RGB). It first asks **current page**
or **whole document**, then a format:

- **TIFF** / **EPS** — raster, high-DPI, with a **CMYK** colour-mode option
  (many print workflows want CMYK). The conversion is a naive,
  non-colour-managed RGB→CMYK (no ICC profile) — fine for layout/proofing,
  not colour-critical print; for that, do the final conversion in a
  colour-managed tool with the printer's own ICC profile. EPS export needs
  no Ghostscript (Pillow writes a plain raster wrapped in PostScript
  commands; only *reading* an EPS back needs Ghostscript, which this tool
  never does).
- **PDF** / **SVG** — vector, always RGB (Qt has no CMYK writer for
  either); `color_mode` doesn't apply.

For the **whole document**, PDF writes one multi-page file (a spread
becomes one double-width PDF page, same as *Export whole document (PDF)…*).
TIFF/EPS/SVG have no standard multi-page container print software reliably
accepts, so those instead write to a **folder** you pick: one numbered file
per page (`page_01_cover_front.tif`, `page_02_spread.tif`, ...) plus a
`manifest.json`.

**A pasted-in `.pyf` figure gets re-rendered at full resolution for this.**
Normally, dropping a `.pyf` onto the page flattens it once at a fixed 300 DPI
(see "Bringing in a finished figure" below) — fine on screen, but if that
panel is later enlarged, or the print export's DPI is higher than that
flatten's own effective resolution, the cached copy becomes the sharpness
ceiling, not the export settings. Print-ready export checks this per image
and, if the cached flatten would be the bottleneck, transparently re-renders
that image fresh from its original `.pyf` at whatever DPI its actual on-page
size needs — so a chart pasted small and then stretched across a spread
comes out print-sharp, not upscaled. Skipped (no needless re-render) when
the cached flatten is already sharp enough; a re-render that fails for any
reason just falls back to the cached copy rather than aborting the export.
Never touches the document itself — the swap only exists for the duration
of the export.

## Consolidation: source-data bundle

*Export source-data bundle…* packages the whole document into one
self-contained folder — the poster/album equivalent of the main editor's
Source Data export, for archiving, handing a project off, or submitting
alongside a printed album. It saves the document first (the bundle is
always built from the file on disk), then writes:

- `<name>.pyfposter` / `.pyfalbum` — a **portable copy** whose every image
  and background path points at the copies below, so the bundle reopens
  standalone even if the original photos move or are deleted;
- `images/` — every page's background/image files, copied and renamed by
  page and shape index (`p02_s01__photo.jpg`, ...);
- `manifest.json` / `MANIFEST.txt` — a per-file index tying each copy back
  to its page/shape.

**Nested consolidation ("inception"):** if a photo was flattened from a
`.pyf` scientific figure (dropped in via drag-and-drop or *Add image…* — see
"Bringing in a finished figure" below), the poster only ever holds the
*flattened PNG*, not the original figure. Consolidating bundles that
original `.pyf`'s **own** Source Data — its panels, underlying CSVs/
images, caption, statistics — right alongside its flattened copy, as
`images/<name>_pyf_bundle/`. So a family photo album with a scientific
figure pasted into it (a chart on a poster page, say) still traces all the
way back to that figure's own data, not just the picture of it.

## Web export: a shareable photo book

*Export as web photo book…* is the one meant for sharing personal photos,
not print or archiving — it writes a **single, self-contained `.html`
file** with every page rendered to a JPEG and embedded right in the file as
a base64 data URI. There's nothing else to attach: email that one file,
drop it on a USB stick, put it on a phone, or upload it to any plain static
web host, and it opens straight in a browser with no PyFigures/Qt install
needed on the other end.

Opening it gives a small page-flip viewer: click either side of the page
(or the ❮ / ❯ buttons), use the ← / → arrow keys, swipe on a touch screen,
or jump straight to a page via the thumbnail dots along the bottom — each
page turn animates as an actual page flip (a CSS 3D rotation), not just a
slide or fade. A page counter and a full-screen button are included; it's
responsive down to phone width. Works for a plain one-page poster too (a
one-page "book"), and for a photo-album's covers/spreads exactly as laid
out (a spread is already one continuous image, so it turns as one page,
matching how it looks on the canvas).

This is a *viewing* export, not a print one — it asks for a DPI (150 by
default, plenty for any screen) and a JPEG quality, not the
resolution/CMYK options print-ready export has; use that instead for an
actual print shop. A `.pyf`-sourced photo is embedded at its existing
cached-flatten resolution here (no high-res re-render — screens don't need
print-grade sharpness).

## Bringing in a finished figure (.pyf)

A common real workflow: build a scientific figure in the main editor, then
drop it into a poster or a slide/photo-album page alongside other photos —
tilted, resized, maybe framed, next to a title or a background. Drag a
`.pyf` file (or several, or a folder containing some) onto the poster page,
or pick one from *Add image…*, and it's rendered once (at 300 DPI, via the
same headless renderer `render_poster`/`preview_poster` use elsewhere) to a
plain PNG in a dedicated cache folder (`~/.pyfigures/poster_pyf_renders/` —
never next to the source `.pyf`, so it doesn't litter whatever folder you
dragged it from) — from that moment on it **is** just a photo: draggable,
rotatable, resizable/croppable via the corner handles, frameable, groupable
with a layout, droppable onto a template slot, exactly like any other image
on the page. A single `.pyf` drop is added straight to the page — unlike a
plain photo, there's no "add vs. background" prompt, since a rendered
scientific figure is never meant as a backdrop. There's no live link back to
the source figure; if you revise the `.pyf` afterwards, drop it in again to
refresh (same `.pyf` always maps to the same cache file, so it's replaced,
not duplicated). Mixing `.pyf` files and regular photos in the same drop
works too — each is resolved to a plain image before anything else about the
drop is decided (arrange-as menu, slot fill…).

Rendering blocks the window for as long as the figure takes to render (a
modal "Rendering…" dialog makes that visible rather than looking like a
freeze). A `.pyf` that fails to render (e.g. it references missing image
files) is skipped with an error message rather than aborting the whole drop.

## Frames

Any image can carry a frame, set from the annotation editor when it's
selected (or via the MCP tools when driving the tool through the MCP server):

- **none** (default) — just the photo, no border.
- **simple** — a thin white border, like a printed photo.
- **polaroid** — a thick white border with a wider strip below for a
  caption. Rotating a framed image rotates the whole card around its own
  center — the way a physical print would — not just the picture inside it.

## Automatic arrangements

Three generative layouts are available from the toolbar (*Scatter* / *Fan* /
*Grid*, applying to every image on the page — text boxes such as a title are
never moved — each one undoable) and from Python/MCP
(`pyfigures/poster/poster_layouts.py`, which can also target a subset of
images):

- **Scatter** — "photos thrown on a table": each image gets a random
  position and a random tilt. Overlap is expected; that's the look. Pass a
  seed (MCP: `arrange_poster_scatter`) to reproduce a specific throw.
- **Fan** — images spread along a circular arc, like a hand of playing
  cards, each one rotated to point away from (or toward) the arc's center.
- **Grid** — rotation reset to 0, each image resized to fill its cell —
  the tidy baseline to fall back on. MCP: `arrange_poster_grid`.

**All three keep every image on the page by default.** If a result would
hang off the edge (a scatter's rotation pushing a corner past the margin, a
fan that doesn't naturally fit the page's proportions), the whole group is
uniformly shrunk and recentered as one piece — relative position, spacing
and tilt are preserved, only the size changes. A result that already lands
cleanly on the page is left completely untouched, so this never second-guesses
a "good" throw. Each layout function (and its MCP tool —
`arrange_poster_scatter` / `arrange_poster_arc` / `arrange_poster_grid`) takes
a `fit_to_page` flag, on by default, to turn this off and get the raw,
unclamped geometry (e.g. for a deliberate bleed off the page edge).

These are one-shot: running one again re-arranges from scratch, and nothing
stops you from dragging individual images afterwards to fix up the result by
hand.

## Layout gallery

Where Scatter/Fan/Grid are *generative* (parametric, can take any number of
images), the *Layout* toolbar button offers a small gallery of hand-designed
page layouts to fill instead — the poster module's version of picking a slide
layout in PowerPoint, and the counterpart to the main editor's Template
feature (`Template > Convert figure to template` + MCP `fill_template`,
which strip a real figure down to `@template@` slots and refill them one at a
time). Here the "slots" are a fixed catalog of shapes you fill in one call:

| Layout | Slots | Look |
|---|---|---|
| Single photo | 1 | full page |
| Diptych (side by side / stacked) | 2 | two even halves |
| Triptych | 3 | three even columns |
| Hero + filmstrip | 4 | one large photo on top, three small ones in a row below |
| Big photo + 3 side | 4 | one large photo on the left, three stacked small ones on the right |
| 2x2 grid | 4 | four even cells |
| Center + 4 corners | 5 | one large centered photo, four small ones in the corners |
| Magazine collage | 5 | varied sizes with a slight tilt, scrapbook feel |
| 3x3 grid | 9 | nine even cells |

There are two ways to reach it:

- The toolbar's **`Layout`** button (labelled, not just an icon, since it's
  the one entry point for this feature) opens a gallery dialog with a
  thumbnail preview of each layout's slot shapes; layouts whose slot count
  matches how many photos are currently on the page are listed first.
- Dropping **several image files at once** from the file browser includes a
  **"Choose a layout… (gallery)"** option in the drop menu, alongside
  Scatter/Fan/Grid — pick it and the gallery opens scoped to just the photos
  you dropped.

Whichever way you get there, applying a layout drops every targeted photo
into a slot, in page order — each resized (aspect ratio preserved, never
stretched or cropped) to fit inside its slot and centered there. With fewer
photos than the layout has slots, only the first slots get filled. With
**more** photos than slots, the layout repeats in horizontal bands stacked
down the page — enough bands to place every photo, the same slot pattern
shrunk to fit each band — so e.g. a 4-slot 2x2 grid with 9 photos gives you
three bands of (up to) four, continuing the pattern rather than leaving the
rest wherever they were. The last band may be partially filled if the count
isn't an exact multiple (MCP/CLI: pass `repeat=False` / `--no-repeat` to get
the old "only fill the first slots" behaviour instead). Like the automatic
arrangements, this is one-shot and fully hand-tweakable afterwards.

By default the images placed by one layout call are **grouped**: dragging any
one of them moves the whole composition together (shown while selected as a
loose orange dash-dot outline around the group, inside which the usual blue
selection outline marks the specific image you clicked). There's no
auto-alignment or repacking — each image keeps its own size/rotation
independently, and fill_template on a grouped slot keeps the group; only the
shared *position* moves as one. Click **Ungroup** (toolbar) to break a
selected group apart so its photos move independently again — sizes,
positions and rotations are unaffected. Pass `group=False` (MCP) /
`--no-group` (CLI) to `apply_poster_layout`/`sketch_poster_layout` to skip
grouping from the start.

MCP: `list_poster_layouts` (names/descriptions/slot counts) and
`apply_poster_layout(poster_path, layout_name, indices, margin_mm)` — so an
MCP client can compose a whole page from a folder of photos by picking a
layout name that matches the photo count. The catalog itself lives in
`pyfigures/poster/poster_templates.py` (`LAYOUTS`, `list_layouts`,
`apply_layout`) if you want to see or extend the slot definitions.

## Sketch a layout first, fill it in later

`apply_poster_layout` above needs the photos already on the page. To design
the page *before* you've picked which photo goes where — the poster module's
counterpart to the main editor's `Template > Convert figure to template` +
`fill_template` workflow — open the toolbar's **`Layout`** gallery and check
**"Sketch as empty slots (no photos yet — fill them in later)"** before
picking a layout. This adds the layout's slots as empty placeholders: dashed
grey boxes with a `+`, no photo yet, same size and position the real layout
would use. They're normal shapes — draggable, resizable by re-picking a
layout, deletable — just unfilled.

Fill a slot by **dragging a single image file straight onto it**: dropping
on top of an empty slot fills that one slot in place (no popup — unambiguous)
and fits the photo inside it (aspect ratio preserved, centered, never
stretched); the slot's box may shrink slightly if the photo's aspect ratio
doesn't match. Drop **several images at once** anywhere on a page that has
empty slots and the drop menu gains a **"Fill N empty template slots in
order"** choice, filling them z-order and adding any extra photos centered
if there are more photos than slots.

MCP/CLI: `sketch_poster_layout(poster_path, layout_name, margin_mm)` creates
the empty slots; `fill_poster_template_slot(poster_path, index, image_path)`
fills one by index (see `list_poster_images`'s `is_template` field to find
which ones are still empty). This lets an MCP client lay a page out first
and decide/receive which photo goes where afterwards, one call per slot —
just like looping `fill_template` over a main-editor template.

## MCP tools

Everything above is also exposed as MCP tools on PyFigures' existing MCP
server (see [docs/MCP_SERVER.md](MCP_SERVER.md) for setup) — so an MCP
client can compose a whole poster or photo-album page from a folder of
photos: `create_poster` (or `create_album`), `add_poster_image` (position/size/rotation/frame/
caption), `add_poster_text` (a title/caption text box, sized via the same
h1/h2/h3/body/caption `style` presets as the GUI — `list_poster_images`
returns both images and text boxes, told apart by their `kind` field),
`set_poster_background` / `clear_poster_background`,
`list_poster_images`, `set_poster_image_frame`, `remove_poster_image`,
`arrange_poster_scatter` / `arrange_poster_arc` / `arrange_poster_grid`,
`list_poster_layouts` / `apply_poster_layout`, `sketch_poster_layout` /
`fill_poster_template_slot`, `ungroup_poster_images`, and `render_poster` /
`preview_poster` to produce or preview the final image.
These tools only ever touch `.pyfposter`/`.pyfalbum` files — never `.pyf` —
and each runs the same offscreen-Qt-subprocess pattern as figure rendering,
so a Qt crash can't take the MCP server down.

**Photo albums (multiple pages)** get their own small set of tools:
`add_poster_page(poster_path, kind, width_mm, height_mm, index)` (kind is
"spread"/"cover_front"/"cover_back"/"single" — see "Multiple pages" above) turns any document into a multi-page album; `list_poster_pages`
inventories every page (index/kind/size/shape_count/has_background);
`remove_poster_page` / `duplicate_poster_page` / `move_poster_page` /
`set_poster_page_kind` manage them. Every other poster tool above accepts an
optional `page` argument (0-based) to target a page other than the first —
omit it for a plain single-page poster. `render_poster_album(poster_path,
out_path, dpi)` renders every page as one multi-page PDF (a spread becomes
one double-width PDF page); `render_poster`/`preview_poster` still render
just one page (add `page=N` to pick which).

`create_album(album_path)` creates a new **photo album**
(`.pyfalbum`, the photo album designer's document — see "Photo album
designer" above): a pinned front cover, one spread and a pinned back cover,
and `add_poster_page` then inserts spreads between the covers. Anything that
would break the book — removing, duplicating or moving a cover, adding a
non-spread page, or re-kinding a cover / an interior spread — is refused
with an `ERROR:` explaining why. A photo album is only ever created as one
(this, or a recipe with `album: true`); there is no tool to turn an
existing poster into an album or back.

Without `page=`, a tool works on page 0; `add_poster_page` without `index`
appends at the end (just before the back cover in album mode).
`add_poster_image` / `fill_poster_template_slot` also take a `.pyf` figure:
it's flattened exactly like a GUI drop and remembered for the source-data
bundle. `list_poster_images` marks images whose file can no longer be found
(`"missing": true`), and render/export results list them under
`missing_files` (they render as grey boxes).

**Print-ready export** (see above): `export_poster_print_ready(poster_path,
out_path, format, color_mode, dpi, page)` for one page, or
`export_poster_album_print_ready(poster_path, out_path, format, color_mode,
dpi)` for the whole document. `format` is `tiff`/`eps` (raster, `color_mode`
`cmyk`/`rgb` applies) or `pdf`/`svg` (vector, always RGB). For the whole
document, `pdf` writes one file; `tiff`/`eps`/`svg` write a folder (one file
per page + `manifest.json`) since none of those have a standard multi-page
container.

**Consolidation** (see above): `export_poster_source_data(poster_path,
out_dir, dpi)` bundles the whole document into `out_dir` — a portable copy
plus every image/background file, copied and renamed by page. Any photo
flattened from a `.pyf` figure gets that figure's own Source Data bundle
nested alongside it (`images/<name>_pyf_bundle/`, built via the existing
export_source_data) — a bundle inside a bundle, so a figure pasted into a
poster stays traceable to its own panels/scripts/CSVs. Returns JSON
including `nested_pyf_bundles`, the count of figures consolidated this way.

**Web export** (see above): `export_poster_web(poster_path, out_path, dpi,
quality)` writes one self-contained `.html` photo-book file — every page
embedded as a base64 JPEG, page-flip viewer built in, nothing else to
attach. `dpi` (default 150) and `quality` (JPEG, default 85) control the
embedded image size/sharpness; this is a viewing export, not print — see
`export_poster_album_print_ready` for that. Returns JSON with the output
path and page count.

## Building a poster or album from a recipe

A YAML (or JSON) file can describe the whole document — pages, backgrounds,
photos (files or glob patterns, in order), how each page's photos are
arranged, and text boxes — and build it in one go, which is handy for an
album rebuilt whenever new photos arrive. Paths are relative to the recipe.

```yaml
output: trip/iceland.pyfalbum     # .pyfposter for a single plain page
page: A4                          # A4..A0, or {width_mm: 300, height_mm: 300}
album: true                       # front cover + spreads + back cover
render: trip/iceland.pdf          # optional: .pdf = every page; .png/.jpg/.tif/.svg = page 1
render_dpi: 300
web: trip/iceland.html            # optional: the self-contained HTML photo book
front_cover:
  background: cover.jpg           # or {image: cover.jpg, zoom: 1.2, pan_x: 0.3, pan_y: 0.5}
  text: [{html: "<b>Iceland 2026</b>", style: h1, x_mm: 20, y_mm: 30}]
spreads:
  - images: ["day1/*.jpg"]
    arrange: {grid: {columns: 3}}           # grid | scatter | fan | none, or {layout: name}
  - images:
      - {image: lagoon.jpg, frame: polaroid, caption: Blue Lagoon}
      - geyser.jpg
      - Figure2.pyf                         # a scientific figure, flattened
    arrange: {layout: hero_with_strip}
    text: "a plain caption"
back_cover:
  text: [{html: "<i>the end</i>", style: caption}]
```

Without `album: true`, use `pages: [...]` (each page may set `kind`), or put a
single page's `background` / `images` / `arrange` / `text` at the top level.
Image entries take `frame`, `caption`, `x_mm`/`y_mm`, `width_mm`/`height_mm`
(one side keeps the photo's aspect ratio) and `theta`; text entries take
`html`, `style` (h1/h2/h3/body/caption), `x_mm`/`y_mm`, `theta`, `width_mm`.
Arrangements never move the text boxes. Unknown keys, missing files,
unreadable images and empty globs are reported before anything is written.

Three ways to run it — same recipe, same result:

- GUI: **Build from recipe…** on the toolbar (opens the result);
- command line: `python -m pyfigures.poster.poster_headless build recipe.yaml`;
- MCP / AI: `build_poster_from_recipe("recipe.yaml")`.

## Saving, moving and sharing safely

- **Unsaved changes are never lost silently**: the title shows `*` while the
  document differs from the file, and New / Open / Build from recipe /
  closing the window ask Save / Discard / Cancel first. Undoing back to the
  saved state clears the `*`; a plain click (selecting) doesn't set it.
- **Saving is atomic**: the file is written next to the target and renamed
  over it, so a crash or full disk mid-save leaves the previous file intact.
- **Moved folders still open**: each image/background is stored with its
  absolute path *and* its path relative to the document. If the absolute
  one no longer exists (folder moved, copied to another computer, a
  source-data bundle unzipped elsewhere), the relative one is used. Files
  that really are gone are listed when the document opens.
- A poster saved as `.pyfposter` that later gains pages is saved next to it
  as `.pyfalbum` (same name) — a `.pyfposter` holds exactly one plain page.
- Unreadable or corrupt image files are refused with a message (they used to
  be added as grey boxes); in a multi-file drop they're skipped and listed.
- Cancelling the export DPI question cancels the export.

## Things worth knowing

- Units inside a poster are millimetres; page presets match ISO A-sizes.
- The `.pyfposter` XML format was written from scratch for this tool (see
  "Where the code lives" below) rather than reusing the main editor's
  reflective XML serializer — this keeps the two formats structurally
  independent, so a bug or future change in one can't leak into the other.
- Standard photo formats (PNG/JPEG/TIFF/BMP) are supported; this tool does
  not handle the scientific multi-channel/LUT image types the main editor
  does — it's for photos and finished raster art, not raw acquisitions.
- Export DPI, page size and file format are independent choices — nothing
  here is tied to journal column-width presets.
- Per-image crop (Ctrl+drag a corner handle) is a GUI-only interaction for
  now — the crop fractions round-trip through `.pyfposter` and show up in
  `list_poster_images`, but there's no MCP tool to set them directly yet.
- Editing a text box's wording is GUI-only too (double-click it) — from the
  MCP side, changing the words means removing it (`remove_poster_image`,
  which works by index for any shape) and adding a new one.

## Where the code lives

Everything is under `pyfigures/poster/`, fully separate from the main
editor (`pyfigures/gui/ezfig.py`, `pyfigures/gui/pfgui.py`):

- `poster_shapes.py` — `PosterImage` (grow-to-fit rotation, frame/caption
  drawing, corner resize/crop geometry, `source_pyf` — the original figure
  path if this image was flattened from one, used only by consolidation),
  `PosterBackground`, `PosterText`, and `PosterPage` (one page's
  width/height/kind/shapes/background — a document is `PosterCanvas.pages`,
  a plain list of these).
- `poster_align.py` — pure-function smart-guide snapping, independent of
  the main editor's tight-packing code in
  `batoolset.figure.alignment`.
- `poster_layouts.py` — pure functions (`scatter_layout` / `arc_layout` /
  `grid_layout`) that reposition/rotate a list of `PosterImage`s in place;
  used by both the toolbar buttons and `poster_headless.py`.
- `poster_templates.py` — the layout gallery: `LAYOUTS` (the slot catalog),
  `list_layouts`, `apply_layout`. Same pure-function, Qt-free shape as
  `poster_layouts.py`.
- `poster_layout_dialog.py` — `LayoutGalleryDialog`, the Qt picker with
  thumbnail previews (and the "sketch as empty slots" checkbox) that the
  toolbar's *Layout* button opens.
- `poster_canvas.py` — `PosterCanvas`, the drawing/drag surface. Exposes
  `shapes_to_draw` / `get_dpi()` / `save()` / `update_size()` so it looks
  like a drop-in peer of the main editor's panel class for anything that
  wants to export it, without actually sharing code with it.
  `page_width_mm`/`page_height_mm`/`shapes_to_draw`/`background` are
  properties proxying to `self.pages[self.current_page_index]` — every
  other method (mouse handling, painting, align/distribute…) only ever
  touches those properties, so it works unchanged whether the document has
  one page or many; `add_page`/`remove_page`/`duplicate_page`/`move_page`/
  `goto_page` manage the page list, `export_album_pdf` renders every page as
  one multi-page PDF. `album_mode` (set by `new_document(album=True)`, a
  recipe or loading a photo album — never toggled on an existing document)
  adds the strict book-structure enforcement (pinned front/back cover, interior pages forced
  to `'spread'`) on top of that same page list — `add_page`/`remove_page`/
  `move_page` all check `self.album_mode` themselves, so nothing else needs
  to know it exists. `export_print_ready`/`_export_raster_print_page`/
  `export_album_print_ready` add print-ready TIFF/EPS (optionally CMYK via
  Pillow, no ICC profile) and PDF/SVG export, one page or the whole
  document; `_high_res_pyf_images` (a context manager, wrapping both of
  those) transparently re-renders any `source_pyf`-backed image at a
  resolution matching its actual on-page size before the export runs,
  swapping it back afterward, so a pasted-in figure isn't capped at its
  cached flatten's resolution. Also `_render_pyf_to_png`/
  `_render_pyf_subprocess` — the one bridge to `.pyf`, via
  `pyfigures.gui.render_headless` in a subprocess, never an in-process
  import of `pfgui`/`ezfig.py`. `_push_undo_checkpoint`/`undo`/`redo`/
  `_restore_snapshot`/`_batch_edit` are the whole-document-snapshot
  undo/redo (each checkpoint is a `save_album()` write into a private
  `tempfile.TemporaryDirectory`, restored via `load_album()`) — called from
  every content-mutating method plus `mouseReleaseEvent` (after a real
  drag) and wrapped around multi-step gestures (`_offer_drop_layout`) via
  `_batch_edit()` so they undo as one step; the `undo_redo_changed` Signal
  lets a window keep its Undo/Redo buttons' enabled state in sync.
  `export_album_web` renders every page to an in-memory JPEG (via
  `QBuffer`, base64-encoded) and hands them to `poster_web_export.
  build_album_html` for the self-contained flip-book HTML export.
- `poster_window.py` — `PosterWindow`, the standalone toolbar/window
  (`album=True` makes it the photo album designer, see
  `_refuse_other_designers_file`), plus the **Pages** dock
  (`_build_page_dock` and friends) for multi-page documents, and the
  Undo/Redo toolbar actions (`_update_undo_redo_buttons`, connected to
  `canvas.undo_redo_changed`).
- `serialization.py` — `.pyfposter` (one page, root `<PosterDocument>`) and
  `.pyfalbum` (many pages, root `<PosterAlbum album_mode="0|1"
  current_page_index="N">`, each a `<Page kind=...>` wrapping the same
  `<Background>`/`<Image>`/`<Text>` elements, `<Image>` also carrying
  `source_pyf` when set) XML read/write; `sniff_root_tag` lets
  `PosterCanvas.load()` tell them apart regardless of the file's actual
  extension.
- `poster_source_data.py` — `export_poster_source_data(canvas, poster_path,
  out_dir, dpi)`, the consolidation bundle: copies every page's
  background/image files into `out_dir/images`, writes a portable document
  copy pointing at those copies, and — the one place anything in this
  package reaches outside it — calls `pyfigures.mcp_server.export_source_data`
  (itself Qt-free) to nest a `.pyf`'s own Source Data bundle alongside any
  image whose `source_pyf` is set.
- `poster_web_export.py` — `build_album_html(pages_data, title)`, the pure
  string-template code (no Qt) for the self-contained flip-book HTML;
  `PosterCanvas.export_album_web()` does the actual page rendering (one
  JPEG per page via `QBuffer`, base64-encoded) and hands the resulting list
  of data URIs to this module.
- `poster_headless.py` — CLI (`python -m pyfigures.poster.poster_headless
  ...`) that edits/renders a `.pyfposter`/`.pyfalbum` off-screen, one
  subcommand per edit (most accept `--page N` to target one page of a
  multi-page document); this is what the MCP tools shell out to (mirrors
  `pyfigures/gui/render_headless.py` for `.pyf`).

The only changes outside `pyfigures/poster/` are a single additive menu
entry — `Tools > Poster / collage designer…` in `pyfigures/gui/pfgui.py`
(`EZFIG_GUI.open_poster_designer`), which lazily imports and shows a
`PosterWindow` — and the poster MCP tools appended to the end of
`pyfigures/mcp_server.py` (a separate section, sharing no code with the
`.pyf` tools above it in that file, with one deliberate exception:
`export_poster_source_data` calls that file's own `export_source_data` to
nest a `.pyf`'s Source Data bundle inside a poster's, see
`poster_source_data.py` above).
