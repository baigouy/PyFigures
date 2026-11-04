"""Build the documentation's example gallery (docs/examples/).

For every example below: write its recipe, build the figure (or poster) from
it with PyFigures, render it to PNG, and write its page. Then write the
gallery index. The sample data are scikit-image's public sample images (see
DATA_CREDITS) and a small simulated CSV, saved in docs/examples/data/.

Run it whenever PyFigures' rendering changes, and commit the result (Read the
Docs cannot run Qt, so the pictures are pre-rendered):

    python docs/examples/build_examples.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import textwrap

os.environ.setdefault("QT_API", "pyqt6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "https://github.com/baigouy/PyFigures"
DATA = os.path.join(HERE, "data")

DATA_CREDITS = (
    "Sample images from [scikit-image](https://scikit-image.org/docs/stable/api/skimage.data.html): "
    "`human_mitosis` (nuclei, Moffat et al., Cell 2006), `cells3d` (membrane and nuclei, Allen "
    "Institute for Cell Science), `protein_transport` (time-lapse, Boisvert et al.), `skin` "
    "(H&E-stained skin). The CSV data are simulated.")


# ---------------------------------------------------------------------------
# sample data
# ---------------------------------------------------------------------------
def make_data():
    import numpy as np
    import tifffile
    from PIL import Image
    from skimage import data
    os.makedirs(DATA, exist_ok=True)
    Image.fromarray(data.human_mitosis()).save(os.path.join(DATA, "mitosis.png"))
    cells = data.cells3d()                                   # z, c, y, x (uint16)
    tifffile.imwrite(os.path.join(DATA, "membrane.tif"), cells[:, 0].max(axis=0))
    tifffile.imwrite(os.path.join(DATA, "nuclei.tif"), cells[:, 1].max(axis=0))
    movie = data.protein_transport()[:, 1]                   # t, y, x (uint8)
    tifffile.imwrite(os.path.join(DATA, "transport.tif"), movie, metadata={"axes": "TYX"})
    Image.fromarray(data.skin()).save(os.path.join(DATA, "skin.jpg"), quality=92)
    rng = np.random.default_rng(7)
    groups = {"WT": rng.normal(42, 6, 12), "KO": rng.normal(27, 7, 12), "Rescue": rng.normal(39, 6, 11)}
    with open(os.path.join(DATA, "counts.csv"), "w", encoding="utf-8") as f:
        f.write(",".join(groups) + "\n")
        for i in range(12):
            f.write(",".join(f"{v[i]:.1f}" if i < len(v) else "" for v in groups.values()) + "\n")


# ---------------------------------------------------------------------------
# the examples (recipes are relative to docs/examples/<name>/)
# ---------------------------------------------------------------------------
EXAMPLES = [
    dict(name="basic", title="Micrographs with scale bars and letters",
         about="Two crops of the same image side by side, lettered A and B, each with a scale bar, "
               "sized for a Nature single column.",
         recipe="""
            output: figure.pyf
            journal: nature
            column: single
            defaults:
              px_to_unit: 0.2                  # µm per pixel
              scale_bar: {units: 10, unit: "µm"}
            rows:
              - - {image: ../data/mitosis.png, crop: {right: 256}}
                - {image: ../data/mitosis.png, crop: {left: 256}, lut: magenta}
            """),
    dict(name="channels", title="Channel split and merge",
         about="Two channels shown separately in their own colours, then merged, with names on the "
               "panels and one scale bar.",
         recipe="""
            output: figure.pyf
            width_mm: 180
            rows:
              - - split: [../data/membrane.tif, ../data/nuclei.tif]
                  names: [Membrane, Nuclei]
                  colors: [green, magenta]
                  merge: true
                  px_to_unit: 0.29
                  scale_bar: {units: 20, unit: "µm"}
            """),
    dict(name="annotations", title="Arrows, regions and text",
         about="Arrows whose tips stay exactly on the cells they point at, outlined regions, and "
               "text in the corners.",
         recipe="""
            output: figure.pyf
            width_mm: 89
            rows:
              - - image: ../data/mitosis.png
                  crop: {left: 100, right: 156, top: 150, bottom: 106}
                  arrows:                      # (x, y) in the image's own pixels
                    - {at: [334, 271], from: w, color: yellow}
                    - {at: [187, 316], from: nw, color: cyan}
                  rois:
                    - {rect: [206, 268, 34, 34], color: "#ff4040", stroke: 2}
                  text: ["Mitosis", {text: "n = 3", placement: bottom right}]
            """),
    dict(name="zoom", title="Zoom callout",
         about="A region of a large histology image magnified in a corner, with the box and the "
               "leader lines drawn automatically.",
         recipe="""
            output: figure.pyf
            width_mm: 120
            rows:
              - - image: ../data/skin.jpg
                  zoom: {box: [700, 380, 160, 120], corner: bottom right, size: 0.42}
            """),
    dict(name="timelapse", title="Time-lapse montage with time stamps",
         about="Five frames of a movie in a row, each stamped with its time.",
         recipe="""
            output: figure.pyf
            width_mm: 180
            rows:
              - - montage: ../data/transport.tif
                  axis: t
                  frames: "0:15:3"
                  interval: 2
                  unit: min
                  stamps: true
            """),
    dict(name="plot", title="Image and data plot with statistics",
         about="A micrograph next to a box plot made from a CSV file. The statistical test is "
               "chosen automatically (here ANOVA with Tukey's post-hoc test), the significance "
               "brackets are drawn, and every p-value is saved with the figure.",
         recipe="""
            output: figure.pyf
            width_mm: 140
            rows:
              - - {image: ../data/nuclei.tif, lut: magenta, px_to_unit: 0.29,
                   scale_bar: {units: 20, unit: "µm"}}
                - {plot: ../data/counts.csv, kind: box, ylabel: "cells / field", title: "Rescue"}
            """),
    dict(name="latex", title="LaTeX: maths in labels and equation panels",
         about="Labels can contain LaTeX maths between dollars, and an equation can be a panel of "
               "its own (here a row of its own, so it keeps a modest height). Both are vector in "
               "every export. Here the equation uses Matplotlib's built-in maths; with "
               "`engine: latex` it is compiled by LaTeX itself (any environment, any package).",
         recipe="""
            output: figure.pyf
            width_mm: 150
            rows:
              - - image: ../data/membrane.tif
                  lut: green
                  text: ['$\\Delta F/F_0$ at $t = 12\\,\\mathrm{min}$']
                - image: ../data/nuclei.tif
                  lut: magenta
                  text: ['$D = 0.12\\,\\mu\\mathrm{m}^2\\,\\mathrm{s}^{-1}$']
              - - equation: '\\frac{\\Delta F}{F_0} = \\frac{F - F_0}{F_0}, \\qquad D = \\frac{\\langle \\Delta r^2 \\rangle}{4\\,\\Delta t}, \\qquad \\tau_{1/2} = \\frac{\\ln 2}{k_\\mathrm{off}}'
                  font_size: 12
            """),
    dict(name="poster", title="A poster with a figure on it",
         kind="poster",
         about="A poster page with a title, a scientific figure dropped in from its `.pyf` file "
               "(kept vector in PDF/SVG exports, with editable text) and a photo.",
         recipe="""
            output: poster.pyfposter
            page: A4
            render: poster.png
            render_dpi: 100
            images:
              - {image: ../basic/figure.pyf, x_mm: 15, y_mm: 32, width_mm: 180}
              - {image: ../data/skin.jpg, x_mm: 15, y_mm: 218, width_mm: 90}
            text:
              - {html: "<b>Cell division in human cells</b>", style: h1, x_mm: 15, y_mm: 12}
              - {html: "Nuclei imaged at 0.2 µm per pixel.<br>Left: H&amp;E-stained skin.",
                 style: body, x_mm: 112, y_mm: 240, width_mm: 80}
            """),
]


def _page(ex, image_name, extra_files):
    recipe = textwrap.dedent(ex["recipe"]).strip()
    if ex.get("kind") == "poster":
        run = textwrap.dedent(f"""
            - **Command line:** `python -m pyfigures.poster.poster_headless build recipe.yaml`
            - **Poster designer:** *Build from recipe…* on the toolbar
            - **MCP server:** `build_poster_from_recipe("recipe.yaml")`
            """).strip()
    else:
        run = textwrap.dedent("""
            - **Command line:** `python -m pyfigures.recipe build recipe.yaml`
            - **PyFigures window:** *File → Build figure from recipe…*
            - **MCP server:** `build_figure_from_recipe("recipe.yaml")`
            """).strip()
    files = ", ".join(f"[`{f}`]({ex['name']}/{f})" for f in extra_files)
    return "\n".join([
        f"# {ex['title']}", "", ex["about"], "",
        f"![{ex['title']}]({ex['name']}/{image_name})", "",
        "## Recipe", "", "```yaml", recipe, "```", "",
        "## Run it", "", run, "",
        f"Files: [`recipe.yaml`]({ex['name']}/recipe.yaml), {files}. The data are in "
        f"[`docs/examples/data/`]({REPO}/tree/main/docs/examples/data); paths in the recipe are "
        "relative to the recipe.", "",
        "The result is an ordinary figure: open it in PyFigures to keep editing it by hand.", "",
        "---", "", DATA_CREDITS, ""])


def build():
    from qtpy.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])  # noqa: F841
    from pyfigures.recipe import build_figure_from_recipe
    from pyfigures.mcp_server import export_figure
    make_data()
    rows = []
    for ex in EXAMPLES:
        folder = os.path.join(HERE, ex["name"])
        # emptied rather than deleted: a synced folder (OneDrive) may be held open
        if os.path.isdir(folder):
            for entry in os.listdir(folder):
                p = os.path.join(folder, entry)
                if os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    os.remove(p)
        os.makedirs(folder, exist_ok=True)
        recipe_path = os.path.join(folder, "recipe.yaml")
        with open(recipe_path, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(ex["recipe"]).strip() + "\n")
        print("building", ex["name"])
        if ex.get("kind") == "poster":
            from pyfigures.mcp_server import build_poster_from_recipe
            res = build_poster_from_recipe(recipe_path)
            if str(res).startswith("ERROR"):
                raise RuntimeError(f"{ex['name']}: {res}")
            image, extra = "poster.png", ["poster.pyfposter"]
        else:
            build_figure_from_recipe(recipe_path)
            pyf = os.path.join(folder, "figure.pyf")
            res = json.loads(export_figure(pyf, os.path.join(folder, "figure.png"), dpi=200))
            json.loads(export_figure(pyf, os.path.join(folder, "figure.pdf"), dpi=300))
            # figure.pyf is not committed (it holds the builder's absolute paths): rebuild from the recipe
            image, extra = os.path.basename(res["output"]), ["figure.pdf"]
        with open(os.path.join(HERE, f"{ex['name']}.md"), "w", encoding="utf-8") as f:
            f.write(_page(ex, image, extra))
        about = ex["about"].replace("`", "")
        rows.append(f'<a class="pyf-card" href="{ex["name"]}.html">'
                    f'<img src="{ex["name"]}/{image}" alt="{ex["title"]}">'
                    f'<b>{ex["title"]}</b><span>{about}</span></a>')
    # (a grid of cards: the theme does not wrap table cells, which squeezed the pictures)
    style = ("<style>.pyf-gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));"
             "gap:16px;margin:1em 0}.pyf-card{display:flex;flex-direction:column;border:1px solid #e1e4e5;"
             "border-radius:4px;padding:10px;color:inherit;text-decoration:none}.pyf-card:hover"
             "{border-color:#2980b9}.pyf-card img{width:100%;height:150px;object-fit:contain;"
             "background:#f8f8f8;margin-bottom:8px}.pyf-card b{color:#2980b9;margin-bottom:4px}"
             ".pyf-card span{font-size:90%}</style>")
    index = ["# Examples", "",
             "Each example is a short recipe (a text file) and the figure PyFigures builds from it. "
             "Click one to see its recipe and how to run it. Every feature shown can also be "
             "used from the PyFigures window or the MCP server.", "",
             style, '<div class="pyf-gallery">', *rows, "</div>", "", "---", "", DATA_CREDITS, ""]
    with open(os.path.join(HERE, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index))
    print("done")


if __name__ == "__main__":
    build()
    sys.stdout.flush()
    os._exit(0)
