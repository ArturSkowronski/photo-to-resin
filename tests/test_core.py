"""Testy rdzenia: poprawność mapy wysokości, szczelność bryły, format STL."""

import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from photo_to_resin import (
    LithophaneParams,
    heightmap_to_triangles,
    image_to_heightmap,
    photo_to_stl,
)
from photo_to_resin.sample import make_sample_photo


def test_heightmap_range_and_size():
    params = LithophaneParams(width_mm=40, pixels_per_mm=2, frame_mm=0)
    heights, px = image_to_heightmap(make_sample_photo(320, 240), params)
    assert abs(px - 0.5) < 1e-9
    assert heights.shape[1] == 80
    assert heights.min() >= params.min_thickness_mm - 1e-9
    assert heights.max() <= params.max_thickness_mm + 1e-9
    # Ciemne góry na dole kadru muszą być grubsze niż jasne niebo u góry.
    assert heights[-10:].mean() > heights[:10].mean()


def test_mesh_is_watertight():
    params = LithophaneParams(width_mm=20, pixels_per_mm=2, frame_mm=1)
    heights, px = image_to_heightmap(make_sample_photo(160, 120), params)
    tris = heightmap_to_triangles(heights, px)

    # Każda krawędź zamkniętej bryły należy do dokładnie dwóch trójkątów.
    verts = tris.reshape(-1, 3)
    _, inverse = np.unique(verts.round(6), axis=0, return_inverse=True)
    idx = inverse.reshape(-1, 3)
    edges = np.concatenate([idx[:, [0, 1]], idx[:, [1, 2]], idx[:, [2, 0]]])
    edges_sorted = np.sort(edges, axis=1)
    _, counts = np.unique(edges_sorted, axis=0, return_counts=True)
    assert (counts == 2).all(), "siatka nie jest szczelna"

    # Objętość ze znakiem musi być dodatnia i równa dokładnej całce
    # z triangulowanej mapy wysokości (pryzmy nad trójkątami (a,b,d)/(a,d,c)).
    v = tris.astype(np.float64)
    volume = np.einsum("ij,ij->i", v[:, 0], np.cross(v[:, 1], v[:, 2])).sum() / 6.0
    z = heights
    expected = (px * px / 6.0) * (
        2 * z[:-1, :-1] + z[:-1, 1:] + z[1:, :-1] + 2 * z[1:, 1:]
    ).sum()
    assert volume > 0
    assert abs(volume - expected) / expected < 1e-6


def test_stl_file_structure(tmp_path):
    params = LithophaneParams(width_mm=15, pixels_per_mm=2)
    out = photo_to_stl(make_sample_photo(80, 60), tmp_path / "demo.stl", params)
    data = out.read_bytes()
    (count,) = struct.unpack("<I", data[80:84])
    assert len(data) == 84 + count * 50
    assert count > 0


if __name__ == "__main__":
    import tempfile

    test_heightmap_range_and_size()
    test_mesh_is_watertight()
    with tempfile.TemporaryDirectory() as td:
        test_stl_file_structure(Path(td))
    print("Wszystkie testy przeszły.")
