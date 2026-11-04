"""Leica .lif series: 2D series read natively, a wrong series number is an error.

read_lif's getMetadata() expects X, Y and Z and failed on single-plane series
("not enough values to unpack"), and an out-of-range series number made
Bio-Formats open the FIRST series instead, so a panel silently showed another
image. Tested without Java or real .lif files.
"""
from __future__ import annotations

import pytest


class _Dim:
    def __init__(self, dim_id, n, length, unit="m"):
        self._a = {"DimID": str(dim_id), "NumberOfElements": str(n), "Length": str(length), "Unit": unit}

    def getAttribute(self, k):
        return self._a.get(k, "")


class _Serie2D:
    def getMetadata(self):
        raise ValueError("not enough values to unpack (expected 3, got 2)")

    def getDimensions(self):
        return [_Dim(1, 1024, 3.875e-4), _Dim(2, 1024, 3.875e-4)]

    def getChannels(self):
        return [object()]

    def getNbFrames(self):
        return 1


def test_metadata_of_a_2d_series():
    from batoolset.image_reader import _lif_series_metadata
    md = _lif_series_metadata(_Serie2D())
    assert md["voxel_number_x"] == 1024 and md["voxel_number_z"] == 1
    assert md["voxel_size_x"] == pytest.approx(3.875e-4 / 1024 * 1e6)
    assert md["voxel_size_unit"] == "um"
    assert md["channel_number"] == 1


def test_bioformats_refuses_a_series_that_does_not_exist():
    ij_reader = pytest.importorskip("batoolset.IJ.ij_reader", exc_type=ImportError)   # the pyimagej reader (scyjava comes with pyimagej)
    with pytest.raises(IndexError, match="21 series"):
        ij_reader._open_from_opts(None, 21, 21)
    with pytest.raises(IndexError):
        ij_reader._open_from_opts(None, -1, 3)
