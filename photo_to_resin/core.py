"""Rdzeń photo-to-resin: zdjęcie -> mapa wysokości -> siatka 3D -> binarny STL.

Litofan działa na prostej zasadzie: im ciemniejszy piksel zdjęcia, tym grubsza
warstwa żywicy w tym miejscu. Podświetlona od tyłu płytka przepuszcza mniej
światła tam, gdzie jest grubsza, i obraz staje się widoczny.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


@dataclass(frozen=True)
class LithophaneParams:
    """Parametry fizyczne litofanu (wymiary w milimetrach)."""

    width_mm: float = 80.0
    min_thickness_mm: float = 0.6
    max_thickness_mm: float = 2.8
    pixels_per_mm: float = 4.0
    frame_mm: float = 2.0
    gamma: float = 1.0
    blur_radius_px: float = 0.5
    invert: bool = True  # True = ciemny piksel -> gruba żywica (klasyczny litofan)

    def validate(self) -> None:
        if not 10 <= self.width_mm <= 300:
            raise ValueError("width_mm musi być w zakresie 10-300 mm")
        if self.min_thickness_mm < 0.2:
            raise ValueError("min_thickness_mm poniżej 0.2 mm będzie zbyt kruche")
        if self.max_thickness_mm <= self.min_thickness_mm:
            raise ValueError("max_thickness_mm musi być większe niż min_thickness_mm")
        if not 1 <= self.pixels_per_mm <= 12:
            raise ValueError("pixels_per_mm musi być w zakresie 1-12")
        if self.frame_mm < 0:
            raise ValueError("frame_mm nie może być ujemne")
        if self.gamma <= 0:
            raise ValueError("gamma musi być dodatnia")


def load_image(source: str | Path | Image.Image | np.ndarray) -> Image.Image:
    """Wczytuje obraz z pliku, obiektu PIL lub tablicy numpy jako 8-bit grayscale."""
    if isinstance(source, Image.Image):
        img = source
    elif isinstance(source, np.ndarray):
        arr = source
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)
    else:
        img = Image.open(source)
    return img.convert("L")


def image_to_heightmap(
    source: str | Path | Image.Image | np.ndarray,
    params: LithophaneParams = LithophaneParams(),
) -> tuple[np.ndarray, float]:
    """Zamienia obraz na mapę grubości w mm.

    Zwraca (heights, pixel_size_mm), gdzie heights[wiersz, kolumna] to grubość
    żywicy w danym punkcie, a pixel_size_mm to rozmiar jednego piksela siatki.
    """
    params.validate()
    img = load_image(source)

    px_size = 1.0 / params.pixels_per_mm
    target_w = max(2, round(params.width_mm * params.pixels_per_mm))
    target_h = max(2, round(target_w * img.height / img.width))
    img = img.resize((target_w, target_h), Image.LANCZOS)

    if params.blur_radius_px > 0:
        img = img.filter(ImageFilter.GaussianBlur(params.blur_radius_px))

    values = np.asarray(img, dtype=np.float64) / 255.0
    values = values ** params.gamma
    if params.invert:
        values = 1.0 - values

    span = params.max_thickness_mm - params.min_thickness_mm
    heights = params.min_thickness_mm + values * span

    if params.frame_mm > 0:
        border = max(1, round(params.frame_mm * params.pixels_per_mm))
        framed = np.full(
            (heights.shape[0] + 2 * border, heights.shape[1] + 2 * border),
            params.max_thickness_mm,
        )
        framed[border:-border, border:-border] = heights
        heights = framed

    return heights, px_size


def heightmap_to_triangles(heights: np.ndarray, pixel_size_mm: float) -> np.ndarray:
    """Buduje zamkniętą bryłę z mapy wysokości.

    Zwraca tablicę trójkątów (N, 3, 3) w mm: górna powierzchnia odwzorowuje
    obraz, spód jest płaski na z=0, boki domykają bryłę. Oś Y jest odwrócona
    względem wierszy obrazu, żeby litofan oglądany od frontu (+z) nie był
    lustrzanym odbiciem zdjęcia.
    """
    z = np.asarray(heights, dtype=np.float64)
    rows, cols = z.shape
    xs = np.arange(cols) * pixel_size_mm
    ys = (rows - 1 - np.arange(rows)) * pixel_size_mm
    X, Y = np.meshgrid(xs, ys)

    top = np.stack([X, Y, z], axis=-1)
    bottom = np.stack([X, Y, np.zeros_like(z)], axis=-1)

    def grid_quads(pts: np.ndarray, flip: bool) -> np.ndarray:
        a = pts[:-1, :-1].reshape(-1, 3)
        b = pts[:-1, 1:].reshape(-1, 3)
        c = pts[1:, :-1].reshape(-1, 3)
        d = pts[1:, 1:].reshape(-1, 3)
        # Y maleje wraz z indeksem wiersza, więc (a, b, d)/(a, d, c) daje
        # normalne skierowane w -z; flip=True odwraca je w +z (góra bryły).
        t1 = np.stack([a, b, d], axis=1)
        t2 = np.stack([a, d, c], axis=1)
        tris = np.concatenate([t1, t2], axis=0)
        if flip:
            tris = tris[:, ::-1, :]
        return tris

    def wall(top_edge: np.ndarray, bot_edge: np.ndarray, flip: bool) -> np.ndarray:
        t0, t1 = top_edge[:-1], top_edge[1:]
        b0, b1 = bot_edge[:-1], bot_edge[1:]
        q1 = np.stack([t0, b0, b1], axis=1)
        q2 = np.stack([t0, b1, t1], axis=1)
        tris = np.concatenate([q1, q2], axis=0)
        if flip:
            tris = tris[:, ::-1, :]
        return tris

    parts = [
        grid_quads(top, flip=True),
        grid_quads(bottom, flip=False),
        wall(top[0], bottom[0], flip=True),       # górna krawędź obrazu (max Y)
        wall(top[-1], bottom[-1], flip=False),    # dolna krawędź obrazu (Y=0)
        wall(top[:, 0], bottom[:, 0], flip=False),  # lewa (x=0)
        wall(top[:, -1], bottom[:, -1], flip=True),   # prawa (x=max)
    ]
    return np.concatenate(parts, axis=0)


def write_binary_stl(triangles: np.ndarray, path: str | Path, name: str = "photo-to-resin") -> Path:
    """Zapisuje trójkąty (N, 3, 3) jako binarny STL."""
    path = Path(path)
    tris = np.ascontiguousarray(triangles, dtype=np.float32)
    n = len(tris)

    e1 = tris[:, 1] - tris[:, 0]
    e2 = tris[:, 2] - tris[:, 0]
    normals = np.cross(e1, e2)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    np.divide(normals, lengths, out=normals, where=lengths > 0)

    record = np.zeros(
        n,
        dtype=np.dtype(
            [("normal", "<f4", 3), ("vertices", "<f4", (3, 3)), ("attr", "<u2")]
        ),
    )
    record["normal"] = normals
    record["vertices"] = tris

    header = name.encode("ascii", "replace")[:80].ljust(80, b"\0")
    with open(path, "wb") as fh:
        fh.write(header)
        fh.write(struct.pack("<I", n))
        fh.write(record.tobytes())
    return path


def photo_to_stl(
    source: str | Path | Image.Image | np.ndarray,
    output: str | Path,
    params: LithophaneParams = LithophaneParams(),
) -> Path:
    """Pełny potok: zdjęcie -> litofan STL. Zwraca ścieżkę zapisanego pliku."""
    heights, px = image_to_heightmap(source, params)
    triangles = heightmap_to_triangles(heights, px)
    return write_binary_stl(triangles, output)
