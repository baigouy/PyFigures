# Zoom callout

A region of a large histology image magnified in a corner, with the box and the leader lines drawn automatically.

![Zoom callout](zoom/figure.png)

## Recipe

```yaml
output: figure.pyf
width_mm: 120
rows:
  - - image: ../data/skin.jpg
      zoom: {box: [700, 380, 160, 120], corner: bottom right, size: 0.42}
```

## Run it

- **Command line:** `python -m pyfigures.recipe build recipe.yaml`
- **PyFigures window:** *File → Build figure from recipe…*
- **MCP server:** `build_figure_from_recipe("recipe.yaml")`

Files: [`recipe.yaml`](zoom/recipe.yaml), [`figure.pdf`](zoom/figure.pdf). The data are in [`docs/examples/data/`](https://github.com/baigouy/PyFigures/tree/main/docs/examples/data); paths in the recipe are relative to the recipe.

The result is an ordinary figure: open it in PyFigures to keep editing it by hand.

---

Sample images from [scikit-image](https://scikit-image.org/docs/stable/api/skimage.data.html): `human_mitosis` (nuclei, Moffat et al., Cell 2006), `cells3d` (membrane and nuclei, Allen Institute for Cell Science), `protein_transport` (time-lapse, Boisvert et al.), `skin` (H&E-stained skin). The CSV data are simulated.
