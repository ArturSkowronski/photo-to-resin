"""Etap 3-4 pipeline'u figurkowego: wizualizacja -> siatka 3D -> STL -> render.

Uruchamiany interpreterem venv3d (z zainstalowanym TripoSR):
    venv3d/bin/python scripts/figurki_3d.py

Zmienna TRIPOSR_DIR wskazuje klon repo TripoSR. Dla każdej wizualizacji
site/figurki/<slug>-wizualizacja.png powstaje:
    <slug>-figurka.stl   siatka przeskalowana do ~90 mm wysokości (PRD: 85-95)
    <slug>-render.png    render przodu
    <slug>-render-bok.png render 3/4 z boku
oraz manifest-3d.json. Istniejące pliki są pomijane (wznawialność).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "figurki"
TRIPOSR_DIR = Path(os.environ["TRIPOSR_DIR"])

TARGET_HEIGHT_MM = 90.0  # PRD: figurka ~85-95 mm

TITLES = {
    "mala-czarodziejka": "Mała czarodziejka",
    "rycerz-z-kartonu": "Rycerz z kartonu",
    "baletnica": "Baletnica",
    "pies-superbohater": "Pies superbohater",
    "maly-astronauta": "Mały astronauta",
}


def generate_mesh(viz_png: Path, workdir: Path) -> Path:
    """Odpala TripoSR na wizualizacji, zwraca ścieżkę mesh.obj."""
    cmd = [
        sys.executable, str(TRIPOSR_DIR / "run.py"), str(viz_png),
        "--output-dir", str(workdir),
        "--model-save-format", "obj",
        "--device", os.environ.get("TRIPOSR_DEVICE", "cpu"),
        "--mc-resolution", os.environ.get("TRIPOSR_MC_RES", "320"),
    ]
    subprocess.run(cmd, check=True, cwd=TRIPOSR_DIR)
    mesh = workdir / "0" / "mesh.obj"
    if not mesh.exists():
        raise FileNotFoundError(f"TripoSR nie zapisał {mesh}")
    return mesh


def _repair_watertight(mesh):
    """Domyka siatkę pymeshfixem; bez usuwania małych komponentów (detale!)."""
    import pymeshfix
    import trimesh

    for kwargs in ({"remove_smallest_components": False}, {}):
        fixer = pymeshfix.MeshFix(np.asarray(mesh.vertices), np.asarray(mesh.faces))
        fixer.repair(**kwargs)
        fixed = trimesh.Trimesh(fixer.points, fixer.faces)
        if fixed.is_watertight:
            return fixed
    return mesh  # nie udało się — manifest pokaże watertight: false


def to_print_scale(mesh):
    """Skaluje figurkę do TARGET_HEIGHT_MM, stawia na z=0 i domyka podstawę.

    TripoSR zwraca modele już w z-up (podstawka przy z-min, przód w +y) —
    sprawdzone empirycznie na wygenerowanych siatkach.
    """
    mesh.merge_vertices()
    mesh.fill_holes()  # marching cubes zostawia otwartą podstawę na granicy siatki
    if not mesh.is_watertight:
        mesh = _repair_watertight(mesh)
    extent = mesh.bounds[1] - mesh.bounds[0]
    mesh.apply_scale(TARGET_HEIGHT_MM / extent[2])
    mesh.apply_translation(-mesh.bounds[0])
    center = (mesh.bounds[0] + mesh.bounds[1]) / 2
    mesh.apply_translation([-center[0], -center[1], 0])
    return mesh


def render_views(mesh, front_png: Path, side_png: Path) -> None:
    """Renderuje siatkę w barwie mlecznej żywicy (matplotlib, bez GPU)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    render_mesh = mesh
    if len(mesh.faces) > 60_000:
        try:
            render_mesh = mesh.simplify_quadric_decimation(face_count=60_000)
        except BaseException:
            pass  # bez decymacji będzie tylko wolniej

    tri = render_mesh.vertices[render_mesh.faces]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    normals /= np.linalg.norm(normals, axis=1, keepdims=True) + 1e-12

    # Empirycznie: twarze figurek TripoSR patrzą w okolice azymutu -40.
    for path, azim in ((front_png, -40), (side_png, -90)):
        light = np.array([np.cos(np.deg2rad(azim - 40)), np.sin(np.deg2rad(azim - 40)), 0.8])
        light /= np.linalg.norm(light)
        shade = np.clip(normals @ light, 0.05, 1.0)
        base = np.array([0.93, 0.89, 0.81])
        shadow = np.array([0.36, 0.31, 0.24])
        colors = shadow + shade[:, None] * (base - shadow)

        fig = plt.figure(figsize=(5.4, 6.4), dpi=130)
        ax = fig.add_subplot(projection="3d")
        coll = Poly3DCollection(tri, facecolors=colors, edgecolors="none")
        ax.add_collection3d(coll)
        lo, hi = render_mesh.bounds
        span = (hi - lo).max()
        mid = (hi + lo) / 2
        ax.set_xlim(mid[0] - span / 2, mid[0] + span / 2)
        ax.set_ylim(mid[1] - span / 2, mid[1] + span / 2)
        ax.set_zlim(0, span)
        ax.set_box_aspect((1, 1, 1))
        ax.set_axis_off()
        ax.view_init(elev=8, azim=azim)
        fig.tight_layout(pad=0)
        fig.savefig(path, transparent=True, bbox_inches="tight", pad_inches=0)
        plt.close(fig)
        print(f"  zapisano {path.name}")


def main() -> int:
    import trimesh

    manifest = []
    for slug, title in TITLES.items():
        viz = OUT / f"{slug}-wizualizacja.png"
        stl = OUT / f"{slug}-figurka.stl"
        front = OUT / f"{slug}-render.png"
        side = OUT / f"{slug}-render-bok.png"
        if not viz.exists():
            print(f"[{title}] brak {viz.name} — pomijam")
            continue
        print(f"[{title}]")

        if not stl.exists():
            with tempfile.TemporaryDirectory() as td:
                mesh_path = generate_mesh(viz, Path(td))
                mesh = trimesh.load(mesh_path, force="mesh")
            mesh = to_print_scale(mesh)
            mesh.export(stl)
            print(f"  zapisano {stl.name} ({stl.stat().st_size / 1_000_000:.1f} MB)")
        else:
            mesh = trimesh.load(stl, force="mesh")
            print(f"  {stl.name} już istnieje — wczytano")

        if not (front.exists() and side.exists()):
            render_views(mesh, front, side)

        extent = mesh.bounds[1] - mesh.bounds[0]
        manifest.append({
            "slug": slug,
            "title": title,
            "size_mm": [round(float(v), 1) for v in extent],
            "triangles": int(len(mesh.faces)),
            "watertight": bool(mesh.is_watertight),
            "stl_mb": round(stl.stat().st_size / 1_000_000, 2),
        })

    with open(OUT / "manifest-3d.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
