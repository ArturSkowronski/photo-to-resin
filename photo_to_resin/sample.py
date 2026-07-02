"""Generuje proceduralne 'zdjęcie' (górski pejzaż ze słońcem) do demo i testów.

Dzięki temu repo nie potrzebuje prawdziwych zdjęć, a strona i przykłady
pokazują rzeczywisty output biblioteki.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter


def make_sample_photo(width: int = 640, height: int = 480, seed: int = 7) -> Image.Image:
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 1.0, width)
    y = np.linspace(0.0, 1.0, height)[:, None]

    # Niebo: pionowy gradient rozjaśniający się ku horyzontowi.
    sky = 0.55 + 0.35 * y

    # Słońce: miękka tarcza w prawej górnej części kadru.
    sun_x, sun_y, sun_r = 0.72, 0.28, 0.09
    dist = np.sqrt((x[None, :] - sun_x) ** 2 + (y - sun_y) ** 2)
    sun = np.exp(-((dist / sun_r) ** 2) * 0.5) * 0.9 + np.exp(-dist * 4.0) * 0.25

    img = np.clip(sky + sun, 0.0, 1.0)

    # Trzy pasma gór: im bliżej, tym ciemniejsze i bardziej postrzępione.
    for ridge_base, roughness, shade in [(0.55, 0.06, 0.42), (0.68, 0.10, 0.26), (0.82, 0.15, 0.12)]:
        phases = rng.uniform(0, 2 * np.pi, 5)
        freqs = rng.uniform(2.0, 11.0, 5)
        amps = roughness * rng.uniform(0.3, 1.0, 5) / np.arange(1, 6)
        ridge = ridge_base + sum(a * np.sin(f * 2 * np.pi * x + p) for a, f, p in zip(amps, freqs, phases))
        mask = y > ridge[None, :]
        # Lekka mgła: dalsze partie gór jaśnieją przy grani.
        depth = np.clip((y - ridge[None, :]) * 6.0, 0.0, 1.0)
        img = np.where(mask, shade + (1.0 - depth) * 0.12, img)

    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "L")
    return pil.filter(ImageFilter.GaussianBlur(1.2))


if __name__ == "__main__":
    make_sample_photo().save("sample_photo.png")
    print("Zapisano sample_photo.png")
