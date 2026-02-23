"""Integration test for Stage 5 turntable renderer — runs inside Blender headless.

Usage (headless):  blender --background --python blender_tests/test_stage5_blender.py
Usage (GUI):       Open in Blender Text Editor, press Alt+R

Tests:
  1. Render street_lamp_01.gltf with 4 angles (EEVEE, 256×256).
     Assert 4 PNG files are created with non-zero size.

Skips gracefully if assets/street_lamp_01.gltf is missing.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

ASSETS_DIR = _PROJECT_ROOT / "assets"

import bpy  # noqa: E402

from pipeline.stage5.turntable import TurntableConfig, render_turntable  # noqa: E402


# ---------------------------------------------------------------------------
# Test entry point
# ---------------------------------------------------------------------------

def run_tests() -> dict:
    """Run stage5 turntable render tests. Returns dict with 'passed' key."""
    asset = ASSETS_DIR / "street_lamp_01.gltf"
    if not ASSETS_DIR.exists() or not asset.exists():
        return {"skipped": True, "reason": f"asset not found: {asset}"}

    failures: list[str] = []

    config = TurntableConfig(
        num_angles=4,
        engine="EEVEE",
        resolution=(256, 256),
        samples=8,
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        paths = render_turntable(str(asset), tmp_dir, config)

        if len(paths) != 4:
            failures.append(f"expected 4 render paths, got {len(paths)}: {paths}")
        else:
            for p in paths:
                if not Path(p).exists():
                    failures.append(f"render file not found: {p}")
                elif Path(p).stat().st_size == 0:
                    failures.append(f"render file is empty: {p}")

    return {"passed": len(failures) == 0, "tests_run": 1, "failures": failures}


def _main() -> None:
    r = run_tests()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r.get("passed", r.get("skipped", False)) else 1)


if __name__ == "__main__":
    _main()
