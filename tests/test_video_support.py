"""Video reading and writing (batoolset.img) and the offer to install PyAV.

- write_video: H.264 for mp4 / mov / mkv and VP9 for webm through PyAV (plays
  on a Mac: QuickTime / Safari / PowerPoint), odd sizes padded for yuv420p,
  OpenCV's MPEG-4 only as a fallback (with a warning);
- read_video: OpenCV, else PyAV; a clear error when neither is installed; a
  movie too big for memory keeps every k-th frame and divides the fps;
- the GUI offers `pip install av` when it is needed (once per session);
- MCP export_video reports the codec.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import logging
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtWidgets import QMessageBox  # noqa: E402

from test_canvas_context_menu import ui  # noqa: E402,F401
from test_canvas_keyboard_and_clicks import movie_gui, _answer_frame_mode  # noqa: E402,F401

av = pytest.importorskip("av")


def _movie(t=12, h=41, w=63):
    a = np.zeros((t, h, w, 3), np.uint8)
    for i in range(t):
        a[i, :, : 4 * i + 4, 0] = 200            # a red bar growing frame by frame
        a[i, 5:15, 5:15, 1] = min(250, 12 * i)
    return a


def _codec(path):
    with av.open(path) as c:
        s = c.streams.video[0]
        return s.codec_context.name, s.codec_context.width, s.codec_context.height


@pytest.mark.parametrize("ext,codec", [(".mp4", "h264"), (".mov", "h264"), (".mkv", "h264"),
                                       (".webm", "vp9")])
def test_write_video_plays_everywhere(tmp_path, ext, codec):
    from batoolset.img import write_video, read_video
    frames = _movie()
    p = str(tmp_path / ("v" + ext))
    write_video(frames, p, fps=12.5, dimensions="thwc")
    name, w, h = _codec(p)
    assert name == codec
    assert (w, h) == (64, 42)                   # padded to even for yuv420p
    md, a = read_video(p)
    assert a.shape == (12, 42, 64, 3) and md["fps"] == pytest.approx(12.5)
    assert md["frame_step"] == 1
    err = np.abs(a[:, :41, :63].astype(int) - frames.astype(int)).mean()
    assert err < 4, err                          # crf 17: visually lossless
    # the bar grows: the red channel's mean rises frame after frame
    reds = [float(f[..., 0].mean()) for f in a]
    assert reds == sorted(reds)


@pytest.mark.parametrize("ext", [".mp4", ".mov"])
@pytest.mark.parametrize("h,w", [(41, 63), (1081, 1921)])
def test_h264_follows_apple_playback_rules(tmp_path, ext, h, w):
    """What QuickTime / Safari / PowerPoint on a Mac need, checked without a Mac
    (tests/mac_check/ decodes the same files with AVFoundation on a macOS
    GitHub runner): H.264 High/Main/Baseline profile, 4:2:0 chroma, even sizes,
    'avc1' sample entry (not 'hev1'/'mp4v'), level <= 5.2, and the index (moov)
    before the data (mdat) so it starts playing before it is fully read."""
    from batoolset.img import write_video
    a = (np.random.default_rng(1).random((3, h, w, 3)) * 255).astype(np.uint8)
    p = str(tmp_path / ("v" + ext))
    write_video(a, p, fps=10, dimensions="thwc")
    with av.open(p) as c:
        s = c.streams.video[0]
        cc = s.codec_context
        assert cc.name == "h264"
        assert cc.profile in ("High", "Main", "Baseline", "Constrained Baseline"), cc.profile
        assert cc.format.name == "yuv420p"
        assert cc.width % 2 == 0 and cc.height % 2 == 0
        assert s.codec_tag == "avc1"
        level = cc.extradata[3]                  # avcC: version, profile, compat, level
        assert 10 <= level <= 52, level
    with open(p, "rb") as f:
        b = f.read()
    assert 0 < b.find(b"moov") < b.find(b"mdat")


def test_write_video_grayscale_and_without_pyav(tmp_path, monkeypatch, caplog):
    from batoolset import img as I
    g = np.stack([np.full((20, 30), 20 * i, np.uint8) for i in range(6)])
    p = str(tmp_path / "g.mp4")
    I.write_video(g, p, fps=5, dimensions="thw")
    assert _codec(p)[0] == "h264"
    md, a = I.read_video(p)
    assert a.ndim == 3 and a.shape == (6, 20, 30)        # grey comes back as grey
    # no PyAV: OpenCV writes MPEG-4 and says it may not play on a Mac
    monkeypatch.setattr(I, "_av_codec_for", lambda path: None)
    p2 = str(tmp_path / "old.mp4")
    with caplog.at_level(logging.WARNING):
        I.write_video(g, p2, fps=5, dimensions="thw")
    assert _codec(p2)[0] == "mpeg4"
    assert "may not play on a Mac" in caplog.text and "pip install av" in caplog.text


def test_read_video_falls_back_to_pyav(tmp_path, monkeypatch):
    from batoolset import img as I
    p = str(tmp_path / "v.mp4")
    I.write_video(_movie(), p, fps=10, dimensions="thwc")

    def broken(path, max_bytes):
        raise IOError("cv2 cannot read this")
    monkeypatch.setattr(I, "_read_video_cv2", broken)
    md, a = I.read_video(p)
    assert a.shape[0] == 12 and md["fps"] == pytest.approx(10)


def test_read_video_without_any_backend_says_what_to_install(tmp_path, monkeypatch):
    from batoolset import img as I
    monkeypatch.setattr(I, "video_backends", lambda: {"cv2": False, "av": False, "h264": False})
    with pytest.raises(IOError, match="pip install av"):
        I.read_video(str(tmp_path / "v.mp4"))


def test_long_video_keeps_every_kth_frame(tmp_path):
    from batoolset import img as I
    p = str(tmp_path / "v.mp4")
    I.write_video(_movie(t=20), p, fps=20, dimensions="thwc")
    one_frame = 42 * 64 * 3
    md, a = I.read_video(p, max_bytes=one_frame * 5)       # room for 5 of 20 frames
    assert md["frame_step"] == 4 and a.shape[0] == 5
    assert md["fps"] == pytest.approx(5)                   # time stamps stay right
    fr, fps, step = I._read_video_av(p, one_frame * 5)
    assert step == 4 and len(fr) == 5


def test_video_backends_reports_h264():
    from batoolset.img import video_backends
    assert video_backends() == {"cv2": True, "av": True, "h264": True}


# ------------------------------------------------------------------ GUI offer
@pytest.fixture
def offer(qapp, monkeypatch):
    from pyfigures.gui import video_support as V
    V._declined.clear()
    state = {"ok": False, "asked": 0, "installed": 0}
    monkeypatch.setattr(V, "_satisfied", lambda need: state["ok"])

    def install():
        state["installed"] += 1
        state["ok"] = True
        return True, "PyAV installed."
    monkeypatch.setattr(V, "install_pyav", install)
    yield V, state
    V._declined.clear()


def test_offer_declined_is_not_asked_again(offer, monkeypatch):
    V, state = offer

    def no(*a, **k):
        state["asked"] += 1
        return QMessageBox.No
    monkeypatch.setattr(QMessageBox, "question", staticmethod(no))
    assert V.offer_video_support(None, "h264") is False
    assert V.offer_video_support(None, "h264") is False
    assert state["asked"] == 1 and state["installed"] == 0


def test_offer_accepted_installs(offer, monkeypatch):
    V, state = offer
    texts = []

    def yes(parent, title, text, *a, **k):
        texts.append(text)
        return QMessageBox.Yes
    monkeypatch.setattr(QMessageBox, "question", staticmethod(yes))
    assert V.offer_video_support(None, "read") is True
    assert state["installed"] == 1
    assert "ffmpeg" in texts[0] and "macOS" in texts[0] and "pip install av" in texts[0]
    assert V.offer_video_support(None, "read") is True          # nothing asked now
    assert len(texts) == 1


def test_offer_failed_install_explains(offer, monkeypatch):
    V, state = offer
    monkeypatch.setattr(V, "install_pyav", lambda: (False, "no network"))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    shown = {}
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda p, t, m: shown.update(m=m)))
    assert V.offer_video_support(None, "h264") is False
    assert "no network" in shown["m"] and "pip install av" in shown["m"]


def test_install_pyav_in_a_frozen_app(monkeypatch):
    import sys
    from pyfigures.gui import video_support as V
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    ok, msg = V.install_pyav()
    assert ok is False and "can't install" in msg


def test_no_offer_when_everything_is_there(qapp, monkeypatch):
    from pyfigures.gui import video_support as V
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: pytest.fail("should not ask")))
    assert V.offer_video_support(None, "read") and V.offer_video_support(None, "h264")


def test_export_as_video_offers_h264_then_writes_it(movie_gui, monkeypatch, tmp_path):
    from pyfigures.gui import pfgui, video_support as V
    asked = []
    monkeypatch.setattr(V, "offer_video_support", lambda parent, need: asked.append(need) or True)
    out = str(tmp_path / "out.mov")
    monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: out)
    _answer_frame_mode(monkeypatch, "Freeze last frame")
    movie_gui.export_as_video()
    assert asked == ["h264"]
    assert _codec(out)[0] == "h264"
    asked.clear()
    out = str(tmp_path / "out.avi")                 # avi is MJPG: nothing to offer
    movie_gui.export_as_video()
    assert asked == [] and os.path.isfile(out)


def test_adding_a_video_offers_a_reader(qapp, ui, monkeypatch, tmp_path):
    from batoolset.img import write_video
    from pyfigures.gui import video_support as V
    from pyfigures.gui.pfgui import EZFIG_GUI
    p = str(tmp_path / "clip.mp4")
    write_video(_movie(), p, fps=10, dimensions="thwc")
    asked = []
    monkeypatch.setattr(V, "offer_video_support", lambda parent, need: asked.append(need) or True)
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    got = []
    g._load_images_then_callback([p], got.extend)
    import time
    t0 = time.time()
    while not got and time.time() - t0 < 30:
        qapp.processEvents()
        time.sleep(0.02)
    assert asked == ["read"]
    assert got and got[0].filename == p
    g._dirty = False
    g._stop_all_img_loaders()
    g.close()


def test_mcp_export_video_reports_the_codec(tmp_path):
    from pyfigures import mcp_server as M
    from batoolset.img import write_video
    clip = str(tmp_path / "clip.mp4")
    write_video(_movie(), clip, fps=10, dimensions="thwc")
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    M.add_image(pyf, [0], clip)
    out = str(tmp_path / "out.mp4")
    r = M.export_video(pyf, out)
    assert not r.startswith("ERROR"), r
    assert json.loads(r)["codec"] == "libx264" and _codec(out)[0] == "h264"
    assert M.export_video(pyf, str(tmp_path / "x.gif")).startswith("ERROR")
