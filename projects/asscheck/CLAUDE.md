# asscheck — Project Conventions

## What This Project Is
3D asset QA pipeline for VR games. Validates Blender-exported assets before Unity import.
Checks geometry, UVs, textures, PBR materials, armatures, and scene structure.
Runs headless in CI: no display, no Unity Editor needed for most stages.

## Stack
- **Python 3.x** — pipeline logic (Stages 0–3, Stage 5)
- **Blender 5.0.1** headless — mesh inspection, UV analysis, texture checks, auto-repair
  - Binary: `/opt/blender-5.0.1-linux-x64/blender`
  - Run headless: `blender --background --python <script>.py`
- **C# / Unity 6 / URP** — Stages 4a–4b (import config, runtime validation)
  - Unity project: `asscheck_uproj/`

## Project Layout
```
projects/asscheck/
  pipeline/           Python QA pipeline package (importable without Blender)
    schema.py         Core types: QaReport, StageResult, CheckResult, enums
    report_builder.py Utility for assembling the final QA report
    main.py           Orchestrator: run_checks() ties all stages together
    intake.py         run_intake(config) -> QaReport  (file validation, asset ID)
    geometry.py       check_geometry(ctx, config) -> StageResult
    uv.py             check_uvs(ctx, config) -> StageResult
    texture.py        check_textures(ctx, config) -> StageResult
    pbr.py            check_pbr(ctx, config) -> StageResult
    armature.py       check_armature(ctx, config) -> StageResult
    scene.py          check_scene(ctx, config) -> StageResult
    blender_runner.py run_in_blender(script, args) -> dict  (subprocess helper)
    remediate.py      auto-fix geometry issues
    export.py         export-and-handoff logic
    turntable.py      render turntable images
    ssim_diff.py      perceptual diff between renders
    summary.py        final QA summary report
  tests/              pytest unit tests (schema + intake only, no Blender)
  blender_tests/
    tests.py          All integration tests in one file — run inside Blender
  tools/
    generate_test_assets.py   Procedurally generates known-bad GLBs via Blender bpy
  assets/             GITIGNORED — real binary assets (gltf, glb, fbx, obj, textures)
    known-bad/        Procedurally generated assets, one error each (see below)
  asscheck_uproj/     Unity 6 project (URP)
  specs/              Work items — acceptance criteria, not implementation
  .venv/              Python venv
```

## Asset Directories

### Real Assets (`assets/`) — gitignored, on disk only
Used by integration tests. Skip (do not fail) if directory is missing (CI safety).
| File | Format | Purpose |
|---|---|---|
| `street_lamp_01.gltf` + `.bin` | glTF | Standard env prop |
| `large_iron_gate_left_door.glb` | GLB | Standard prop |
| `tree_small_02_branches.fbx` | FBX | ~114 MB, used for size-limit tests |
| `double_door_standard_01.obj` + `.mtl` | OBJ | Standard prop |

Test files reference assets via:
```python
ASSETS_DIR = Path(__file__).parent.parent / "assets"
```

### Known-Bad Assets (`assets/known-bad/`) — gitignored, procedurally generated
Minimum triangles needed to trigger exactly one check failure. No collateral errors.
Generate or regenerate with:
```
blender --background --python tools/generate_test_assets.py -- projects/asscheck/assets
```

| File | Tris | Error demonstrated |
|---|---|---|
| `non_manifold.glb` | 1 | 3 boundary (non-manifold) edges |
| `degenerate_faces.glb` | 1 | Collinear verts → zero-area face |
| `flipped_normals.glb` | 4 | Tetrahedron with one face winding reversed |
| `loose_geometry.glb` | 2+1vert | Two connected tris + one isolated vertex |
| `overbudget_tris.glb` | 5100 | Exceeds env_prop max (5000 tris) |
| `underbudget_tris.glb` | 1 | Below env_prop min (500 tris) |
| `no_uvs.glb` | 1 | No UV layer present |
| `uvs_out_of_bounds.glb` | 1 | UVs at (2.5, 2.5) — outside [0,1] |
| `uv_overlap.glb` | 2 | Two tris mapped to identical UV space |
| `non_pbr_material.glb` | 1 | Emission shader instead of Principled BSDF |
| `wrong_colorspace_normal.glb` | 1 | Normal map with sRGB (should be Non-Color) |

Design rules for known-bad assets:
- Geometry checks: no UV layer, no material
- UV checks: UV layer present, no material
- Material/PBR checks: material present, minimal geometry

## Test Strategy

### Pure Python Tests (`tests/`) — schema and intake only
Tests for `pipeline/schema.py` (serialization) and `pipeline/intake.py`
(file format/size logic). No Blender dependency. Fast.
Run with: `python -m pytest tests/ -v`

### Integration Tests (`blender_tests/tests.py`) — primary test gate
Real Blender runs against real assets and known-bad GLBs. These are the authoritative
tests for all Stage 1+ pipeline logic. All stage tests live in a single file.

Can be run as:
- Headless: `blender --background --python blender_tests/tests.py`
- GUI: open `blender_tests/tests.py` in Blender Text Editor → `Alt+R`

Test functions skip gracefully if `assets/` is missing.

### Running Tests
```bash
# Full test suite (pytest + blender integration)
./test.sh

# Quick pure-Python only (no Blender)
source .venv/bin/activate && python -m pytest tests/ -v

# Blender integration only
/opt/blender-5.0.1-linux-x64/blender --background --python blender_tests/tests.py

# GUI (interactive, no process spawn — for development iteration)
# Open blender_tests/tests.py in Blender Text Editor → Alt+R
```

## Pipeline Stages & Status

| Stage | Module | Status | Notes |
|---|---|---|---|
| 0-intake | `pipeline/intake.py` | Built | Format, size, asset ID |
| 0-schema | `pipeline/schema.py` | Built | Core types |
| 1a-geometry | `pipeline/geometry.py` | Built | polycount, non_manifold, degenerate, normals, loose |
| 1b-uv | `pipeline/uv.py` | Built | missing uvs, bounds, overlap |
| 1c-texture | `pipeline/texture.py` | Built | resolution, format, colorspace |
| 1d-pbr | `pipeline/pbr.py` | Built | PBR workflow validation |
| 1e-armature | `pipeline/armature.py` | Built | Skeleton checks |
| 1f-scene | `pipeline/scene.py` | Built | Hierarchy and naming |
| 2-remediation | `pipeline/remediate.py` | Built | Auto-fix geometry |
| 3-export | `pipeline/export.py` | Built | Handoff packaging |
| 4a-unity-import | `asscheck_uproj/Assets/Editor/` | Spec only | Unity-side import config |
| 4b-unity-runtime | `asscheck_uproj/Assets/Editor/` | Spec only | Runtime validation |
| 5-visual | `pipeline/turntable.py`, `pipeline/ssim_diff.py`, `pipeline/summary.py` | Built | Turntable render + SSIM |

## Automated Commit Format
- Subject: `[automated] asscheck: <description>`
- Branch: commit directly to current branch — do not create a new branch

## Never Modify
- `asscheck_uproj/Library/`    — Unity generated, gitignored
- `asscheck_uproj/Temp/`       — Unity generated, gitignored
- `.git/`

## Python Conventions
- All QA data flows through types in `pipeline/schema.py` — no ad-hoc dicts
- Validators return `StageResult`, never raw booleans
- `BlenderContext` abstraction separates bpy-specific code from pure logic
- File paths in specs are relative to `projects/asscheck/`
- Unity C#: namespace `QAPipeline`, scripts in `asscheck_uproj/Assets/Editor/QAPipeline/`
