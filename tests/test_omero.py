"""Images from an OMERO server through OMERO.web (batoolset.omero_web), and
their use in PyFigures: add_image / recipes / inspect_omero_image / the GUI
URL action with its login prompt.

A local HTTP server stands in for OMERO.web: imgData JSON, greyscale
render_image / render_image_region PNGs, and the JSON API login (token,
servers, login) guarding a private image. No internet needed.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import io
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from batoolset import omero_web as O

_REAL_RAW_CONNECTION = O.raw_connection

# image 1 (public): T=2, Z=3, C=2, 40 x 50 uint16, 0.25 µm px
RNG = np.random.default_rng(1)
DATA = {1: RNG.integers(100, 4000, (2, 3, 40, 50, 2)).astype(np.uint16),
        2: RNG.integers(0, 255, (1, 1, 30, 20, 1)).astype(np.uint8),          # private
        3: RNG.integers(0, 255, (1, 1, 3100, 3200, 1)).astype(np.uint8)}      # region tiles
TYPES = {1: "uint16", 2: "uint8", 3: "uint8"}
PREFIX = "/omero"
STATE = {"renders": 0, "regions": 0}


def _img_data(iid):
    a = DATA[iid]
    t, z, h, w, c = a.shape
    chans = []
    for k in range(c):
        ch = a[..., k]
        chans.append({"label": ["Membrane", "DNA"][k] if iid == 1 else "Grey",
                      "color": ["00FF00", "FF00FF"][k] if iid == 1 else "FFFFFF",
                      "window": {"min": int(ch.min()), "max": int(ch.max()),
                                 "start": int(ch.min()), "end": int(ch.max())},
                      "active": True})
    return {"id": iid, "meta": {"imageName": f"img{iid}", "pixelsType": TYPES[iid]},
            "size": {"width": w, "height": h, "z": z, "t": t, "c": c},
            "pixel_size": {"x": 0.25, "y": 0.25, "z": 1.0}, "channels": chans}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="application/json", headers=()):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in headers:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _logged_in(self):
        return "sessionid=ok" in (self.headers.get("Cookie") or "")

    def do_GET(self):
        u = urlsplit(self.path)
        q = parse_qs(u.query)
        p = u.path[len(PREFIX):] if u.path.startswith(PREFIX) else u.path
        if p == "/api/v0/token/":
            return self._send(200, json.dumps({"data": "tok"}).encode(),
                              headers=[("Set-Cookie", "csrftoken=tok; Path=/")])
        if p == "/api/v0/servers/":
            return self._send(200, json.dumps({"data": [{"id": 1, "host": "localhost"}]}).encode())
        parts = [s for s in p.split("/") if s]
        if len(parts) >= 3 and parts[0] == "webgateway":
            iid = int(parts[2])
            if iid not in DATA:
                return self._send(404, b"{}")
            if iid == 2 and not self._logged_in():
                return self._send(302, b"", "text/html", [("Location", PREFIX + "/webclient/login/")])
            if parts[1] == "imgData":
                return self._send(200, json.dumps(_img_data(iid)).encode())
            if parts[1] in ("render_image", "render_image_region"):
                from PIL import Image
                z, t = int(parts[3]), int(parts[4])
                spec = q["c"][0]
                assert q.get("m") == ["g"]
                ch = int(spec.split("|")[0]) - 1
                lo, hi = (float(v) for v in spec.split("|")[1].split("$")[0].split(":"))
                plane = DATA[iid][t, z, :, :, ch].astype(float)
                if parts[1] == "render_image_region":
                    STATE["regions"] += 1
                    x, y, w, h = (int(v) for v in q["region"][0].split(","))
                    plane = plane[y:y + h, x:x + w]
                else:
                    STATE["renders"] += 1
                grey = np.clip(np.round((plane - lo) / (hi - lo) * 255), 0, 255).astype(np.uint8)
                buf = io.BytesIO()
                Image.fromarray(np.stack([grey] * 3, -1)).save(buf, "PNG")
                return self._send(200, buf.getvalue(), "image/png")
        return self._send(404, b"{}")

    def do_POST(self):
        p = urlsplit(self.path).path[len(PREFIX):]
        n = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(n).decode())
        if p == "/api/v0/login/":
            if self.headers.get("X-CSRFToken") != "tok":
                return self._send(403, json.dumps({"message": "CSRF"}).encode())
            if form.get("username") == ["alice"] and form.get("password") == ["secret"]:
                return self._send(200, json.dumps({"success": True}).encode(),
                                  headers=[("Set-Cookie", "sessionid=ok; Path=/")])
            return self._send(403, json.dumps({"success": False, "message": "Login failed"}).encode())
        return self._send(404, b"{}")


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}{PREFIX}"
    yield base
    httpd.shutdown()


@pytest.fixture(autouse=True)
def fresh_sessions(monkeypatch):
    monkeypatch.delenv("OMERO_USERNAME", raising=False)
    monkeypatch.delenv("OMERO_USER", raising=False)
    monkeypatch.delenv("OMERO_PASSWORD", raising=False)
    O._SESSIONS.clear()
    # hermetic: never open a real Ice connection (omero-py may be installed);
    # the fake_omero_py fixture restores the real function
    monkeypatch.setattr(O, "raw_connection", lambda base: None)
    yield
    O._SESSIONS.clear()


def test_link_formats():
    b = "https://omero.example.org/omero"
    for link in (f"{b}/webclient/img_detail/12/", f"{b}/webclient/?show=image-12",
                 f"{b}/webclient/?show=dataset-3|image-12", f"{b}/iviewer/?images=12&dataset=3",
                 f"{b}/webgateway/img_detail/12", f"{b}/webgateway/imgData/12/",
                 f"{b}/webclient/img_detail/12/#z=0-3&t=1"):
        assert O.parse_omero_url(link) == (b, 12), link
    assert O.parse_omero_url("https://host/webclient/img_detail/7/") == ("https://host", 7)
    for not_omero in ("https://host/image.tif", "https://host/x.zarr", "/local/file.tif",
                      "https://host/webclient/?show=dataset-3"):
        assert not O.is_omero_url(not_omero)
    assert O._selection("x#z=0-2&t=1&c=0,1") == {"z": [0, 1, 2], "t": [1], "c": [0, 1]}


def test_read_public_image(server):
    url = f"{server}/webclient/img_detail/1/"
    info = O.describe(url)
    assert info["size"] == {"width": 50, "height": 40, "z": 3, "t": 2, "c": 2}
    assert info["rendered_planes"] == 12 and info["channels"][1]["label"] == "DNA"
    meta, arr = O.read_omero(url)
    assert arr.shape == (2, 3, 40, 50, 2) and arr.dtype == np.uint16 and meta["dimensions"] == "tdhwc"
    src = DATA[1]
    step = (src.max(axis=(0, 1, 2, 3)) - src.min(axis=(0, 1, 2, 3))) / 255.0
    err = np.abs(arr.astype(float) - src.astype(float)).max(axis=(0, 1, 2, 3))
    assert np.all(err <= step / 2 + 1)                     # 256 levels over each channel's range
    assert meta["vx"] == 0.25 and meta["vz"] == 1.0 and meta["AR"] == 4.0
    assert meta["channel_names"] == ["Membrane", "DNA"] and len(meta["LUTs"]) == 2
    assert meta["omero"]["image_id"] == 1 and meta["omero"]["quantised_to_8_bits"]


def test_plane_selection_and_errors(server):
    meta, arr = O.read_omero(f"{server}/webclient/img_detail/1/#z=1&t=0&c=1")
    assert arr.shape == (40, 50) and meta["dimensions"] == "hw" and meta["channel_names"] == ["DNA"]
    _, arr = O.read_omero(f"{server}/webclient/img_detail/1/#t=1")
    assert arr.shape == (3, 40, 50, 2)
    with pytest.raises(ValueError, match="z must be within"):
        O.read_omero(f"{server}/webclient/img_detail/1/#z=9")
    with pytest.raises(ValueError, match="choose planes"):
        O.read_omero(f"{server}/webclient/img_detail/1/", max_bytes=1000)
    with pytest.raises(FileNotFoundError):
        O.describe(f"{server}/webclient/img_detail/99/")


def test_big_planes_are_read_in_regions(server):
    STATE["regions"] = 0
    _, arr = O.read_omero(f"{server}/webclient/img_detail/3/")
    assert arr.shape == (3100, 3200) and STATE["regions"] == 4
    assert np.abs(arr.astype(int) - DATA[3][0, 0, :, :, 0].astype(int)).max() <= 1


def test_private_image_needs_a_login(server, monkeypatch):
    url = f"{server}/webclient/?show=image-2"
    with pytest.raises(O.OmeroLoginRequired) as e:
        O.describe(url)
    assert e.value.base == server
    with pytest.raises(PermissionError, match="Login failed"):
        O.login(server, "alice", "wrong")
    assert O.login(server, "alice", "secret")
    meta, arr = O.read_omero(url)
    assert arr.shape == (30, 20) and arr.dtype == np.uint8
    assert np.array_equal(arr, DATA[2][0, 0, :, :, 0])     # 8-bit data: exact
    # from the environment (scripts, recipes, the MCP server)
    O._SESSIONS.clear()
    monkeypatch.setenv("OMERO_USERNAME", "alice")
    monkeypatch.setenv("OMERO_PASSWORD", "secret")
    assert O.describe(url)["size"]["width"] == 20


@pytest.fixture
def fake_omero_py(monkeypatch):
    """A stand-in for omero-py's BlitzGateway (zeroc-ice cannot be installed
    here): Ice reachable on the web host's port 4064, credentials alice/secret,
    raw planes from DATA. The calls are those of omero.gateway: BlitzGateway(user,
    passwd, host=, port=, secure=), connect(), getObject('Image', id),
    getPrimaryPixels().getPlanes([(z, c, t), ...])."""
    import sys
    import types
    calls = {"connect": [], "planes": 0, "reachable": True}

    class Pixels:
        def __init__(self, iid):
            self.iid = iid

        def getPlanes(self, zct):
            for z, c, t in zct:
                calls["planes"] += 1
                yield DATA[self.iid][t, z, :, :, c].copy()

    class Image:
        def __init__(self, iid):
            self.iid = iid

        def getPrimaryPixels(self):
            return Pixels(self.iid)

    class BlitzGateway:
        def __init__(self, username=None, passwd=None, host=None, port=None, secure=None, **kw):
            self.cred, self.host, self.port = (username, passwd), host, port

        def connect(self):
            calls["connect"].append((self.host, self.port))
            return calls["reachable"] and self.cred == ("alice", "secret") \
                and self.host == "127.0.0.1" and self.port == 4064

        def isConnected(self):
            return True

        def keepAlive(self):
            return True

        def close(self):
            pass

        def getObject(self, kind, iid):
            assert kind == "Image"
            return Image(iid) if iid in DATA else None

    omero = types.ModuleType("omero")
    gateway = types.ModuleType("omero.gateway")
    gateway.BlitzGateway = BlitzGateway
    omero.gateway = gateway
    monkeypatch.setitem(sys.modules, "omero", omero)
    monkeypatch.setitem(sys.modules, "omero.gateway", gateway)
    monkeypatch.setattr(O, "raw_connection", _REAL_RAW_CONNECTION)
    O._RAW_CONNS.clear()
    O._CREDENTIALS.clear()
    yield calls
    O._RAW_CONNS.clear()
    O._CREDENTIALS.clear()


def test_raw_16_bit_pixels_with_omero_py(server, fake_omero_py):
    url = f"{server}/webclient/img_detail/1/"
    assert O.raw_reader_installed()
    assert "after a login" in O.describe(url)["raw_reader"]
    # public image, not logged in: OMERO.web renders (no Ice connection tried)
    meta, _ = O.read_omero(url)
    assert meta["omero"]["reader"] == "omero.web" and not fake_omero_py["connect"]
    O.login(server, "alice", "secret")
    assert O.describe(url)["raw_reader"] == "omero-py (raw pixels)"
    STATE["renders"] = 0
    meta, arr = O.read_omero(url + "#z=0-1&t=1")
    assert meta["omero"]["reader"] == "omero-py" and not meta["omero"]["quantised_to_8_bits"]
    assert arr.dtype == np.uint16 and np.array_equal(arr, DATA[1][1, 0:2])     # exact, all 16 bits
    assert STATE["renders"] == 0 and fake_omero_py["planes"] == 4
    assert fake_omero_py["connect"] == [("127.0.0.1", 4064)]
    # the connection is reused, and raw=False still asks OMERO.web
    O.read_omero(url + "#z=0&t=0")
    assert len(fake_omero_py["connect"]) == 1
    meta, _ = O.read_omero(url + "#z=0&t=0", raw=False)
    assert meta["omero"]["reader"] == "omero.web" and STATE["renders"] == 2
    O.logout(server)
    assert server not in O._CREDENTIALS and server not in O._RAW_CONNS


def test_raw_reader_falls_back_to_omero_web(server, fake_omero_py, monkeypatch):
    fake_omero_py["reachable"] = False                 # Ice port closed, no websockets
    monkeypatch.setenv("OMERO_HOST", "omero-ice.example.org")
    O.login(server, "alice", "secret")
    meta, arr = O.read_omero(f"{server}/webclient/img_detail/1/#z=0&t=0")
    assert meta["omero"]["reader"] == "omero.web" and arr.dtype == np.uint16
    hosts = [h for h, _ in fake_omero_py["connect"]]
    assert hosts == ["omero-ice.example.org", "127.0.0.1", f"wss://{server.split('//')[1].split('/')[0]}/omero-ws"]


def test_img_and_pyfigures_tools(qapp, server, tmp_path):
    from batoolset.img import Img
    from pyfigures import mcp_server as M
    from pyfigures.mcp_tools.core import _raw_size_from_file
    url = f"{server}/webclient/img_detail/1/#t=0"
    img = Img(url)
    assert img.shape == (3, 40, 50, 2) and img.metadata["vx"] == 0.25
    assert _raw_size_from_file(url) == (50, 40)
    info = json.loads(M.inspect_omero_image(url))
    assert info["selected"]["t"] == [0] and info["pixel_size_um"]["x"] == 0.25
    assert M.inspect_omero_image(f"{server}/webclient/img_detail/2/").startswith("ERROR")
    assert M.inspect_omero_image("https://host/a.tif").startswith("ERROR: not an OMERO")
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1)
    assert M.add_image(pyf, [0], url).startswith(f"Added {url} as image")   # the link, not "?show=…"
    out = str(tmp_path / "f.png")
    json.loads(M.export_figure(pyf, out, dpi=72))
    assert os.path.getsize(out) > 0


def test_recipe_with_an_omero_image(qapp, server, tmp_path):
    from pyfigures.recipe import build_figure_from_recipe
    out = str(tmp_path / "r.pyf")
    recipe = {"output": out, "rows": [[{"image": f"{server}/webclient/img_detail/1/#z=0&t=0",
                                        "scale_bar": {"units": 2}}]]}
    path = tmp_path / "r.json"
    path.write_text(json.dumps(recipe), encoding="utf-8")
    build_figure_from_recipe(str(path))
    assert "img_detail/1/" in open(out, encoding="utf-8").read()


def test_opening_a_figure_with_private_images_asks_for_a_login(qapp, server, tmp_path, monkeypatch):
    from qtpy.QtWidgets import QInputDialog
    from pyfigures import mcp_server as M
    from pyfigures.gui.pfgui import EZFIG_GUI
    url = f"{server}/webclient/img_detail/2/"
    O.login(server, "alice", "secret")
    pyf = str(tmp_path / "private.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1)
    M.add_image(pyf, [0], url)
    O._SESSIONS.clear()                                    # a new session: logged out
    answers = ["alice", "secret"]
    asked = []

    def get_text(parent, title, label, *a, **k):
        asked.append(title)
        return answers.pop(0), True
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(get_text))
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.show()
    try:
        g._start_pyf_loader([pyf], append=False, reset_undo=True)
        assert asked == ["OMERO login", "OMERO login"]
        g.wait_for_images()
        from batoolset.lists.tools import flatten_iterable
        imgs = [s for s in flatten_iterable(g.paint.EZFIG_panel.shapes_to_draw) if hasattr(s, "filename")]
        assert imgs and imgs[0].img is not None and imgs[0].img.shape == (30, 20), \
            (imgs[0].filename if imgs else None, O._SESSIONS)
    finally:
        g._dirty = False
        g._stop_all_img_loaders()
        g.close()


def test_gui_url_action_logs_in_and_picks_planes(qapp, server, monkeypatch):
    from qtpy.QtWidgets import QInputDialog, QMessageBox
    from batoolset.lists.tools import flatten_iterable
    from pyfigures.gui.pfgui import EZFIG_GUI
    answers = [f"{server}/webclient/?show=image-2", "alice", "secret"]
    asked = []

    def get_text(parent, title, label, *a, **k):
        asked.append(title)
        return answers.pop(0), True
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(get_text))
    msgs = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: msgs.append(a[1])))
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.show()
    try:
        g.add_image_from_url_action()
        t0 = time.time()
        while time.time() - t0 < 30 and not g.paint.EZFIG_panel.shapes_to_draw:
            qapp.processEvents()
            time.sleep(0.01)
        assert not msgs and asked.count("OMERO login") == 2
        imgs = [s for s in flatten_iterable(g.paint.EZFIG_panel.shapes_to_draw) if hasattr(s, "filename")]
        assert [i.filename for i in imgs] == [f"{server}/webclient/img_detail/2/"]
        g.wait_for_images()
        assert imgs[0].img is not None and imgs[0].img.shape == (30, 20)
        # a stack too big to read whole: the planes are asked for
        monkeypatch.setattr(O, "MAX_PLANES", 5)
        answers[:] = [f"{server}/webclient/img_detail/1/", "z=0-1&t=1"]
        asked.clear()
        g.add_image_from_url_action()
        assert asked[-1] == "Planes to read"
        t0 = time.time()
        while time.time() - t0 < 30 and len([s for s in flatten_iterable(g.paint.EZFIG_panel.shapes_to_draw)
                                             if hasattr(s, "filename")]) < 2:
            qapp.processEvents()
            time.sleep(0.01)
        names = [s.filename for s in flatten_iterable(g.paint.EZFIG_panel.shapes_to_draw) if hasattr(s, "filename")]
        assert f"{server}/webclient/img_detail/1/#z=0-1&t=1" in names
    finally:
        g._dirty = False
        g._stop_all_img_loaders()
        g.close()
