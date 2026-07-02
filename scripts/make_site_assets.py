"""Generuje grafiki na stronę reklamową prawdziwym potokiem photo-to-resin.

Hero strony pokazuje ten sam litofan dwa razy: zgaszony (relief) i podświetlony
(symulacja transmisji światła). Oba obrazy pochodzą z image_to_heightmap,
więc strona reklamuje rzeczywisty output narzędzia, nie mockup.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from photo_to_resin.core import LithophaneParams, image_to_heightmap
from photo_to_resin.preview import render_backlit, render_relief
from photo_to_resin.sample import make_sample_photo


def main() -> None:
    assets = ROOT / "site" / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    photo = make_sample_photo(960, 720)
    params = LithophaneParams(width_mm=120, pixels_per_mm=8, frame_mm=3)
    heights, _ = image_to_heightmap(photo, params)

    photo.convert("RGB").save(assets / "zdjecie.png")
    render_relief(heights).save(assets / "litofan-zgaszony.png")
    render_backlit(heights).save(assets / "litofan-podswietlony.png")
    print(f"Zapisano 3 pliki w {assets}")


if __name__ == "__main__":
    main()
