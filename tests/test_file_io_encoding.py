"""
Regression test: .pyf state files must be written as UTF-8.

read_string_from_file() reads UTF-8, but write_string_to_file() used to open the
file with no encoding, so on Windows it defaulted to cp1252. Any non-ASCII glyph
common in scientific figures (µm, accents, arrows, em dashes, Greek letters)
then raised UnicodeEncodeError on save. Because the autosave runs inside a Qt
debounce-timer slot, that unhandled error made PyQt6 abort the whole app with
0xC0000409 (STATUS_STACK_BUFFER_OVERRUN) — e.g. right after moving a label row.
"""
import os
import tempfile

import pytest

from batoolset.files.tools import write_string_to_file, read_string_from_file


NON_ASCII = 'scale 10 µm — αβγ → “curly” ≥ 5 · é ñ ü ©'


def test_write_read_roundtrip_non_ascii():
    p = os.path.join(tempfile.mkdtemp(), 'roundtrip.pyf')
    write_string_to_file(p, NON_ASCII)
    assert read_string_from_file(p) == NON_ASCII


def test_written_bytes_are_utf8():
    p = os.path.join(tempfile.mkdtemp(), 'bytes.pyf')
    write_string_to_file(p, NON_ASCII)
    with open(p, 'rb') as f:
        raw = f.read()
    # must decode as UTF-8 (would fail / differ if written as cp1252)
    assert raw.decode('utf-8') == NON_ASCII


@pytest.mark.parametrize('ch', ['µ', '—', '→', '≥', 'α', '“', '”', '·'])
def test_each_non_ascii_char_survives(ch):
    p = os.path.join(tempfile.mkdtemp(), 'ch.pyf')
    write_string_to_file(p, ch)   # must not raise UnicodeEncodeError
    assert read_string_from_file(p) == ch
