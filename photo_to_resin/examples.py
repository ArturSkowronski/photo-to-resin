"""Pipeline galerii przykładów: zdjęcie -> heightmapa -> STL -> renderingi.

Dla każdej sceny z photo_to_resin.sample.SAMPLES zapisuje w katalogu wyjściowym:
  <slug>-zdjecie.png        wejściowe zdjęcie
  <slug>-podswietlony.png   symulacja litofanu pod światło
  <slug>-relief.png         płytka bez podświetlenia
  <slug>-3d.png             widok 3D siatki (wysokość przewyższona)
  <slug>-litofan.stl        model do druku
oraz manifest.json z parametrami i rozmiarami plików.
"""

from __future__ import annotations

import json
from pathlib import Path

from photo_to_resin.core import (
    LithophaneParams,
    heightmap_to_triangles,
    image_to_heightmap,
    write_binary_stl,
)
from photo_to_resin.preview import render_backlit, render_relief
from photo_to_resin.render3d import render_stl_view
from photo_to_resin.sample import SAMPLES

#: Parametry wydruku dla galerii: 60 mm to rozsądny rozmiar na stół 16K,
#: a 2 px/mm trzyma pliki STL w okolicach 2-3 MB (wersja demonstracyjna).
GALLERY_PARAMS = LithophaneParams(width_mm=60, pixels_per_mm=2.0, frame_mm=2.0)

#: Renderingi liczymy na gęstszej siatce niż STL — obraz ma być ładny,
#: a plik lekki; oba wychodzą z tej samej funkcji image_to_heightmap.
RENDER_PARAMS = LithophaneParams(width_mm=60, pixels_per_mm=8.0, frame_mm=2.0)

Z_EXAGGERATION = 5.0


def build_example(slug: str, out_dir: str | Path = "../site/przyklady") -> dict:
    """Przeprowadza jedną scenę przez cały pipeline. Zwraca wpis manifestu."""
    title, generator = SAMPLES[slug]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    photo = generator()
    photo.convert("RGB").save(out / f"{slug}-zdjecie.png")

    fine, _ = image_to_heightmap(photo, RENDER_PARAMS)
    render_backlit(fine).save(out / f"{slug}-podswietlony.png")
    render_relief(fine).save(out / f"{slug}-relief.png")
    render_stl_view(fine, 1.0 / RENDER_PARAMS.pixels_per_mm,
                    z_exaggeration=Z_EXAGGERATION).save(out / f"{slug}-3d.png")

    heights, px = image_to_heightmap(photo, GALLERY_PARAMS)
    triangles = heightmap_to_triangles(heights, px)
    stl_path = write_binary_stl(triangles, out / f"{slug}-litofan.stl", name=slug)

    plate_w = heights.shape[1] * px
    plate_h = heights.shape[0] * px
    return {
        "slug": slug,
        "title": title,
        "plate_mm": [round(plate_w, 1), round(plate_h, 1)],
        "thickness_mm": [GALLERY_PARAMS.min_thickness_mm, GALLERY_PARAMS.max_thickness_mm],
        "triangles": len(triangles),
        "stl_mb": round(stl_path.stat().st_size / 1_000_000, 2),
    }


def build_all(out_dir: str | Path = "../site/przyklady") -> list[dict]:
    """Cała galeria: pięć scen przez pełny pipeline + manifest.json."""
    manifest = [build_example(slug, out_dir) for slug in SAMPLES]
    with open(Path(out_dir) / "manifest.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    return manifest
