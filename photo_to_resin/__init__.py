"""photo-to-resin: zamień zdjęcie w litofan STL dla drukarki żywicznej."""

from photo_to_resin.core import (
    LithophaneParams,
    heightmap_to_triangles,
    image_to_heightmap,
    load_image,
    photo_to_stl,
    write_binary_stl,
)
from photo_to_resin.preview import render_backlit, render_relief

__version__ = "0.1.0"

__all__ = [
    "LithophaneParams",
    "heightmap_to_triangles",
    "image_to_heightmap",
    "load_image",
    "photo_to_stl",
    "write_binary_stl",
    "render_backlit",
    "render_relief",
    "__version__",
]
