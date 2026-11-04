# Micrographs with scale bars and letters

Two crops of the same image side by side, lettered A and B, each with a scale bar, sized for a Nature single column.

![Micrographs with scale bars and letters](basic/figure.png)

## Recipe

```yaml
output: figure.pyf
journal: nature
column: single
defaults:
  px_to_unit: 0.2                  # µm per pixel
  scale_bar: {units: 10, unit: "µm"}
rows:
  - - {image: ../data/mitosis.png, crop: {right: 256}}
    - {image: ../data/mitosis.png, crop: {left: 256}, lut: magenta}
```

## Run it

- **Command line:** `python -m pyfigures.recipe build recipe.yaml`
- **PyFigures window:** *File → Build figure from recipe…*
- **MCP server:** `build_figure_from_recipe("recipe.yaml")`

Files: [`recipe.yaml`](basic/recipe.yaml), [`figure.pdf`](basic/figure.pdf). The data are in [`docs/examples/data/`](https://github.com/baigouy/PyFigures/tree/main/docs/examples/data); paths in the recipe are relative to the recipe.

The result is an ordinary figure: open it in PyFigures to keep editing it by hand.

---

Sample images from [scikit-image](https://scikit-image.org/docs/stable/api/skimage.data.html): `human_mitosis` (nuclei, Moffat et al., Cell 2006), `cells3d` (membrane and nuclei, Allen Institute for Cell Science), `protein_transport` (time-lapse, Boisvert et al.), `skin` (H&E-stained skin). The CSV data are simulated.
