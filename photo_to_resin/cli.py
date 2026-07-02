"""Prosty interfejs wiersza poleceń: photo-to-resin zdjecie.jpg -o litofan.stl"""

from __future__ import annotations

import argparse
from pathlib import Path

from photo_to_resin.core import LithophaneParams, photo_to_stl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="photo-to-resin",
        description="Zamienia zdjęcie w litofan STL gotowy do druku na drukarce żywicznej.",
    )
    parser.add_argument("image", help="ścieżka do zdjęcia (JPG/PNG/...)")
    parser.add_argument("-o", "--output", help="plik wynikowy STL (domyślnie: <zdjęcie>.stl)")
    parser.add_argument("--width", type=float, default=80.0, help="szerokość litofanu w mm (domyślnie 80)")
    parser.add_argument("--min-thickness", type=float, default=0.6, help="grubość w najjaśniejszym miejscu, mm")
    parser.add_argument("--max-thickness", type=float, default=2.8, help="grubość w najciemniejszym miejscu, mm")
    parser.add_argument("--resolution", type=float, default=4.0, help="rozdzielczość siatki, piksele na mm")
    parser.add_argument("--frame", type=float, default=2.0, help="szerokość ramki w mm (0 = bez ramki)")
    parser.add_argument("--gamma", type=float, default=1.0, help="korekcja gamma jasności zdjęcia")
    parser.add_argument("--no-invert", action="store_true",
                        help="nie odwracaj jasności (relief zamiast litofanu)")
    args = parser.parse_args(argv)

    output = Path(args.output) if args.output else Path(args.image).with_suffix(".stl")
    params = LithophaneParams(
        width_mm=args.width,
        min_thickness_mm=args.min_thickness,
        max_thickness_mm=args.max_thickness,
        pixels_per_mm=args.resolution,
        frame_mm=args.frame,
        gamma=args.gamma,
        invert=not args.no_invert,
    )
    path = photo_to_stl(args.image, output, params)
    size_mb = path.stat().st_size / 1_000_000
    print(f"Zapisano {path} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
