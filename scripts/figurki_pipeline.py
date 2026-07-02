"""Pipeline figurkowy (DziadkoDruk): zdjęcie -> wizualizacja -> model 3D -> render.

Etapy zgodne z PRD Photo-to-STL:
  1. zdjęcie      — gpt-image-1 generuje przykładowe "zdjęcie rodzica" (demo
                    nie używa prawdziwych zdjęć dzieci),
  2. wizualizacja — gpt-image-1 images.edit robi z niego stylizowaną referencję
                    figurki (szara rzeźba, neutralne tło) jak w faza0,
  3. model 3D     — TripoSR (image-to-3D) zamienia referencję w siatkę,
                    scripts/figurki_3d.py,
  4. render + publikacja — sekcja "Figurki" na stronie.

Ten skrypt robi etapy 1-2. Uruchomienie:  .venv/bin/python scripts/figurki_pipeline.py
Wymaga OPENAI_API_KEY w środowisku. Istniejące pliki są pomijane (wznawialność).
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "figurki"

#: Sceny demo: slug -> (tytuł, prompt zdjęcia).
SCENES: dict[str, tuple[str, str]] = {
    "mala-czarodziejka": (
        "Mała czarodziejka",
        "Casual snapshot taken by a parent with a phone: a 5-year-old girl in a "
        "purple witch costume with a pointed hat, joyfully waving a toy magic wand, "
        "standing on a garden lawn in warm evening sunlight, photorealistic, "
        "slightly imperfect framing like a real family photo",
    ),
    "rycerz-z-kartonu": (
        "Rycerz z kartonu",
        "Casual family photo: a 6-year-old boy wearing homemade cardboard knight "
        "armor and helmet, holding a wooden toy sword raised up, proud pose, "
        "backyard with a fence in the background, daylight, photorealistic snapshot",
    ),
    "baletnica": (
        "Baletnica",
        "Casual indoor family photo: a 7-year-old girl in a pink tutu dress "
        "mid-pirouette with arms raised in a living room, natural window light, "
        "photorealistic phone snapshot",
    ),
    "pies-superbohater": (
        "Pies superbohater",
        "Casual photo: a corgi dog wearing a small red superhero cape, sitting "
        "proudly on green grass in a park, golden hour light, photorealistic "
        "phone snapshot",
    ),
    "maly-astronauta": (
        "Mały astronauta",
        "Casual family photo: a 5-year-old child in a white toy astronaut costume "
        "with a round helmet, arms spread like flying, standing in a park, "
        "daylight, photorealistic phone snapshot",
    ),
}

#: Krok 2 — rozwinięcie promptu z faza0/pipeline/visualize.py na całą postać.
VISUALIZATION_PROMPT = (
    "Turn this photo into a clean, stylized reference render of a single "
    "one-piece 3D-printable figurine standing on a small round base: full body, "
    "matte gray clay material like a ZBrush sculpt render, plain light neutral "
    "backdrop, even studio lighting, keep the pose, face and clothing clearly "
    "readable, simplify fragile details so they are printable. This is a "
    "reference for 3D model generation, not a final render."
)


def _save_b64(data: str, path: Path) -> None:
    path.write_bytes(base64.b64decode(data))
    print(f"  zapisano {path.relative_to(ROOT)}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    client = OpenAI()

    for slug, (title, prompt) in SCENES.items():
        print(f"[{title}]")
        photo = OUT / f"{slug}-zdjecie.png"
        viz = OUT / f"{slug}-wizualizacja.png"

        if not photo.exists():
            result = client.images.generate(
                model="gpt-image-1", prompt=prompt, size="1024x1024", quality="medium"
            )
            _save_b64(result.data[0].b64_json, photo)
        else:
            print(f"  {photo.name} już istnieje — pomijam")

        if not viz.exists():
            with open(photo, "rb") as fh:
                result = client.images.edit(
                    model="gpt-image-1", image=fh,
                    prompt=VISUALIZATION_PROMPT, size="1024x1024",
                )
            _save_b64(result.data[0].b64_json, viz)
        else:
            print(f"  {viz.name} już istnieje — pomijam")

    return 0


if __name__ == "__main__":
    sys.exit(main())
