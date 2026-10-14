# Time-lapse montage with time stamps

Five frames of a movie in a row, each stamped with its time.

![Time-lapse montage with time stamps](timelapse/figure.png)

## Recipe

```yaml
output: figure.pyf
width_mm: 180
rows:
  - - montage: ../data/transport.tif
      axis: t
      frames: "0:15:3"
      interval: 2
      unit: min
      stamps: true
```

## Run it

- **Command line:** `python -m pyfigures.recipe build recipe.yaml`
- **PyFigures window:** *File → Build figure from recipe…*
- **MCP server:** `build_figure_from_recipe("recipe.yaml")`

Files: [`recipe.yaml`](timelapse/recipe.yaml), [`figure.pyf`](timelapse/figure.pyf), [`figure.pdf`](timelapse/figure.pdf). The data are in [`docs/examples/data/`](https://github.com/baigouy/PyFigures/tree/main/docs/examples/data); paths in the recipe are relative to the recipe.

The result is an ordinary figure: open it in PyFigures to keep editing it by hand.

---

Sample images from [scikit-image](https://scikit-image.org/docs/stable/api/skimage.data.html): `human_mitosis` (nuclei, Moffat et al., Cell 2006), `cells3d` (membrane and nuclei, Allen Institute for Cell Science), `protein_transport` (time-lapse, Boisvert et al.), `skin` (H&E-stained skin). The CSV data are simulated.
