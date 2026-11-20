"""2026-11-20, PyFigures CI on macOS: the plot's font passed the "can matplotlib draw it"
check, yet measuring its tick labels at the plot's sizes raised "failed to load glyph".
The plot was left unfitted and 2 % of its panel stayed empty. The font is now dropped
when that happens and the plot is fitted again in one that draws."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_a_font_that_fails_at_the_plots_size_is_replaced(tmp_path, monkeypatch):
    import pandas as pd
    from matplotlib.backends import backend_agg
    import batoolset.matplolibs.tools as T
    import batoolset.drawings.shapes.image2d as I
    from pyfigures.mcp_server import create_figure, add_data_plot, preview_panel_source

    monkeypatch.setattr(T, "_BEST_HELVETICA", [])
    monkeypatch.setattr(I, "_FONT_DRAWS", {})
    bad = T.best_helvetica_clone()
    assert bad != "DejaVu Sans"            # a clone other than the last resort is installed
    real = backend_agg.RendererAgg.get_text_width_height_descent

    fitting = []

    def flaky(self, s, prop, ismath):
        # as on macOS CI: the check and the panel script draw it, fitting it fails
        if fitting and bad in prop.get_family():
            raise RuntimeError("failed to load glyph")
        return real(self, s, prop, ismath)
    monkeypatch.setattr(backend_agg.RendererAgg, "get_text_width_height_descent", flaky)
    real_fit = I.Image2D._fit_page_sizes_once

    def fit(self, *a):
        fitting.append(1)
        try:
            return real_fit(self, *a)
        finally:
            fitting.pop()
    monkeypatch.setattr(I.Image2D, "_fit_page_sizes_once", fit)

    csv = tmp_path / "values.csv"
    pd.DataFrame({"WT": [1, 2, 3, 2, 3], "mutA": [4, 5, 4, 6, 5]}).to_csv(csv, index=False)
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    out = add_data_plot(pyf, [0], str(csv))
    assert not out.startswith("ERROR"), out
    text, _img = preview_panel_source(pyf, [0], 0, view="figure")
    assert "EMPTY:" not in text, text
    assert I._FONT_DRAWS.get(bad) is False
