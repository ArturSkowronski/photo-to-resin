"""Pipeline figurkowy (DziadkoDruk): zdjęcie -> wizualizacja -> model 3D -> render.

Etapy zgodne z PRD Photo-to-STL:
  1. zdjęcie      — gpt-image-1 generuje przykładowe "zdjęcie rodzica" (demo
                    nie używa prawdziwych zdjęć dzieci),
  2. wizualizacja — gpt-image-1 images.edit z input_fidelity=high robi z niego
                    realistyczną referencję figurki (szara rzeźba jak skan 3D,
                    zachowane rysy twarzy i proporcje osoby ze zdjęcia),
  3. model 3D     — Tripo API / TripoSR (image-to-3D), scripts/figurki_3d.py,
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

#: Sceny demo: slug -> (tytuł, prompt zdjęcia). Każdy prompt wymusza ostrą,
#: dobrze widoczną twarz i całą postać w kadrze — image-to-3D odwzoruje tylko
#: to, co naprawdę widać na wejściu.
SCENES: dict[str, tuple[str, str]] = {
    "mala-czarodziejka": (
        "Mała czarodziejka",
        "Photorealistic family photo taken with an 85mm lens: a 5-year-old "
        "girl in a purple witch costume with a pointed hat, joyfully waving a "
        "toy magic wand, standing on a garden lawn in warm evening sunlight. "
        "Sharp focus on her face with natural, clearly visible facial "
        "features and skin texture, full body in frame.",
    ),
    "rycerz-z-kartonu": (
        "Rycerz z kartonu",
        "Photorealistic family photo: a 6-year-old boy wearing homemade "
        "cardboard knight armor and helmet with an open face, holding a "
        "wooden toy sword raised up, proud pose, backyard with a fence in the "
        "background, daylight. Sharp focus on his face with natural, clearly "
        "visible facial features, full body in frame.",
    ),
    "baletnica": (
        "Baletnica",
        "Photorealistic family photo: a 7-year-old girl in a pink tutu dress "
        "mid-pirouette with arms raised in a living room, natural window "
        "light. Sharp focus on her face with natural, clearly visible facial "
        "features, full body in frame.",
    ),
    "pies-superbohater": (
        "Pies superbohater",
        "Photorealistic photo: a corgi dog wearing a small red superhero "
        "cape, sitting proudly on green grass in a park, golden hour light. "
        "Sharp focus on the dog's face and fur texture, full body in frame.",
    ),
    "maly-astronauta": (
        "Mały astronauta",
        "Photorealistic family photo: a 5-year-old child in a white toy "
        "astronaut costume with an open round helmet showing the face "
        "clearly, arms spread like flying, standing in a park, daylight. "
        "Sharp focus on the face with natural, clearly visible facial "
        "features, full body in frame.",
    ),
}

#: Krok 2 — realistyczna referencja: proporcje i rysy osoby ze zdjęcia,
#: bez stylizacji chibi/cartoon. input_fidelity=high pilnuje twarzy.
VISUALIZATION_PROMPT = (
    "Turn this photo into a high-fidelity reference render of a single "
    "one-piece 3D-printable figurine standing on a small round base: full "
    "body, realistic human proportions exactly as in the photo (not "
    "stylized, not chibi, not cartoon), preserve the person's actual facial "
    "features, expression, hairstyle and clothing so they are clearly "
    "recognizable — like a detailed 3D scan of the real person. Matte gray "
    "clay material with crisp, sharply defined surface details (folds, hair "
    "strands, facial features), plain light neutral backdrop, even studio "
    "lighting. Exactly one figure and nothing else: no other people, no "
    "hands or objects entering from outside the frame, hands empty unless "
    "the subject clearly holds a prop, the whole figurine fully inside the "
    "frame. This is a reference for 3D model generation, not a final render."
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
                model="gpt-image-1", prompt=prompt, size="1024x1024", quality="high"
            )
            _save_b64(result.data[0].b64_json, photo)
        else:
            print(f"  {photo.name} już istnieje — pomijam")

        if not viz.exists():
            with open(photo, "rb") as fh:
                result = client.images.edit(
                    model="gpt-image-1", image=fh,
                    prompt=VISUALIZATION_PROMPT, size="1024x1024",
                    quality="high",
                    extra_body={"input_fidelity": "high"},
                )
            _save_b64(result.data[0].b64_json, viz)
        else:
            print(f"  {viz.name} już istnieje — pomijam")

    return 0


if __name__ == "__main__":
    sys.exit(main())
