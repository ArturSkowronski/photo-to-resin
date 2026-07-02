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
TRIPOSR_DIR = Path(os.environ["TRIPOSR_DIR"]) if "TRIPOSR_DIR" in os.environ else None

TARGET_HEIGHT_MM = 90.0  # PRD: figurka ~85-95 mm

TITLES = {
    "mala-czarodziejka": "Mała czarodziejka",
    "rycerz-z-kartonu": "Rycerz z kartonu",
    "baletnica": "Baletnica",
    "pies-superbohater": "Pies superbohater",
    "maly-astronauta": "Mały astronauta",
}


def generate_mesh_tripo(viz_png: Path, workdir: Path) -> Path:
    """Generuje siatkę przez Tripo API (image-to-model), zwraca ścieżkę GLB.

    Wymaga TRIPO_API_KEY w środowisku i kredytów API na koncie.
    """
    import time

    import requests

    key = os.environ["TRIPO_API_KEY"]
    headers = {"Authorization": f"Bearer {key}"}
    api = "https://api.tripo3d.ai/v2/openapi"

    cache = ROOT / ".cache" / "figurki" / f"{viz_png.stem}.glb"
    if cache.exists():
        print(f"  tripo: GLB z cache ({cache.name})", flush=True)
        return cache

    with open(viz_png, "rb") as fh:
        up = requests.post(f"{api}/upload/sts", headers=headers,
                           files={"file": (viz_png.name, fh, "image/png")}, timeout=120)
    up.raise_for_status()
    token = up.json()["data"]["image_token"]

    task = requests.post(f"{api}/task", headers=headers, timeout=60, json={
        "type": "image_to_model",
        "file": {"type": "png", "file_token": token},
        "texture": False,   # do druku potrzebna tylko geometria
        "pbr": False,
    })
    task.raise_for_status()
    body = task.json()
    if body.get("code") != 0:
        raise RuntimeError(f"Tripo: {body.get('message')} ({body.get('suggestion', '')})")
    task_id = body["data"]["task_id"]

    while True:
        time.sleep(6)
        st = requests.get(f"{api}/task/{task_id}", headers=headers, timeout=60).json()["data"]
        status = st["status"]
        print(f"  tripo: {status} {st.get('progress', '')}%", flush=True)
        if status == "success":
            url = st["output"].get("model") or st["output"].get("base_model")
            break
        if status in ("failed", "banned", "expired", "cancelled"):
            raise RuntimeError(f"Tripo task {status}")

    data = requests.get(url, timeout=300)
    data.raise_for_status()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(data.content)
    return cache


def generate_mesh(viz_png: Path, workdir: Path) -> Path:
    """Silnik wybiera env FIGURKI_ENGINE: 'tripo' (API) albo TripoSR (domyślnie)."""
    if os.environ.get("FIGURKI_ENGINE") == "tripo":
        return generate_mesh_tripo(viz_png, workdir)
    return generate_mesh_triposr(viz_png, workdir)


def generate_mesh_triposr(viz_png: Path, workdir: Path) -> Path:
    """Odpala TripoSR na wizualizacji, zwraca ścieżkę mesh.obj."""
    if TRIPOSR_DIR is None:
        raise RuntimeError("Ustaw TRIPOSR_DIR (klon repo TripoSR) albo FIGURKI_ENGINE=tripo")
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


def _rotate_up_to_z(mesh):
    """Obraca bryłę do z-up według konwencji silnika.

    Heurystyka "podstawka = największe skupisko wierzchołków" zawodzi
    (rondo kapelusza potrafi wygrać z podstawką), więc konwencja jest
    zadeklarowana wprost: glTF z Tripo to y-up, TripoSR daje z-up.
    """
    import trimesh

    if os.environ.get("FIGURKI_ENGINE") == "tripo":
        mesh.apply_transform(
            trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
        )
    return mesh


def _voxel_remesh(mesh, res: int = 420):
    """Przebudowuje bryłę przez pole odległości ze znakiem + marching cubes.

    Jedyna niezawodna droga dla modeli generatywnych złożonych z dziesiątek
    otwartych, przecinających się powłok (Tripo): pymeshfix i boolean union
    na takim wejściu zawodzą. Zwraca pojedynczą szczelną powłokę.
    """
    import open3d as o3d
    from skimage import measure
    import trimesh

    scene = o3d.t.geometry.RaycastingScene()
    scene.add_triangles(o3d.t.geometry.TriangleMesh.from_legacy(
        o3d.geometry.TriangleMesh(
            o3d.utility.Vector3dVector(mesh.vertices),
            o3d.utility.Vector3iVector(mesh.faces),
        )))
    lo, hi = mesh.bounds
    pad = 0.03 * (hi - lo).max()
    lo, hi = lo - pad, hi + pad
    spacing = (hi - lo).max() / res
    dims = np.ceil((hi - lo) / spacing).astype(int) + 1
    axes = [np.linspace(lo[i], lo[i] + (dims[i] - 1) * spacing, dims[i]) for i in range(3)]
    grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3).astype(np.float32)
    sdf = scene.compute_signed_distance(o3d.core.Tensor(grid)).numpy().reshape(dims)

    verts, faces, _, _ = measure.marching_cubes(sdf, level=0.0, spacing=(spacing,) * 3)
    verts += lo
    out = trimesh.Trimesh(verts, faces)
    return sorted(out.split(only_watertight=False), key=lambda p: len(p.faces))[-1]


def to_print_scale(mesh):
    """Obraca do z-up, skaluje do TARGET_HEIGHT_MM, stawia na z=0, domyka siatkę."""
    mesh.merge_vertices()
    mesh = _rotate_up_to_z(mesh)
    mesh.fill_holes()  # marching cubes zostawia otwartą podstawę na granicy siatki
    if not mesh.is_watertight:
        if mesh.body_count > 1:  # wiele otwartych powłok -> pełny remesh
            mesh = _voxel_remesh(mesh)
            target = int(os.environ.get("FIGURKI_TARGET_FACES", "160000"))
            if len(mesh.faces) > target:
                mesh = mesh.simplify_quadric_decimation(face_count=target)
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
