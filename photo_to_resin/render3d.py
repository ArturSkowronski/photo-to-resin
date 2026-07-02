"""Widok 3D litofanu (matplotlib) — do galerii i podglądu w notebooku.

Wymaga matplotliba, czyli instalacji z ekstrasem: pip install -e ".[notebook]".
Grubość płytki (max ~3 mm przy szerokości ~100 mm) jest w prawdziwej skali
niewidoczna, więc widok przewyższa oś Z — współczynnik podajemy jawnie
i opisujemy w podpisie na stronie.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image


def render_stl_view(
    heights: np.ndarray,
    pixel_size_mm: float,
    z_exaggeration: float = 5.0,
    max_grid: int = 220,
    elev: float = 58.0,
    azim: float = -66.0,
) -> Image.Image:
    """Renderuje mapę wysokości jako bryłę 3D w barwie mlecznej żywicy."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource, LinearSegmentedColormap

    h = np.asarray(heights, dtype=np.float64)
    step = max(1, int(np.ceil(max(h.shape) / max_grid)))
    h = h[::step, ::step]
    rows, cols = h.shape
    xs = np.arange(cols) * pixel_size_mm * step
    ys = (rows - 1 - np.arange(rows)) * pixel_size_mm * step  # jak w heightmap_to_triangles
    X, Y = np.meshgrid(xs, ys)

    resin = LinearSegmentedColormap.from_list(
        "zywica", [(0.32, 0.26, 0.19), (0.62, 0.55, 0.45), (0.93, 0.89, 0.81)]
    )
    ls = LightSource(azdeg=315, altdeg=55)
    rgb = ls.shade(h, cmap=resin, blend_mode="soft", vert_exag=40.0)

    fig = plt.figure(figsize=(6.4, 5.0), dpi=140)
    ax = fig.add_subplot(projection="3d")
    ax.plot_surface(X, Y, h, facecolors=rgb, rstride=1, cstride=1,
                    linewidth=0, antialiased=False, shade=False)
    ax.set_zlim(0, h.max())
    x_extent = cols * pixel_size_mm * step
    y_extent = rows * pixel_size_mm * step
    ax.set_box_aspect((x_extent, y_extent, z_exaggeration * h.max()))
    ax.set_axis_off()
    ax.view_init(elev=elev, azim=azim)
    fig.tight_layout(pad=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGBA")
