"""Podglądy litofanu bez drukowania: symulacja podświetlenia i relief.

Używane przez interfejs w Jupyterze do podglądu na żywo oraz przez skrypt
generujący grafiki na stronę.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

# Barwa ciepłego podświetlenia LED przechodzącego przez mleczną żywicę,
# od najgrubszego (ciemnego) do najcieńszego (jasnego) miejsca płytki.
_BACKLIGHT_DARK = np.array([26.0, 16.0, 10.0])
_BACKLIGHT_LIGHT = np.array([255.0, 214.0, 156.0])


def _normalized(heights: np.ndarray) -> np.ndarray:
    h = np.asarray(heights, dtype=np.float64)
    span = h.max() - h.min()
    if span <= 0:
        return np.zeros_like(h)
    return (h - h.min()) / span


def render_backlit(heights: np.ndarray, absorption: float = 3.2) -> Image.Image:
    """Symuluje litofan podświetlony od tyłu (prawo Beera-Lamberta).

    Im grubsza żywica, tym mniej światła przechodzi: transmisja maleje
    wykładniczo z grubością. Zwraca obraz RGB w ciepłej barwie LED.
    """
    t = _normalized(heights)
    transmission = np.exp(-absorption * t)
    transmission = (transmission - transmission.min()) / (
        transmission.max() - transmission.min() + 1e-12
    )
    rgb = (
        _BACKLIGHT_DARK[None, None, :]
        + transmission[..., None] * (_BACKLIGHT_LIGHT - _BACKLIGHT_DARK)[None, None, :]
    )
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")


def render_relief(heights: np.ndarray, light_azimuth_deg: float = 315.0,
                  light_elevation_deg: float = 55.0) -> Image.Image:
    """Renderuje niepodświetloną płytkę: matowa żywica z cieniowanym reliefem."""
    h = _normalized(heights)
    gy, gx = np.gradient(h)
    scale = 24.0  # wzmocnienie reliefu, żeby płytki wzór był widoczny
    normal = np.dstack([-gx * scale, -gy * scale, np.ones_like(h)])
    normal /= np.linalg.norm(normal, axis=2, keepdims=True)

    az = np.deg2rad(light_azimuth_deg)
    el = np.deg2rad(light_elevation_deg)
    light = np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])

    shade = np.clip(normal @ light, 0.0, 1.0)
    # Mleczna, lekko bursztynowa żywica w świetle warsztatu.
    base = np.array([233.0, 226.0, 214.0])
    shadow = np.array([148.0, 138.0, 124.0])
    rgb = shadow[None, None, :] + shade[..., None] * (base - shadow)[None, None, :]
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")
