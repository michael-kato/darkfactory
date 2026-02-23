# asscheck

3D asset QA pipeline for VR games. Validates mesh geometry, UVs, textures, PBR materials,
armatures, and scene structure before assets are imported into Unity.

Runs entirely headless: Blender 5.x for 3D analysis, Python for orchestration, Unity CLI for
import and runtime checks.

## Pipeline Overview

```
assets/ (gltf, glb, fbx, obj)
        │
        ▼
Stage 0 — Intake & Triage
  Format validation, file size check, asset ID generation
        │
        ▼
Stage 1 — Analysis (all checks run; results collected even if earlier checks fail)
  1a geometry    polycount budget, non-manifold, degenerate faces, normals, loose geometry
  1b uv          missing UVs, out-of-bounds UVs, UV overlap
  1c texture     resolution, format, colorspace
  1d pbr         Principled BSDF workflow validation
  1e armature    skeleton naming, bone count, bind pose
  1f scene       hierarchy naming, object count, origin placement
        │
        ▼
Stage 2 — Auto-Remediation
  Apply fixes for issues flagged in Stage 1 (where auto-fix is safe)
        │
        ▼
Stage 3 — Export & Handoff
  Package validated asset for Unity import
        │
        ▼
Stage 4 — Unity Integration
  4a import config   AssetPostprocessor settings per category
  4b runtime         Runtime bounds, LOD, collider validation
        │
        ▼
Stage 5 — Visual Verification
  Turntable renders + SSIM diff against approved reference
        │
        ▼
QA Report (JSON)
```

## Quick Start

```bash
cd projects/asscheck

# Create venv and install deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run unit tests (no Blender required)
python -m pytest tests/ -v

# Run integration tests (requires Blender + assets/)
/opt/blender-5.0.1-linux-x64/blender --background --python blender_tests/test_stage1a_blender.py
```

## Running Through the Factory

```bash
# From darkfactory root — run a spec through the AI agent
./invoke.sh projects/asscheck/specs/stage1a-geometry-checks.md

# Resume a checkpointed run
./invoke.sh projects/asscheck/specs/stage1a-geometry-checks.md --resume <session-id>
```

## Spec Execution Order

Specs have dependencies — run them in order:

| Order | Spec file | Builds |
|---|---|---|
| 1 | `stage0-qa-schema.md` | `pipeline/schema.py`, `pipeline/report_builder.py` |
| 2 | `stage0-intake-triage.md` | `pipeline/stage0/intake.py` |
| 3 | `stage1a-geometry-checks.md` | `pipeline/stage1/geometry.py`, `blender_runner.py` |
| 4 | `stage1b-uv-checks.md` | `pipeline/stage1/uv.py` |
| 5 | `stage1c-texture-checks.md` | `pipeline/stage1/texture.py` |
| 6 | `stage1d-pbr-validation.md` | `pipeline/stage1/pbr.py` |
| 7 | `stage1e-armature-checks.md` | `pipeline/stage1/armature.py` |
| 8 | `stage1f-scene-hierarchy.md` | `pipeline/stage1/scene.py` |
| 9 | `stage2-auto-remediation.md` | `pipeline/stage2/remediate.py` |
| 10 | `stage3-export-handoff.md` | `pipeline/stage3/export.py` |
| 11 | `stage4a-unity-import-config.md` | Unity C# scripts |
| 12 | `stage4b-unity-runtime-validation.md` | Unity runtime checks |
| 13 | `stage5-visual-verification.md` | `pipeline/stage5/` |

## Test Assets

### Real Assets (`assets/`) — gitignored
Place production-quality assets here for integration tests. Tests skip gracefully if
this directory doesn't exist, so CI can run unit tests without binary files.

Regenerate known-bad procedural assets:
```bash
/opt/blender-5.0.1-linux-x64/blender --background \
    --python tools/generate_test_assets.py \
    -- projects/asscheck/assets
```

### Known-Bad Assets (`assets/known-bad/`) — gitignored
One GLB per check type. Each file contains the minimum geometry to trigger exactly that
one error and nothing else.

| File | Error |
|---|---|
| `non_manifold.glb` | Non-manifold boundary edges |
| `degenerate_faces.glb` | Zero-area (collinear) face |
| `flipped_normals.glb` | Inconsistent face winding |
| `loose_geometry.glb` | Isolated vertex with no faces |
| `overbudget_tris.glb` | Triangle count above budget |
| `underbudget_tris.glb` | Triangle count below budget |
| `no_uvs.glb` | Missing UV layer |
| `uvs_out_of_bounds.glb` | UVs outside [0, 1] |
| `uv_overlap.glb` | UV islands overlapping |
| `non_pbr_material.glb` | Non-PBR shader (Emission) |
| `wrong_colorspace_normal.glb` | Normal map with sRGB colorspace |

## Project Conventions

See [CLAUDE.md](CLAUDE.md) for the full conventions document including Blender paths,
test commands, code conventions, and pipeline stage status.
