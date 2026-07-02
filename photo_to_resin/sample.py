"""Proceduralne 'zdjęcia' do demo, testów i galerii przykładów.

Dzięki temu repo nie potrzebuje prawdziwych zdjęć, a strona i przykłady
pokazują rzeczywisty output biblioteki. Wszystkie sceny to kompozycje
sylwetka + gradient + poświata — czyli to, co na litofanie wychodzi najlepiej.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def _canvas(width: int, height: int, top: float, bottom: float) -> np.ndarray:
    """Pionowy gradient jasności od `top` (góra kadru) do `bottom` (dół)."""
    y = np.linspace(0.0, 1.0, height)[:, None]
    return np.broadcast_to(top + (bottom - top) * y, (height, width)).copy()


def _glow(img: np.ndarray, cx: float, cy: float, radius: float, strength: float) -> None:
    """Dodaje miękką poświatę wokół punktu (współrzędne 0-1)."""
    h, w = img.shape
    x = np.linspace(0.0, 1.0, w)[None, :]
    y = np.linspace(0.0, 1.0, h)[:, None]
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    img += strength * np.exp(-((dist / radius) ** 2))


def _finish(img: np.ndarray, overlays: list | None = None, blur: float = 1.2) -> Image.Image:
    """Nakłada rysowane sylwetki na tło i wygładza całość."""
    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "L")
    if overlays:
        draw = ImageDraw.Draw(pil)
        for kind, coords, value in overlays:
            fill = int(np.clip(value, 0, 1) * 255)
            if kind == "polygon":
                draw.polygon(coords, fill=fill)
            elif kind == "ellipse":
                draw.ellipse(coords, fill=fill)
            elif kind == "rectangle":
                draw.rectangle(coords, fill=fill)
    return pil.filter(ImageFilter.GaussianBlur(blur))


def make_sample_photo(width: int = 640, height: int = 480, seed: int = 7) -> Image.Image:
    """Góry o świcie: trzy pasma grani, słońce i mgła. Domyślna scena demo."""
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 1.0, width)
    y = np.linspace(0.0, 1.0, height)[:, None]

    img = _canvas(width, height, 0.55, 0.9)
    _glow(img, 0.72, 0.28, 0.09, 0.9)
    _glow(img, 0.72, 0.28, 0.25, 0.25)

    for ridge_base, roughness, shade in [(0.55, 0.06, 0.42), (0.68, 0.10, 0.26), (0.82, 0.15, 0.12)]:
        phases = rng.uniform(0, 2 * np.pi, 5)
        freqs = rng.uniform(2.0, 11.0, 5)
        amps = roughness * rng.uniform(0.3, 1.0, 5) / np.arange(1, 6)
        ridge = ridge_base + sum(a * np.sin(f * 2 * np.pi * x + p) for a, f, p in zip(amps, freqs, phases))
        mask = y > ridge[None, :]
        depth = np.clip((y - ridge[None, :]) * 6.0, 0.0, 1.0)
        img = np.where(mask, shade + (1.0 - depth) * 0.12, img)

    return _finish(img)


def make_lighthouse(width: int = 640, height: int = 480) -> Image.Image:
    """Latarnia morska nocą: snop światła, księżyc i morze po horyzont."""
    w, h = width, height
    img = _canvas(w, h, 0.2, 0.5)
    img[int(0.62 * h):] = _canvas(w, h - int(0.62 * h), 0.42, 0.28)  # morze
    _glow(img, 0.22, 0.18, 0.05, 0.85)   # księżyc
    _glow(img, 0.22, 0.18, 0.16, 0.2)

    # Snop światła z lampy w lewo — rysowany osobno i rozmyty, potem dodany.
    beam = Image.new("L", (w, h), 0)
    ImageDraw.Draw(beam).polygon(
        [(0.66 * w, 0.30 * h), (0.02 * w, 0.20 * h), (0.02 * w, 0.44 * h)], fill=110
    )
    img += np.asarray(beam.filter(ImageFilter.GaussianBlur(6)), dtype=np.float64) / 255.0

    tower = [
        ("polygon", [(0.63 * w, 0.62 * h), (0.69 * w, 0.62 * h),
                     (0.675 * w, 0.30 * h), (0.645 * w, 0.30 * h)], 0.08),
        ("rectangle", [0.638 * w, 0.26 * h, 0.682 * w, 0.30 * h], 0.1),   # laterna
        ("ellipse", [0.648 * w, 0.265 * h, 0.672 * w, 0.29 * h], 0.98),   # lampa
        ("polygon", [(0.63 * w, 0.26 * h), (0.69 * w, 0.26 * h), (0.66 * w, 0.22 * h)], 0.07),
        ("polygon", [(0.52 * w, 0.75 * h), (0.85 * w, 0.78 * h), (0.92 * w, h),
                     (0.5 * w, h)], 0.1),                                  # klif
    ]
    return _finish(img, tower)


def make_cat(width: int = 640, height: int = 480) -> Image.Image:
    """Kot w oknie: sylwetka na tle pełni księżyca, parapet u dołu."""
    w, h = width, height
    img = _canvas(w, h, 0.18, 0.32)
    _glow(img, 0.5, 0.38, 0.22, 0.75)   # księżyc w pełni
    _glow(img, 0.5, 0.38, 0.45, 0.15)

    cat = [
        ("ellipse", [0.36 * w, 0.52 * h, 0.62 * w, 0.86 * h], 0.06),          # tułów
        ("ellipse", [0.40 * w, 0.34 * h, 0.56 * w, 0.56 * h], 0.06),          # głowa
        ("polygon", [(0.415 * w, 0.38 * h), (0.45 * w, 0.36 * h), (0.42 * w, 0.26 * h)], 0.06),
        ("polygon", [(0.545 * w, 0.38 * h), (0.51 * w, 0.36 * h), (0.54 * w, 0.26 * h)], 0.06),
        ("polygon", [(0.60 * w, 0.80 * h), (0.72 * w, 0.72 * h), (0.75 * w, 0.52 * h),
                     (0.71 * w, 0.51 * h), (0.68 * w, 0.68 * h), (0.58 * w, 0.74 * h)], 0.06),  # ogon
        ("rectangle", [0, 0.84 * h, w, h], 0.1),                              # parapet
    ]
    return _finish(img, cat)


def make_sailboat(width: int = 640, height: int = 480) -> Image.Image:
    """Żaglówka o zachodzie: słońce przy horyzoncie i smuga blasku na wodzie."""
    w, h = width, height
    img = _canvas(w, h, 0.4, 0.88)          # niebo jaśnieje ku horyzontowi
    horizon = int(0.58 * h)
    img[horizon:] = _canvas(w, h - horizon, 0.55, 0.3)  # morze
    _glow(img, 0.42, 0.56, 0.08, 0.95)      # słońce tuż nad horyzontem
    _glow(img, 0.42, 0.56, 0.22, 0.3)

    # Smuga słońca na wodzie: pionowy pas, słabnący z głębią.
    x = np.linspace(0.0, 1.0, w)[None, :]
    y = np.linspace(0.0, 1.0, h)[:, None]
    path = np.exp(-(((x - 0.42) / 0.05) ** 2)) * np.clip((y - 0.58) * 4, 0, 1) * 0.35
    img += np.where(y > 0.58, path * np.clip(1.6 - y, 0, 1), 0)

    boat = [
        ("polygon", [(0.60 * w, 0.66 * h), (0.80 * w, 0.66 * h),
                     (0.76 * w, 0.72 * h), (0.63 * w, 0.72 * h)], 0.08),      # kadłub
        ("polygon", [(0.695 * w, 0.64 * h), (0.695 * w, 0.34 * h), (0.62 * w, 0.64 * h)], 0.1),   # grot
        ("polygon", [(0.715 * w, 0.64 * h), (0.715 * w, 0.38 * h), (0.78 * w, 0.64 * h)], 0.12),  # fok
    ]
    return _finish(img, boat)


def make_city(width: int = 640, height: int = 480, seed: int = 21) -> Image.Image:
    """Wieczorna panorama miasta: sylwetki wieżowców i świecące okna."""
    rng = np.random.default_rng(seed)
    w, h = width, height
    img = _canvas(w, h, 0.24, 0.62)
    _glow(img, 0.5, 0.66, 0.5, 0.18)        # łuna nad miastem

    buildings: list = []
    windows: list = []
    x0 = 0.0
    while x0 < 1.0:
        bw = rng.uniform(0.05, 0.11)
        top = rng.uniform(0.30, 0.62)
        buildings.append(("rectangle", [x0 * w, top * h, min(1.0, x0 + bw) * w, h], 0.08))
        for wy in np.arange(top + 0.05, 0.92, 0.055):
            for wx in np.arange(x0 + 0.012, min(1.0, x0 + bw) - 0.015, 0.022):
                if rng.random() < 0.42:
                    windows.append(
                        ("rectangle", [wx * w, wy * h, (wx + 0.008) * w, (wy + 0.018) * h], 0.85)
                    )
        x0 += bw + rng.uniform(0.004, 0.02)

    return _finish(img, buildings + windows, blur=0.8)


#: Sceny galerii przykładów: slug -> (tytuł, generator).
SAMPLES: dict[str, tuple] = {
    "gory-o-swicie": ("Góry o świcie", make_sample_photo),
    "latarnia-morska": ("Latarnia morska", make_lighthouse),
    "kot-w-oknie": ("Kot w oknie", make_cat),
    "zaglowka-o-zachodzie": ("Żaglówka o zachodzie", make_sailboat),
    "wieczorne-miasto": ("Wieczorne miasto", make_city),
}


if __name__ == "__main__":
    for slug, (title, fn) in SAMPLES.items():
        fn().save(f"{slug}.png")
        print(f"Zapisano {slug}.png ({title})")
