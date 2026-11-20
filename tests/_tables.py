"""Small tables for the data-plot tests, written into the test's own folder.

The tests first read demo_figures/plots_playground/measurements.xlsx, which is not in
the repository: they failed on GitHub (CI 2026-11-20)."""
import numpy as np
import pandas as pd


def measurements_xlsx(folder):
    """An Excel book like the playground's: 'counts' (WT, mutA, mutB: mutA clearly lower,
    so a plot of it gets significance brackets) and 'growth' (genotype, day, length)."""
    rng = np.random.default_rng(3)
    path = str(folder / "measurements.xlsx")
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        pd.DataFrame({"WT": rng.normal(42, 2.5, 10), "mutA": rng.normal(35, 2, 10),
                      "mutB": rng.normal(41, 2.5, 10)}).to_excel(w, sheet_name="counts", index=False)
        rows = [(g, d, 10 + 2 * i + rng.normal()) for g in ("WT", "mut") for i, d in enumerate(("d1", "d2"))
                for _ in range(8)]
        pd.DataFrame(rows, columns=["genotype", "day", "length"]).to_excel(w, sheet_name="growth", index=False)
    return path
