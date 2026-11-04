"""PyMuPDF (vector PDF panels) offered on the user's request: in the GUI when
a PDF is added or a figure with PDF panels is exported to a vector format
(and from Tools), a note in MCP / recipe replies. Installed with pip, or in a
standalone app as checked wheels from PyPI in a per-user folder."""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import zipfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import pytest

from pyfigures import extras as X


def _wheel(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()


def _pypi(monkeypatch, packages):
    """Fake PyPI: {name: (wheel filename, wheel bytes, requires_dist)}."""
    def fetch(url, timeout):
        for name, (fn, data, reqs) in packages.items():
            if url == X.PYPI_JSON.format(name=name):
                return json.dumps({"info": {"requires_dist": reqs}, "urls": [
                    {"filename": fn, "url": "https://files/" + fn,
                     "digests": {"sha256": hashlib.sha256(data).hexdigest()}},
                    {"filename": name + "-1.0.tar.gz", "url": "https://files/sdist"}]}).encode()
            if url == "https://files/" + fn:
                return data
        raise AssertionError(url)
    monkeypatch.setattr(X, "_fetch", fetch)


def test_wheel_for_this_platform_is_picked():
    tags = ["cp311-cp311-win_amd64", "cp311-abi3-win_amd64", "py3-none-any"]
    files = [{"filename": "pymupdf-1.26.0-cp39-abi3-macosx_11_0_arm64.whl"},
             {"filename": "pymupdf-1.26.0-cp39-abi3-win_amd64.whl"},
             {"filename": "pymupdf-1.26.0.tar.gz"}]
    assert X._pick_wheel(files, tags + ["cp39-abi3-win_amd64"])["filename"].endswith("win_amd64.whl")
    assert X._pick_wheel(files[:1], tags) is None
    # this interpreter accepts some wheel tag at all
    assert X._supported_tags()


def test_standalone_install_unpacks_checked_wheels_and_their_requirements(tmp_path, monkeypatch):
    tag = X._supported_tags()[0]
    _pypi(monkeypatch, {
        "pymupdf": (f"pymupdf-1.0-{tag}.whl", _wheel({"fakefitz_pkg/__init__.py": "X = 1\n"}),
                    ["pymupdfb==1.0", "matplotlib; extra == 'plots'"]),
        "pymupdfb": (f"pymupdfb-1.0-{tag}.whl", _wheel({"fakefitz_libs/__init__.py": ""}), None)})
    X._install_wheels("pymupdf", str(tmp_path), 5)
    assert (tmp_path / "fakefitz_pkg" / "__init__.py").is_file()
    assert (tmp_path / "fakefitz_libs" / "__init__.py").is_file()   # required wheel too
    assert not (tmp_path / "matplotlib").exists()                     # extras skipped


def test_a_wheel_with_a_wrong_checksum_or_unsafe_paths_is_refused(tmp_path, monkeypatch):
    tag = X._supported_tags()[0]
    good = _wheel({"ok.py": ""})
    _pypi(monkeypatch, {"pymupdf": (f"pymupdf-1.0-{tag}.whl", good, None)})
    fetch = X._fetch
    monkeypatch.setattr(X, "_fetch", lambda url, t: b"tampered" if url.startswith("https://files/")
                        else fetch(url, t))
    with pytest.raises(RuntimeError, match="checksum"):
        X._install_wheels("pymupdf", str(tmp_path / "a"), 5)
    _pypi(monkeypatch, {"pymupdf": (f"pymupdf-1.0-{tag}.whl", _wheel({"../evil.py": ""}), None)})
    with pytest.raises(RuntimeError, match="unsafe path"):
        X._install_wheels("pymupdf", str(tmp_path / "b"), 5)
    assert not (tmp_path / "evil.py").exists()


def test_frozen_app_installs_into_the_user_folder_and_imports_from_it(tmp_path, monkeypatch):
    tag = X._supported_tags()[0]
    _pypi(monkeypatch, {"pymupdf": (f"pymupdf-1.0-{tag}.whl",
                                    _wheel({"pyf_fake_mupdf/__init__.py": "OK = True\n"}), None)})
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(X, "extras_dir", lambda: str(tmp_path / "extras"))
    monkeypatch.setattr(X, "has_pymupdf", lambda: __import__("pyf_fake_mupdf").OK)
    monkeypatch.setattr(sys, "path", list(sys.path))
    ok, msg = X.install_pymupdf()
    assert ok, msg
    assert str(tmp_path / "extras") in sys.path
    sys.modules.pop("pyf_fake_mupdf", None)


def test_pip_install_when_not_frozen(monkeypatch):
    calls = []

    class P:
        returncode = 0
        stdout = stderr = ""
    monkeypatch.setattr(X.subprocess, "run", lambda cmd, **k: calls.append(cmd) or P())
    monkeypatch.setattr(X, "has_pymupdf", lambda: True)
    assert X.install_pymupdf()[0]
    assert calls[0][-3:] == ["pip", "install", "pymupdf"]


# --- the GUI offer --------------------------------------------------------

@pytest.fixture
def offer(monkeypatch, qapp):
    from pyfigures.gui import pdf_support as P
    from pyfigures.gui import user_prefs
    monkeypatch.setattr(P, "ASK_OFFSCREEN", True)
    monkeypatch.setattr(P, "_asked_this_session", [False])
    monkeypatch.setattr(P, "has_pymupdf", lambda: False)
    user_prefs.save_offer_pymupdf(True)
    shown = []

    def answer(button_text, dont_ask=False):
        def exec_(box):
            shown.append(box.text() + " " + box.informativeText())
            if dont_ask and box.checkBox() is not None:
                box.checkBox().setChecked(True)
            for b in box.buttons():
                if b.text() == button_text:
                    b.click()
            return 0
        monkeypatch.setattr(P.QMessageBox, "exec", exec_)
    monkeypatch.setattr(P.QMessageBox, "information", lambda *a, **k: shown.append(a[2]))
    monkeypatch.setattr(P.QMessageBox, "warning", lambda *a, **k: shown.append(a[2]))
    return P, answer, shown


def test_offer_installs_and_converts_the_pdf_panels(offer, monkeypatch):
    P, answer, shown = offer
    monkeypatch.setattr(P, "install_pymupdf", lambda: (True, "ok"))

    class Panel:
        filename = "x.pdf"
        redone = 0

        def setFigure(self, f):
            self.redone += 1
    panel = Panel()
    answer("Install PyMuPDF")
    assert P.offer_pymupdf(None, "add", [panel]) is True
    assert "AGPL v3" in shown[0] and "PyPI" in shown[0] and "600-dpi" in shown[0]
    assert panel.redone == 1 and "1 panel(s) converted" in shown[-1]


def test_offer_once_per_session_and_dont_ask_again(offer, monkeypatch):
    P, answer, shown = offer
    from pyfigures.gui import user_prefs
    answer("Not now", dont_ask=True)
    assert P.offer_pymupdf(None, "add") is False
    assert user_prefs.load_offer_pymupdf() is False
    n = len(shown)
    monkeypatch.setattr(P, "_asked_this_session", [False])
    assert P.offer_pymupdf(None, "export") is False and len(shown) == n   # not asked again
    # Tools menu: always asks
    answer("Not now")
    assert P.offer_pymupdf(None, "menu", force=True) is False and len(shown) == n + 1
    user_prefs.save_offer_pymupdf(True)


def test_failed_install_says_how_to_do_it(offer, monkeypatch):
    P, answer, shown = offer
    monkeypatch.setattr(P, "install_pymupdf", lambda: (False, "no network"))
    answer("Install PyMuPDF")
    assert P.offer_pymupdf(None, "add") is False
    assert "no network" in shown[-1] and "pip install pymupdf" in shown[-1]


def test_failed_install_in_a_standalone_app_does_not_say_pip(offer, monkeypatch):
    # the apps have no pip: point at the connection instead
    P, answer, shown = offer
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(P, "install_pymupdf", lambda: (False, "no network"))
    answer("Install PyMuPDF")
    assert P.offer_pymupdf(None, "add") is False
    assert "no network" in shown[-1] and "pip" not in shown[-1] and "internet" in shown[-1]


def test_downloads_use_certifi_not_the_windows_store(monkeypatch):
    # one malformed certificate in the Windows store made Python's default
    # context fail ("[ASN1: NOT_ENOUGH_DATA]"): the in-app install died before
    # downloading anything, while pip (own bundle) worked
    import ssl
    certifi = pytest.importorskip("certifi")
    seen = {}

    def no_windows_store(self, *a, **k):
        raise ssl.SSLError("[ASN1: NOT_ENOUGH_DATA] not enough data")

    monkeypatch.setattr(ssl.SSLContext, "load_default_certs", no_windows_store)
    real = ssl.create_default_context

    def spy(*a, **k):
        seen.update(k)
        return real(*a, **k)

    monkeypatch.setattr(ssl, "create_default_context", spy)
    ctx = X.ssl_context()
    assert isinstance(ctx, ssl.SSLContext) and seen.get("cafile") == certifi.where()

    opened = {}

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda url, timeout=None, context=None: opened.update(context=context) or R(b"{}"))
    assert X._fetch("https://pypi.org/pypi/pymupdf/json", 5) == b"{}"
    assert isinstance(opened["context"], ssl.SSLContext)


def test_nobody_is_asked_offscreen(monkeypatch, qapp):
    from pyfigures.gui import pdf_support as P
    monkeypatch.setattr(P, "has_pymupdf", lambda: False)
    monkeypatch.setattr(P, "_asked_this_session", [False])
    monkeypatch.setattr(P.QMessageBox, "exec", lambda box: pytest.fail("asked"))
    assert P.offer_pymupdf(None, "add") is False


@pytest.fixture
def gui(qapp):
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    yield g
    g.paint.EZFIG_panel.shapes_to_draw.clear()
    g._dirty = False
    g.close()
    g.deleteLater()
    qapp.processEvents()


def test_gui_hooks(gui, monkeypatch):
    from pyfigures.gui import pdf_support as P
    asked = []
    monkeypatch.setattr(P, "offer_pymupdf",
                        lambda parent, reason, panels=None, force=False: asked.append(reason) or False)
    # export of a figure without PDF panels: nothing to offer
    assert gui._offer_vector_pdf("export") is False and asked == []
    titles = [a.text() for m in gui.menuBar.actions() if m.menu() for a in m.menu().actions()]
    assert "Vector PDF panels (PyMuPDF)…" in titles
    tools = next(m.menu() for m in gui.menuBar.actions() if m.text() == "Tools")
    next(a for a in tools.actions() if a.text().startswith("Vector PDF")).trigger()
    assert asked == ["menu"]


def test_mcp_and_recipe_say_what_pymupdf_would_change(tmp_path, monkeypatch, qapp):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    M = pytest.importorskip("pyfigures.mcp_server")
    fig = plt.figure(figsize=(2, 2))
    plt.plot([0, 1], [0, 1])
    fig.savefig(tmp_path / "plot.pdf")
    plt.close(fig)
    monkeypatch.setattr(X, "has_pymupdf", lambda: False)
    pyf = tmp_path / "f.pyf"
    M.create_figure(str(pyf), num_groups=1)
    res = M.add_image(str(pyf), [0], str(tmp_path / "plot.pdf"))
    assert "PyMuPDF keeps them as vectors" in res and "ask the user" in res
    out = json.loads(M.build_figure_from_recipe(str(tmp_path / "r.yaml"), recipe_text=(
        "output: r.pyf\nrows:\n  - [plot.pdf]\n")))
    assert any("PyMuPDF" in w for w in out["warnings"])
    monkeypatch.setattr(X, "has_pymupdf", lambda: True)
    assert "PyMuPDF" not in M.add_image(str(pyf), [0], str(tmp_path / "plot.pdf"))
