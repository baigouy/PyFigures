"""H.264 without x264 (2026-11-18): opencv-python-headless 5.1's FFmpeg libraries took
the place of PyAV's on macOS, which then had no libx264, and every macOS app failed its
video self-test. The self-test and the chat demo videos now use the encoder the video
export uses (x264, else VideoToolbox on macOS, else Media Foundation on Windows), and
the self-test really writes and reads back an MP4."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

av = pytest.importorskip("av")

SYSTEM_H264 = ('h264_videotoolbox', 'h264_mf')


def _usable(codec):
    if codec not in av.codecs_available:
        return False
    try:
        av.CodecContext.create(codec, 'w')
        return True
    except Exception:
        return False


def _without(monkeypatch, *codecs):
    monkeypatch.setattr(av, 'codecs_available', set(av.codecs_available) - set(codecs))


def test_the_self_test_writes_a_real_h264_mp4(tmp_path):
    from pyfigures.self_test import _check_video
    result = _check_video(str(tmp_path))
    assert result.startswith('ok (PyAV ') and os.path.getsize(tmp_path / 'self_test.mp4') > 0


def test_without_x264_the_self_test_uses_videotoolbox_or_says_there_is_none(tmp_path, monkeypatch):
    """The macOS case. (Media Foundation is left out: inside a Qt process on Windows
    COM is already set up in a mode it cannot use, and Windows wheels always have x264.)"""
    from pyfigures.self_test import _check_video
    _without(monkeypatch, 'libx264', 'h264_mf')
    if _usable('h264_videotoolbox'):
        assert _check_video(str(tmp_path)).endswith(', h264_videotoolbox)')
    else:
        with pytest.raises(AssertionError, match='no H.264 encoder'):
            _check_video(str(tmp_path))


def test_without_any_h264_encoder_the_self_test_fails(tmp_path, monkeypatch):
    from pyfigures.self_test import _check_video
    _without(monkeypatch, 'libx264', *SYSTEM_H264)
    with pytest.raises(AssertionError, match='no H.264 encoder'):
        _check_video(str(tmp_path))


def test_chat_videos_choose_the_same_encoder(monkeypatch):
    from pyfigures.assistant import chat_video as V
    assert V.h264_encoder() in ('libx264',) + SYSTEM_H264
    _without(monkeypatch, 'libx264', *SYSTEM_H264)
    with pytest.raises(RuntimeError, match='No H.264 encoder'):
        V.h264_encoder()


class _Picture:
    """Stands for a grabbed QImage: save(path, 'PNG')."""

    def __init__(self, colour, size=(301, 181)):
        from PIL import Image
        self.image = Image.new('RGB', size, colour)

    def save(self, path, fmt):
        self.image.save(path)
        return True


def test_a_chat_video_mp4_with_an_encoder_that_takes_a_bit_rate(tmp_path, monkeypatch):
    """VideoToolbox / Media Foundation take a bit rate, not x264's crf: that branch
    (here with FFmpeg's mpeg4 encoder, present everywhere) writes a playable file."""
    from pyfigures.assistant import chat_video as V
    monkeypatch.setattr(V, 'h264_encoder', lambda out_path='video.mp4': 'mpeg4')
    reel = V.Reel(tmp_path / 'frames')
    reel.add(_Picture((200, 30, 30)), 1.0)
    reel.add(_Picture((30, 30, 200)), 0.5)
    mp4 = V.encode_mp4(reel, tmp_path / 'demo.mp4')
    with av.open(mp4) as c:
        s = c.streams.video[0]
        assert s.codec_context.name == 'mpeg4' and s.codec_context.pix_fmt == 'yuv420p'
        assert 0 < s.codec_context.bit_rate <= 0.3 * 1280 * 770 * V.FPS * 1.01
        assert sum(1 for _ in c.decode(video=0)) == reel.frames
