"""Interfejs photo-to-resin dla Jupytera: suwaki zamiast kodu.

Użycie w notebooku:

    from photo_to_resin.notebook import launch
    launch()
"""

from __future__ import annotations

import io
import time
from pathlib import Path

import ipywidgets as w
from IPython.display import display
from PIL import Image

from photo_to_resin.core import (
    LithophaneParams,
    heightmap_to_triangles,
    image_to_heightmap,
    write_binary_stl,
)
from photo_to_resin.preview import render_backlit, render_relief
from photo_to_resin.sample import make_sample_photo

_PREVIEW_MAX_PPMM = 2.0  # podgląd liczymy na zgrubnej siatce, żeby był płynny
_STL_BYTES_PER_TRIANGLE = 50


def _png_bytes(img: Image.Image, max_width: int = 460) -> bytes:
    if img.width > max_width:
        img = img.resize((max_width, round(img.height * max_width / img.width)))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _uploaded_image(upload: w.FileUpload) -> Image.Image | None:
    if not upload.value:
        return None
    item = upload.value[0]  # ipywidgets >= 8
    return Image.open(io.BytesIO(bytes(item["content"])))


def launch(output_dir: str | Path = ".") -> w.Widget:
    """Buduje i wyświetla panel sterowania litofanem. Zwraca główny widget."""
    output_dir = Path(output_dir)

    upload = w.FileUpload(accept="image/*", multiple=False, description="Zdjęcie")
    width = w.FloatSlider(value=80, min=20, max=200, step=5, description="Szerokość", readout_format=".0f")
    thickness = w.FloatRangeSlider(
        value=(0.6, 2.8), min=0.2, max=4.0, step=0.1, description="Grubość", readout_format=".1f"
    )
    resolution = w.FloatSlider(value=4, min=1, max=10, step=0.5, description="Rozdz. px/mm", readout_format=".1f")
    frame = w.FloatSlider(value=2, min=0, max=8, step=0.5, description="Ramka", readout_format=".1f")
    gamma = w.FloatSlider(value=1.0, min=0.4, max=2.5, step=0.05, description="Gamma", readout_format=".2f")
    invert = w.Checkbox(value=True, description="Negatyw (klasyczny litofan)")
    filename = w.Text(value="litofan.stl", description="Plik STL")
    generate = w.Button(description="Generuj STL", button_style="success", icon="cube")
    status = w.HTML()
    estimate = w.HTML()

    preview_lit = w.Image(format="png", width=460)
    preview_raw = w.Image(format="png", width=460)

    for slider in (width, thickness, resolution, frame, gamma):
        slider.style.description_width = "110px"
        slider.continuous_update = False

    def current_params(pixels_per_mm: float) -> LithophaneParams:
        return LithophaneParams(
            width_mm=width.value,
            min_thickness_mm=thickness.value[0],
            max_thickness_mm=thickness.value[1],
            pixels_per_mm=pixels_per_mm,
            frame_mm=frame.value,
            gamma=gamma.value,
            invert=invert.value,
        )

    def current_image() -> Image.Image:
        return _uploaded_image(upload) or make_sample_photo()

    def refresh_preview(_change=None) -> None:
        try:
            img = current_image()
            heights, _ = image_to_heightmap(img, current_params(min(resolution.value, _PREVIEW_MAX_PPMM)))
            preview_lit.value = _png_bytes(render_backlit(heights))
            preview_raw.value = _png_bytes(render_relief(heights))

            full = current_params(resolution.value)
            grid_w = round(full.width_mm * full.pixels_per_mm) + 2 * round(full.frame_mm * full.pixels_per_mm)
            grid_h = round(grid_w * img.height / img.width)
            tri_count = 4 * grid_w * grid_h  # góra + spód, po 2 trójkąty na komórkę
            mb = tri_count * _STL_BYTES_PER_TRIANGLE / 1_000_000
            source = "wgrane zdjęcie" if upload.value else "przykładowy pejzaż (wgraj własne zdjęcie)"
            estimate.value = (
                f"Źródło: <b>{source}</b> &nbsp;|&nbsp; siatka ≈ {grid_w} × {grid_h} px"
                f" &nbsp;|&nbsp; STL ≈ {mb:.1f} MB"
            )
            status.value = ""
        except ValueError as exc:
            status.value = f"<span style='color:#b3261e'>Popraw parametry: {exc}</span>"

    def on_generate(_button) -> None:
        status.value = "Generuję pełną siatkę…"
        try:
            started = time.perf_counter()
            heights, px = image_to_heightmap(current_image(), current_params(resolution.value))
            tris = heightmap_to_triangles(heights, px)
            out = write_binary_stl(tris, output_dir / filename.value)
            mb = out.stat().st_size / 1_000_000
            status.value = (
                f"Zapisano <b>{out.resolve()}</b> — {len(tris):,} trójkątów, {mb:.1f} MB,"
                f" {time.perf_counter() - started:.1f} s"
            )
        except Exception as exc:  # pokaż błąd w panelu zamiast tracebacku
            status.value = f"<span style='color:#b3261e'>Nie udało się zapisać STL: {exc}</span>"

    for control in (width, thickness, resolution, frame, gamma, invert, upload):
        control.observe(refresh_preview, names="value")
    generate.on_click(on_generate)

    controls = w.VBox(
        [
            upload,
            width,
            thickness,
            resolution,
            frame,
            gamma,
            invert,
            filename,
            generate,
            status,
        ],
        layout=w.Layout(min_width="360px"),
    )
    previews = w.VBox(
        [
            w.HTML("<b>Podświetlony (symulacja)</b>"),
            preview_lit,
            w.HTML("<b>Bez podświetlenia (relief)</b>"),
            preview_raw,
            estimate,
        ]
    )
    panel = w.HBox([controls, previews], layout=w.Layout(gap="24px"))

    refresh_preview()
    display(panel)
    return panel
