# Script panels: plots PyFigures has no tool for

A **script panel** is a panel drawn by Python code stored in the `.pyf`. It is how a plot
PyFigures does not make itself (a phylogenetic tree, a map, a genome track, a network...)
goes into a figure. You can write the script yourself, or give this page to an LLM or a
coding agent: it says everything the script must do.

## The contract

The script is plain Python, run when the figure opens.

**Already defined** (no import needed):

| name        | what it is                                                         |
|-------------|--------------------------------------------------------------------|
| `plt`       | `matplotlib.pyplot`                                                |
| `np`        | `numpy`                                                            |
| `self`      | the panel; the script sets `self.img`                              |
| `file_path` | the panel's linked data file (a tree file, a table...), or `None`  |

**It must end by setting `self.img`** to one of:

| `self.img` is                         | the panel is                                       | use it for |
|---------------------------------------|----------------------------------------------------|------------|
| a matplotlib `Figure` (**best**)       | vector: sharp in the PDF / SVG export; its text follows the figure's font and size; title, axis labels, tick labels and legend each adjustable in the panel editor | any plot or diagram drawn with matplotlib (Bio.Phylo, ete3's matplotlib output, networkx, cartopy, ...) |
| a NumPy image (`H x W` grey or `H x W x 3` RGB, `uint8`) | pixels | an image you computed or rendered |
| the path of an **SVG or PDF** file the script wrote | vector, as a dropped SVG / PDF | a tool that writes its own vector file (R, graphviz, a tree viewer) |

**Rules**

* Read the data from `file_path` (link the file to the panel) or from an absolute path.
* Never call `plt.show()`; do not open windows.
* Set the figure's size with `figsize` (inches): its width / height ratio is the panel's
  shape. The panel is scaled to the figure's layout; the text keeps the figure's sizes.
* Imports, helper functions and recursive functions are fine (needs batoolset-gui 0.2.10
  or later; before it, a function the script defined could not see the script's imports).
* Keep it self-contained and fast: it runs each time the figure opens.

## Example: a tree (shape of the script only)

```python
from Bio import Phylo                     # any library the user has installed

tree = Phylo.read(file_path, "newick")    # the panel's linked tree file
fig, ax = plt.subplots(figsize=(3.5, 4))
Phylo.draw(tree, axes=ax, do_show=False)
ax.set_xlabel("branch length")
self.img = fig
```

## Putting it in a figure

* **The chat (MCP):** `add_scripted_image(group_path, script)` adds the panel;
  `set_script(...)` replaces a panel's script. The script is run before it is added: one
  that fails is refused with its error, so the model can fix it.
* **A recipe:** a `script:` panel (with `allow_scripts: true`), see RECIPES.md.
* **The GUI:** double-click a panel, *Script* tab, paste the code.

## Checking a script before using it

```
python -m pyfigures.script_panels my_panel.py [data_file]
```

prints `OK: the panel is figure (3.50 x 4.00 in)` or what failed and this contract.
From Python: `pyfigures.script_panels.check_script(code, file_path)`.
