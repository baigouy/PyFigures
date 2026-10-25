"""“Show me how”: short guides that teach one operation in the running GUI.

An MCP client (or the command line, or Help → Show me how…) picks an
authored guide by its id; the GUI then highlights the real menus and controls
in a floating, closable bubble and the *user* performs the clicks. Showing a
guide never edits the figure.

Three modes stay distinct:

* **Do it**: the ordinary MCP tools edit the figure.
* **Show me how**: :func:`show` opens the guide in the running GUI.
* **Explain**: :func:`explain` returns the same authored steps as text, with no
  GUI needed.

This module has no Qt dependency. The guide registry lives here; the GUI side
(``pyfigures.gui.show_me_how``) builds the highlighted steps from it, and each
GUI window opens a small local mailbox that :func:`show`, :func:`status` and
:func:`close` write requests to::

    ~/.pyfigures/gui_sessions/<pid>_<token>/session.json     (written by the GUI)
    ~/.pyfigures/gui_sessions/<pid>_<token>/<id>.request.json  (written here)
    ~/.pyfigures/gui_sessions/<pid>_<token>/<id>.response.json (GUI's answer)

A request must carry the session's random token and is refused after 30 s;
it can only name a guide from the registry (never code, coordinates or
arbitrary menu paths).

Command line::

    python -m pyfigures.guides list
    python -m pyfigures.guides explain "crop an image"
    python -m pyfigures.guides show split_channels [--figure fig.pyf]
    python -m pyfigures.guides status
    python -m pyfigures.guides close
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
# Step kinds (the GUI turns each into one or more highlighted steps):
#   {"select": "image" | "channel_image"}      click a panel first
#   {"menu": [top, sub, ..., action]}           one highlighted step per level
#   {"context": "text"}                         right-click route (canvas highlighted)
#   {"dialog": "text"}                          what to do in the dialog that opened
# "done" names the result the GUI watches for (see gui/show_me_how.py):
#   split_created, scalebar_added, inset_added, lut_changed, crop_changed,
#   panel_added, dialog_closed, order_changed, layout_changed.

GUIDES: dict[str, dict] = {
    "split_channels": {
        "title": "Split channels (each channel + merge)",
        "summary": "Turn a multi-channel image into a row of single channels plus a merge.",
        "keywords": ["split", "channel", "channels", "separate", "merge row", "rgb"],
        "steps": [
            {"select": "channel_image",
             "text": "Click the multi-channel image you want to split. The guide does not "
                     "select or change it for you."},
            {"menu": ["Insert", "Stack views", "Channel split (each channel + merge)…"]},
            {"dialog": "Name the channels, choose their colours and keep <b>Add the merge</b> "
                       "checked if you want it. Click <b>Ok</b>. A new row is added; the "
                       "original panel stays."},
        ],
        "alternative": "Right-click the image → Split ▶ → Channel split (Gray mode) or "
                       "(Magenta/Green mode).",
        "done": "split_created",
        "mcp": "add_channel_split",
    },
    "add_scale_bars": {
        "title": "Add scale bars to every panel",
        "summary": "Add a calibrated scale bar to all image panels at once.",
        "keywords": ["scale bar", "scalebar", "scale", "bar", "micron", "µm", "um", "calibration"],
        "steps": [
            {"menu": ["Annotations", "Add scale bar to all panels…"]},
            {"dialog": "Enter the bar length (for example 10 µm) and choose the corner. Each "
                       "image uses its own pixel size (from its file, or set in its editor); "
                       "type one only for images that have none — an image without any gets "
                       "a bar in pixels (10 px). Click <b>Ok</b>."},
        ],
        "alternative": "One panel only: double-click it (Edit Image) and use its scale-bar "
                       "settings.",
        "done": "scalebar_added",
        "mcp": "set_scale_bar_all",
    },
    "zoom_inset": {
        "title": "Add a zoom inset (magnified detail)",
        "summary": "Box a region of a panel and show it magnified in a corner with leader lines.",
        "keywords": ["zoom", "inset", "magnify", "magnified", "callout", "detail", "enlarge region"],
        "steps": [
            {"select": "image", "text": "Click the panel that holds the detail you want to magnify."},
            {"menu": ["Annotations", "Add zoom callout to selected panel…"]},
            {"dialog": "Drag on the picture to draw the region (or type x, y, width, height in "
                       "image pixels), choose the corner, the inset size and the leader lines "
                       "(0 when they would hide data), then click <b>Ok</b>."},
        ],
        "alternative": "Double-click the panel → Annotations tab: draw a rectangle, then "
                       "<b>Rect ROI → Inset</b>.",
        "done": "inset_added",
        "mcp": "add_zoom_callout",
    },
    "reorder_panels": {
        "title": "Reorder panels or rows",
        "summary": "Move a panel inside its row, swap two panels, or move a whole row up or down.",
        "keywords": ["order", "reorder", "move", "rearrange", "swap", "exchange", "invert",
                     "reverse", "first", "last", "position", "sort", "row up", "row down"],
        "steps": [
            {"select": "image",
             "text": "Click the row once (the whole row is selected), then click the panel "
                     "to move (now only that panel is selected)."},
            {"context": "Press the <b>←</b> / <b>→</b> (left / right) arrow keys to move the "
                        "panel inside its row. With the whole row selected, <b>↑</b> / <b>↓</b> "
                        "(up / down) move the row. "
                        "Or drag the panel onto another one and choose <b>Swap</b>."},
        ],
        "alternative": "Drag a row onto another row and choose Swap to exchange two rows.",
        "done": "order_changed",
        "mcp": "reorder_children",
    },
    "stack_in_row": {
        "title": "Stack two images inside a row",
        "summary": "Put an image under another one of a row: A | B becomes A | (B / C).",
        "keywords": ["stack", "stacked", "stacking", "nest", "nested", "column in the row",
                     "under", "below", "on top of", "column inside"],
        "steps": [
            {"select": "image",
             "text": "Click the row once, then click the image to move (now only that image "
                     "is selected)."},
            {"context": "Drag it onto the image of the row it should go under, release, and "
                        "choose <b>Stack with it (column in the row)</b> in the menu. The two "
                        "become a column inside that row. To cancel, choose <b>Ignore</b> or "
                        "press Escape while the menu is open."},
        ],
        "alternative": "To row / To column in the same menu make a new top-level row or "
                       "column instead.",
        "done": "layout_changed",
        "mcp": "stack_with_image",
    },
    "edit_text": {
        "title": "Greek letters, µ, superscripts in a text on an image",
        "summary": "Write or edit an ordinary text on a panel, with µ, Greek letters, "
                   "superscripts or subscripts (not the panel letters).",
        "keywords": ["greek", "µ", "micro", "micron sign", "alpha", "beta", "superscript",
                     "subscript", "exponent", "co2", "edit text", "edit the text", "text on the image",
                     "existing text", "word bold"],
        "steps": [
            {"select": "image", "text": "Click the panel that holds (or will hold) the text."},
            {"context": "Double-click the panel: its editor opens. In the <b>Texts</b> tab click "
                        "<b>Add Text</b>, or double-click an existing text. In the <b>Edit text</b> "
                        "dialog select the characters and click <b>Superscript</b> or "
                        "<b>Subscript</b>, or pick µ / a Greek letter from the toolbar menu; "
                        "Bold and Italic work on the selection only. Click <b>Ok</b>, then "
                        "<b>Ok</b> in the editor."},
        ],
        "alternative": "Panel letters (a, b, c…) are not edited here: Annotations → panel "
                       "letters options.",
        "done": "dialog_closed",
        "mcp": "set_annotation_text",
    },
    "edit_roi": {
        "title": "Change an existing ROI (outline, fill, dashes, position)",
        "summary": "Recolour a box, ellipse, line or polygon already drawn on a panel, make its "
                   "outline thicker or dashed, remove its fill, or move / resize it.",
        "keywords": ["existing roi", "edit roi", "edit the roi", "outline", "thicker", "thinner",
                     "dashed", "dotted", "remove the fill", "remove fill", "no fill", "box colour",
                     "box color", "rectangle colour", "rectangle color", "change the rectangle",
                     "change the box", "change the ellipse", "change the circle", "move the box",
                     "resize the box", "roi colour", "roi color"],
        "steps": [
            {"select": "image", "text": "Click the panel that has the ROI."},
            {"context": "Double-click the panel: its editor opens on the <b>Annotations</b> tab. "
                        "Click the ROI on the image to select it. <b>Contour</b> and <b>Fill</b> "
                        "set its colours (<b>Reset</b> removes the fill), <b>Opacity</b> its "
                        "transparency, <b>Stroke Size</b> and <b>Type</b> its outline width and "
                        "dashes — they change the selected ROI only. Drag it to move it. Click "
                        "<b>Ok</b>."},
        ],
        "alternative": "Several ROIs look alike? Select the one you mean on the image first.",
        "done": "dialog_closed",
        "mcp": "set_roi_properties",
    },
    "edit_inset": {
        "title": "Change an existing inset (size, border)",
        "summary": "Resize an inset already on a panel, or change its border width and colour.",
        "keywords": ["existing inset", "edit inset", "edit the inset", "inset size", "inset border",
                     "resize inset", "resize the inset", "bigger inset", "smaller inset",
                     "inset colour", "inset color", "change the inset", "change inset"],
        "steps": [
            {"select": "image", "text": "Click the panel that has the inset."},
            {"context": "Double-click the panel: its editor opens. Click the inset to select it, "
                        "then double-click it: <b>Edit Inset</b> sets its size (percentage of "
                        "the panel width), border size and colour. Click <b>Ok</b>, then "
                        "<b>Ok</b> in the editor."},
        ],
        "alternative": "The corner is chosen when the inset is made: to move it to another "
                       "corner, select it in the editor, delete it, and add it again "
                       "(Annotations → Add zoom callout…).",
        "done": "dialog_closed",
        "mcp": "set_image_property",
    },
    "draw_roi": {
        "title": "Draw a rectangle, ellipse, polygon or line on an image",
        "summary": "Outline a region of a panel with a new box, ellipse, polygon or line, with "
                   "or without a filled interior.",
        "keywords": ["draw a rectangle", "draw a box", "draw an ellipse", "draw a circle",
                     "draw a polygon", "draw a line", "new roi", "add a roi", "add roi",
                     "ellipse instead", "irregular region", "polygon", "ellipse", "circle",
                     "mark a feature", "outline a region", "no filled interior", "hollow",
                     "rectangle with an outline"],
        "steps": [
            {"select": "image", "text": "Click the panel to draw on."},
            {"context": "Double-click the panel: its editor opens on the <b>Annotations</b> tab. "
                        "Click the shape button (square for a rectangle, <b>Ellipse</b>, "
                        "<b>Polygon</b>, <b>Line</b>…) and drag on the image; for a polygon click "
                        "each corner and double-click to close it. A new shape takes the current "
                        "settings: <b>Contour</b> is the outline colour, <b>Stroke Size</b> its "
                        "width, and <b>Fill</b> its interior; click <b>Reset</b> next to Fill for "
                        "an outline with no filled interior (it also removes the fill of a "
                        "selected shape). Click <b>Ok</b>."},
        ],
        "alternative": "To change a ROI that is already drawn, select it in the same editor.",
        "done": "dialog_closed",
        "mcp": "add_roi_rect",
    },
    "remove_inset": {
        "title": "Remove an inset but keep its rectangle",
        "summary": "Delete a magnified inset while the rectangle (ROI) that marks its region "
                   "stays on the original image.",
        "keywords": ["remove the inset", "remove an inset", "remove a magnified inset",
                     "delete the inset", "delete an inset", "remove inset", "delete inset",
                     "keep the rectangle", "leaving its rectangle", "keep its rectangle",
                     "keep the roi"],
        "steps": [
            {"select": "image", "text": "Click the panel that has the inset."},
            {"context": "Double-click the panel: its editor opens on the <b>Annotations</b> tab. "
                        "Click the inset (the magnified picture) to select it and press "
                        "<b>Delete</b>. The rectangle ROI is a separate object and stays on the "
                        "image. Click <b>Ok</b>."},
        ],
        "alternative": "Every inset of every panel at once (the rectangles stay): Annotations → "
                       "Remove → Remove all insets.",
        "done": "dialog_closed",
        "mcp": "remove_inset",
    },
    "scale_bar_units": {
        "title": "Change a scale bar's unit (µm → nm)",
        "summary": "Show a scale bar in nanometres (or another unit) instead of micrometres.",
        "keywords": ["nanometre", "nanometres", "nanometer", "nanometers", "nm", "unit",
                     "units", "micrometres to", "micrometers to", "scale bar legend",
                     "scale bar unit", "legend unit", "change the unit"],
        "steps": [
            {"select": "image", "text": "Click the panel that has the scale bar."},
            {"context": "Double-click the panel: its editor opens. In the <b>File Infos + "
                        "Scale</b> tab, set <b>Pixel to unit conversion factor</b> in the new unit "
                        "(nm per pixel = µm per pixel × 1000)."},
            {"context": "In the <b>Annotations</b> tab click the scale bar, then double-click it: "
                        "<b>Edit ScaleBar</b>. Set its size in the new unit (e.g. 500) and edit the "
                        "legend text to read the unit (e.g. 500 nm). Click <b>Ok</b>, then "
                        "<b>Ok</b> in the editor."},
        ],
        "alternative": "Every panel at once: Annotations → Add scale bar to all panels… with "
                       "the length typed in the new unit, once each image's pixel size is in "
                       "that unit.",
        "done": "dialog_closed",
        "mcp": "set_scale_bar",
    },
    "max_projection": {
        "title": "Show a Z stack as a maximum-intensity projection",
        "summary": "Display the maximum (or minimum, average) projection of a Z stack panel.",
        "keywords": ["maximum intensity projection", "max projection", "maximum projection",
                     "projection", "project", "z stack", "z-stack", "mip", "average projection"],
        "steps": [
            {"select": "image", "text": "Click the Z-stack panel."},
            {"context": "Double-click the panel: its editor opens. In the <b>File Infos + "
                        "Scale</b> tab, the <b>Projection</b> box sets <b>Max</b> (or Min / Avg) "
                        "and the Z range to include. Click <b>Ok</b>."},
        ],
        "alternative": "New Z stacks open as a max projection when View → Show new Z stacks as "
                       "max projection is checked; Insert → Stack views → Montage of frames "
                       "(time / Z)… shows several slices instead.",
        "done": "dialog_closed",
        "mcp": "configure_image",
    },
    "remap_images": {
        "title": "Reconnect missing images after moving their folder",
        "summary": "Point the figure at the new location of images that were moved or renamed.",
        "keywords": ["reconnect", "relink", "remap", "missing image", "missing images",
                     "moved", "moving its folder", "moved folder", "broken link", "broken links",
                     "new location", "file not found"],
        "steps": [
            {"menu": ["QC", "Remap image paths…"]},
            {"dialog": "Type the <b>Old path prefix</b> (the folder the images were in, e.g. "
                       "C:\\old\\data) and the <b>New path prefix</b> (where they are now, e.g. "
                       "D:\\new\\data). Click <b>Ok</b>: every missing image under the old "
                       "folder is reconnected."},
        ],
        "alternative": "QC → Check for changed source files… lists images that changed since the "
                       "figure was saved.",
        "done": "dialog_closed",
        "mcp": "remap_paths",
    },
    "arrowheads": {
        "title": "Point at a feature with an arrow or an arrowhead",
        "summary": "Add an arrow, or the larger head alone (as in papers), pointing at a feature.",
        "keywords": ["arrow", "arrowhead", "arrowheads", "arrow head", "point at", "pointing",
                     "pointer", "tip"],
        "steps": [
            {"select": "image", "text": "Click the panel that shows the feature."},
            {"menu": ["Annotations", "Add arrow pointing at a feature…"]},
            {"dialog": "In <b>Style</b> choose an arrow, a double arrow or <b>Arrowhead only "
                       "(larger head, no line)</b>. Type the tip position in image pixels and "
                       "the direction (Length does not apply to an arrowhead), or click "
                       "<b>Draw it with the mouse instead…</b>. Click <b>Ok</b>."},
        ],
        "alternative": "Double-click the panel → Annotations tab: pick the Arrow or the "
                       "Arrowhead tool and drag towards the feature, then Ok.",
        "done": "dialog_closed",
        "mcp": "add_arrow",
    },
    "text_style": {
        "title": "Change the font of labels, letters or scale-bar numbers",
        "summary": "Restyle a whole family of texts at once (font, size, colour, bold, italic).",
        "keywords": ["font", "text style", "bold", "italic", "font size", "text size",
                     "scale bar numbers", "scale bar legend", "labels font", "restyle"],
        "steps": [
            {"menu": ["Annotations", "Text style (letters, labels, scale bars…)…"]},
            {"dialog": "Choose which texts (panel letters, labels, scale-bar legends or all), "
                       "then tick <b>Font</b> or <b>Size</b>, or pick a colour, bold or italic. "
                       "Only what you tick or pick changes; the words stay. Click <b>Ok</b>."},
        ],
        "alternative": "Panel letters only: Annotations → Panel letters options. One text: "
                       "double-click its panel → Texts tab → double-click the text.",
        "done": "dialog_closed",
        "mcp": "restyle_texts",
    },
    "review_comments": {
        "title": "Get comments from co-authors (review)",
        "summary": "Export a review page others can comment on, then import their comments.",
        "keywords": ["review", "comment", "comments", "co-author", "coauthor", "feedback",
                     "annotate for review", "reviewer"],
        "steps": [
            {"menu": ["File", "Review comments", "Export for review…"]},
            {"dialog": "Give your e-mail if you want replies sent to you and save the HTML "
                       "page. Send it: reviewers open it in a browser, draw a box on a region "
                       "and comment it, or write a general comment, then save their copy."},
        ],
        "alternative": "When a reviewed copy comes back: File → Review comments → Import "
                       "review comments… shows each comment on its panel.",
        "done": "dialog_closed",
        "mcp": "export_review",
    },
    "set_lut": {
        "title": "Change channel colours (LUTs)",
        "summary": "Choose the colour of each channel (for example magenta and green).",
        "keywords": ["lut", "luts", "colour", "color", "colours", "colors", "magenta", "green",
                     "pseudocolour", "recolour", "recolor"],
        "steps": [
            {"select": "image", "text": "Click the image whose colours you want to change."},
            {"context": "<b>Right-click</b> the selected image, open <b>Appearance ▶</b> and "
                        "choose <b>Set LUT(s)</b>."},
            {"dialog": "Pick a colour for each channel and click <b>Ok</b>. For a channel "
                       "split, changing the merge also recolours the channel names."},
        ],
        "alternative": "Appearance ▶ → Reset LUT(s) goes back to the original colours.",
        "done": "lut_changed",
        "mcp": "set_lut",
    },
    "crop_image": {
        "title": "Crop or rotate a panel",
        "summary": "Trim pixels from the edges of a panel (for example burned-in text) or rotate it.",
        "keywords": ["crop", "trim", "cut", "rotate", "rotation", "edges", "remove text", "footer"],
        "steps": [
            {"select": "image", "text": "Click the panel you want to crop."},
            {"context": "<b>Double-click</b> the selected panel (or right-click → <b>Edit "
                        "Image</b>) to open the image editor."},
            {"dialog": "Open the <b>Rotate + Crop</b> tab, enter how many pixels to remove from "
                       "each side (or an angle), then click <b>Ok</b>."},
        ],
        "alternative": "Right-click a row → Crop & size ▶ to give all panels the same crop.",
        "done": "crop_changed",
        "mcp": "transform_image",
    },
    "panel_letters": {
        "title": "Panel letters (A, B, C…)",
        "summary": "Set the style and position of the automatic panel letters.",
        "keywords": ["letter", "letters", "lettering", "label panels", "a b c", "panel labels"],
        "steps": [
            {"menu": ["Annotations", "Panel letters (A, B, C…)…"]},
            {"dialog": "Choose the letter style, size and corner, then click <b>Ok</b>. "
                       "Automatic lettering is the checkbox in the toolbar."},
        ],
        "alternative": "Right-click a panel → Text & lettering ▶ → Change lettering parameters.",
        "done": "dialog_closed",
        "mcp": "add_corner_labels",
    },
    "add_data_plot": {
        "title": "Add a data plot from a CSV",
        "summary": "Make a box/bar/scatter plot panel (with statistics) from a CSV file.",
        "keywords": ["plot", "graph", "chart", "csv", "box plot", "bar plot", "statistics", "stats"],
        "steps": [
            {"menu": ["Insert", "Data plot from CSV…"]},
            {"dialog": "Pick the CSV, the plot type and the statistics options, then click "
                       "<b>Ok</b>. The plot is added as a new panel."},
        ],
        "alternative": "",
        "done": "panel_added",
        "mcp": "add_data_plot",
    },
    "channel_merge": {
        "title": "Merge single-channel images",
        "summary": "Overlay separate single-channel images into one coloured composite.",
        "keywords": ["merge", "overlay", "composite", "combine channels"],
        "steps": [
            {"menu": ["Insert", "Multi-channel merge…"]},
            {"dialog": "Choose the channel images and their colours, then click <b>Ok</b>."},
        ],
        "alternative": "",
        "done": "panel_added",
        "mcp": "add_channel_merge",
    },
    "journal_check": {
        "title": "Check a figure against a journal",
        "summary": "Check width, fonts, scale bars and labels against a journal's rules.",
        "keywords": ["journal", "compliance", "submission", "ready", "guidelines", "nature",
                     "science", "cell", "pnas", "check"],
        "steps": [
            {"menu": ["QC", "Check journal compliance…"]},
            {"dialog": "Choose the journal and column width and read the PASS/FAIL report."},
        ],
        "alternative": "QC → Apply journal guidelines… resizes and fixes fonts in one go.",
        "done": "dialog_closed",
        "mcp": "check_journal_compliance",
    },
    "apply_journal": {
        "title": "Resize a figure for a journal",
        "summary": "Resize to a journal column width and raise fonts to its minimum.",
        "keywords": ["resize", "width", "column", "journal", "apply guidelines", "double column",
                     "single column"],
        "steps": [
            {"menu": ["QC", "Apply journal guidelines…"]},
            {"dialog": "Choose the journal (or a style you imported) and the column, then click "
                       "<b>Ok</b>."},
        ],
        "alternative": "",
        "done": "dialog_closed",
        "mcp": "apply_journal_guidelines",
    },
    "check_resolution": {
        "title": "Check print resolution (DPI)",
        "summary": "See the printed DPI of each panel at the figure's size.",
        "keywords": ["dpi", "resolution", "pixelated", "print"],
        "steps": [
            {"menu": ["QC", "Check print resolution…"]},
            {"dialog": "Read the DPI of each panel; panels below the limit are listed first."},
        ],
        "alternative": "",
        "done": "dialog_closed",
        "mcp": "check_resolution",
    },
    "export_pptx": {
        "title": "Export to editable PowerPoint",
        "summary": "Save the figure as a PowerPoint file with editable text and playable movies.",
        "keywords": ["powerpoint", "pptx", "ppt", "slides", "editable", "export"],
        "steps": [
            {"menu": ["File", "Export As", "PowerPoint (editable)…"]},
            {"dialog": "Choose where to save the .pptx and click <b>Save</b>."},
        ],
        "alternative": "File → Export As → PDF / SVG / PNG / TIF for other formats.",
        "done": "dialog_closed",
        "mcp": "export_pptx",
    },
    "figure_caption": {
        "title": "Write the figure caption",
        "summary": "Write or edit the caption/legend stored beside the figure.",
        "keywords": ["caption", "legend", "figure legend", "text below"],
        "steps": [
            {"menu": ["File", "Figure caption / legend…"]},
            {"dialog": "Type the caption in the rich-text editor. To italicize or bold some "
                       "words, select them and click <b>Italic</b> or <b>Bold</b> in its "
                       "toolbar (Greek letters and superscripts are there too). The title is "
                       "optional. Click <b>Ok</b>: the caption is saved beside the .pyf, as "
                       "plain text and as Markdown keeping the formatting."},
        ],
        "alternative": "",
        "done": "dialog_closed",
        "mcp": "set_figure_caption",
    },
    "presubmission_review": {
        "title": "Run all pre-submission checks",
        "summary": "Run every check (journal, resolution, scale bars, integrity) in one report.",
        "keywords": ["review", "all checks", "pre-submission", "presubmission", "qc", "audit"],
        "steps": [
            {"menu": ["QC", "Pre-submission review (all checks)…"]},
            {"dialog": "Read the report; each problem says how to fix it."},
        ],
        "alternative": "",
        "done": "dialog_closed",
        "mcp": "figure_review_brief",
    },
    "colour_blind_preview": {
        "title": "Preview for colour-blind readers",
        "summary": "See the figure as readers with colour-vision deficiencies see it.",
        "keywords": ["colour blind", "color blind", "colorblind", "deuteranopia", "accessibility",
                     "cvd"],
        "steps": [
            {"menu": ["QC", "Preview figure under colour-blindness…"]},
            {"dialog": "Compare the simulated views; avoid red/green pairs that look alike."},
        ],
        "alternative": "QC → Show color-blind assistant suggests safe palettes.",
        "done": "dialog_closed",
        "mcp": "simulate_color_blindness",
    },
}

_WORD = re.compile(r"[a-zµ0-9]+")


def _norm(text: str) -> str:
    return " ".join(_WORD.findall(str(text).lower()))


def find_guide(query: str) -> tuple[str | None, list[str]]:
    """(guide_id, candidates) for an id or a free-text request ("show me how
    to crop"). guide_id is None when nothing matches or the request is
    ambiguous; candidates then lists the best matches."""
    q = str(query or "").strip()
    if q in GUIDES:
        return q, [q]
    key = q.lower().replace("-", "_").replace(" ", "_")
    if key in GUIDES:
        return key, [key]
    words = _norm(q)
    if not words:
        return None, []
    scores = {}
    for gid, g in GUIDES.items():
        score = 0
        for kw in g["keywords"]:
            k = _norm(kw)
            if k and re.search(r"\b" + re.escape(k) + r"\b", words):
                score += 2 if " " in k else 1
        for w in _norm(g["title"]).split():
            if len(w) > 3 and re.search(r"\b" + re.escape(w) + r"\b", words):
                score += 1
        if score:
            scores[gid] = score
    if not scores:
        return None, []
    ranked = sorted(scores, key=lambda g: -scores[g])
    best = scores[ranked[0]]
    tied = [g for g in ranked if scores[g] == best]
    return (ranked[0] if len(tied) == 1 else None), ranked[:4]


def step_texts(guide_id: str) -> list[str]:
    """The guide's steps as plain instructions (the same text the GUI shows)."""
    g = GUIDES[guide_id]
    out = []
    for s in g["steps"]:
        if "menu" in s:
            out.append("Choose " + " → ".join(s["menu"]) + ".")
        else:
            text = s.get("text") or s.get("context") or s.get("dialog") or ""
            out.append(re.sub(r"<[^>]+>", "", text))
    if g.get("alternative"):
        out.append("Alternative: " + re.sub(r"<[^>]+>", "", g["alternative"]))
    return out


def list_guides() -> list[dict]:
    return [{"id": gid, "title": g["title"], "summary": g["summary"],
             "do_it_tool": g.get("mcp", "")} for gid, g in GUIDES.items()]


def explain(query: str) -> dict:
    """Explain mode: the authored steps as text (no GUI needed)."""
    gid, cands = find_guide(query)
    if gid is None:
        return {"status": "unknown_operation" if not cands else "ambiguous",
                "candidates": cands, "available": list(GUIDES)}
    g = GUIDES[gid]
    return {"status": "explained", "guide": gid, "title": g["title"],
            "steps": step_texts(gid), "do_it_tool": g.get("mcp", ""),
            "operation_executed": False}


# ---------------------------------------------------------------------------
# Mailbox client (talks to the GUI windows)
# ---------------------------------------------------------------------------

def sessions_root() -> str:
    """Where GUI windows open their mailboxes (PYFIGURES_GUI_SESSIONS overrides)."""
    return (os.environ.get("PYFIGURES_GUI_SESSIONS")
            or os.path.join(os.path.expanduser("~"), ".pyfigures", "gui_sessions"))


def _pid_alive(pid: int) -> bool:
    try:
        import psutil
    except ImportError:          # cannot tell: trust the session file
        return True
    return psutil.pid_exists(int(pid))


def live_sessions() -> list[dict]:
    """Running GUI windows that accept guides, newest first. Folders of
    windows that are gone (crash) are removed."""
    root = sessions_root()
    out = []
    try:
        names = os.listdir(root)
    except OSError:
        return []
    for name in names:
        folder = os.path.join(root, name)
        path = os.path.join(folder, "session.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if not _pid_alive(data.get("pid", 0)):
            try:
                import shutil
                shutil.rmtree(folder, ignore_errors=True)
            except Exception:
                pass
            continue
        data["folder"] = folder
        out.append(data)
    out.sort(key=lambda d: -float(d.get("created", 0)))
    return out


def _pick_session(figure_path: str | None):
    sessions = live_sessions()
    if not sessions:
        return None, sessions
    if figure_path:
        want = os.path.normcase(os.path.abspath(figure_path))
        for s in sessions:
            fig = s.get("figure") or ""
            if fig and os.path.normcase(os.path.abspath(fig)) == want:
                return s, sessions
    return sessions[0], sessions


def _request(action: str, topic: str | None = None, figure_path: str | None = None,
             timeout: float = 5.0) -> dict:
    session, sessions = _pick_session(figure_path)
    if session is None:
        return {"status": "gui_unavailable", "operation_executed": False,
                "error": "No PyFigures window is open. Start the GUI (python -m pyfigures) "
                         "and ask again, or use explain mode for the steps as text."}
    rid = uuid.uuid4().hex
    folder = session["folder"]
    req = os.path.join(folder, rid + ".request.json")
    resp = os.path.join(folder, rid + ".response.json")
    payload = {"version": 1, "token": session["token"], "created": time.time(),
               "action": action, "topic": topic}
    from .atomic_io import write_atomic
    write_atomic(req, json.dumps(payload))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.exists(resp):
            try:
                with open(resp, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                time.sleep(0.05)
                continue
            try:
                os.remove(resp)
            except OSError:
                pass
            data.setdefault("window_figure", session.get("figure") or "")
            if len(sessions) > 1:
                data["windows_open"] = len(sessions)
            return data
        time.sleep(0.05)
    try:
        os.remove(req)
    except OSError:
        pass
    return {"status": "gui_unavailable", "operation_executed": False,
            "error": f"The PyFigures window did not answer within {timeout:g} s "
                     "(busy, or a modal dialog is waiting)."}


def show(query: str, figure_path: str | None = None) -> dict:
    """Show me how: open the guide in the running GUI. The user does the clicks."""
    gid, cands = find_guide(query)
    if gid is None:
        return {"status": "unknown_operation" if not cands else "ambiguous",
                "candidates": cands, "available": list(GUIDES), "operation_executed": False}
    result = _request("show", gid, figure_path)
    if result.get("status") == "gui_unavailable":
        result["steps_as_text"] = step_texts(gid)
    return result


def status(figure_path: str | None = None) -> dict:
    return _request("status", None, figure_path)


def close(figure_path: str | None = None) -> dict:
    return _request("close", None, figure_path)


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="python -m pyfigures.guides",
                                description="Show-me-how guides for the PyFigures GUI.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for name in ("explain", "show"):
        sp = sub.add_parser(name)
        sp.add_argument("operation")
        sp.add_argument("--figure", default=None)
    for name in ("status", "close"):
        sp = sub.add_parser(name)
        sp.add_argument("--figure", default=None)
    a = p.parse_args(argv)
    if a.cmd == "list":
        res = list_guides()
    elif a.cmd == "explain":
        res = explain(a.operation)
    elif a.cmd == "show":
        res = show(a.operation, a.figure)
    elif a.cmd == "status":
        res = status(a.figure)
    else:
        res = close(a.figure)
    print(json.dumps(res, indent=2, ensure_ascii=True))
    return 0 if not (isinstance(res, dict) and res.get("status") in
                     ("gui_unavailable", "error", "unknown_operation", "ambiguous")) else 1


if __name__ == "__main__":
    sys.exit(main())
