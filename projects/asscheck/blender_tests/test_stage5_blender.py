#!/usr/bin/env python3
"""Integration test: Stage 5 Blender turntable renderer.

Renders the sample glTF asset with 4 angles (EEVEE, 256×256) and verifies
that 4 valid PNG files are produced.

Run with:
    blender --background --python blender_tests/test_stage5_blender.py

The test exits with code 0 on pass and 1 on failure so that CI can detect it.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Add the project root to sys.path so ``pipeline`` is importable.
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from pipeline.stage5.turntable import TurntableConfig, render_turntable  # noqa: E402

SAMPLE_ASSET = str(
    _project_root / "asscheck_uproj" / "Assets" / "Models" / "street_lamp_01_quant.gltf"
)

_PASS = 0
_FAIL = 1


def test_turntable_renders_four_angles() -> None:
    """Render 4 angles and assert PNG files are created with non-zero size."""
    if not os.path.exists(SAMPLE_ASSET):
        print(f"SKIP: sample asset not found: {SAMPLE_ASSET}", file=sys.stderr)
        return

    config = TurntableConfig(
        num_angles=4,
        engine="EEVEE",
        resolution=(256, 256),
        samples=8,
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        paths = render_turntable(SAMPLE_ASSET, tmp_dir, config)

        if len(paths) != 4:
            raise AssertionError(
                f"Expected 4 render paths, got {len(paths)}: {paths}"
            )

        for p in paths:
            if not os.path.exists(p):
                raise AssertionError(f"Render file not found: {p}")
            size = os.path.getsize(p)
            if size == 0:
                raise AssertionError(f"Render file is empty: {p}")
            print(f"  OK  {p}  ({size} bytes)")

    print("PASS: test_turntable_renders_four_angles")


if __name__ == "__main__":
    try:
        test_turntable_renders_four_angles()
        sys.exit(_PASS)
    except (AssertionError, Exception) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(_FAIL)
