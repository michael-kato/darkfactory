# Spec: Stage 5 — Visual Verification

## Goal
Generate automated visual artefacts for human review: turntable renders from Blender
and a reference-scene screenshot from Unity. If golden reference images exist, compute
a perceptual diff (SSIM) and flag significant deviations. Place all outputs in the QA
report folder for reviewer access. A VR-scale reference scene screenshot is generated
for scale verification — this final gate requires a human to approve.

## Depends On
- `stage3-export-handoff.md` (Blender export must exist)
- `stage4a-unity-import-config.md` (asset must be in Unity project)

## Acceptance Criteria

### Part A — Blender Turntable Renders

1. Module `pipeline/stage5/turntable.py` exports `render_turntable(asset_blend_or_gltf: str, output_dir: str, config: TurntableConfig) -> list[str]` (returns list of rendered image paths).

2. **`TurntableConfig` dataclass**:
   ```python
   @dataclass
   class TurntableConfig:
       num_angles: int       # default 8 (every 45°)
       camera_distance: float  # default 2.5 (in scene units)
       camera_elevation: float # degrees above horizon, default 25.0
       resolution: tuple[int,int]  # default (1024, 1024)
       engine: str           # "EEVEE" or "CYCLES", default "EEVEE"
       samples: int          # default 32
   ```

3. Script runs headless:
   `blender --background --python pipeline/stage5/turntable.py -- <asset_path> <output_dir>`

4. For each angle (0°, 45°, 90°, ... through 360°):
   - Position camera at `camera_distance` from bounding box center, at `camera_elevation`
   - Render to `{output_dir}/{asset_id}_turntable_{angle:03d}.png`

5. A 3-point HDRI-based lighting rig is set up (or a basic sun + fill if no HDRI available).

6. Returns list of rendered image file paths.

### Part B — SSIM Perceptual Diff

7. Module `pipeline/stage5/ssim_diff.py` exports `compare_renders(new_renders: list[str], reference_dir: str) -> list[SSIMResult]`.

8. **`SSIMResult` dataclass**: `angle: int, score: float, diff_image_path: str | None, flagged: bool`

9. If `{reference_dir}/{asset_id}_turntable_{angle:03d}.png` exists: compute SSIM using
   `scikit-image skimage.metrics.structural_similarity`. Score < 0.85 → `flagged=True`.
   Save diff image highlighting changed pixels.

10. If no reference image exists: `score = 1.0`, `flagged = False` (first run establishes the reference).

11. Flagged renders are added as `ReviewFlag` entries in the QA report.

### Part C — Unity Scale Reference Screenshot

12. C# script `asscheck_uproj/Assets/Editor/QAPipeline/ScaleVerificationCapture.cs`:
    - Instantiates the asset in a pre-built reference scene containing a human figure
      (capsule, 1.75m height) and a door frame (2.1m height × 0.9m width)
    - Captures a screenshot via `ScreenCapture.CaptureScreenshotAsTexture()`
    - Saves to `{qa_output_dir}/{asset_id}_scale_reference.png`

13. Scale verification is always marked `NEEDS_REVIEW` (human must confirm) and added
    as a `ReviewFlag` with severity `INFO`:
    `"Scale reference screenshot generated. Human reviewer must verify scale is correct."`

### Part D — QA Output Summary

14. Module `pipeline/stage5/summary.py` exports `write_review_package(report: QaReport, render_paths: list[str], ssim_results: list[SSIMResult], scale_image: str, output_dir: str)` that writes:
    - `{output_dir}/{asset_id}/` containing all render images
    - `{output_dir}/{asset_id}/review_summary.html` — simple HTML page showing:
      - Asset metadata and overall status
      - Turntable renders as an image grid
      - Scale reference screenshot
      - SSIM diff images (if any)
      - All review flags listed

15. `review_summary.html` requires no external CSS frameworks — plain HTML with inline styles.

## Tests

**Unit tests** (`tests/test_stage5.py`):
- SSIM score ≥ 0.85 → `flagged = False`
- SSIM score 0.72 → `flagged = True`
- No reference image → `score == 1.0`, `flagged == False`
- `write_review_package` creates `review_summary.html` with correct title and image tags
- Scale verification adds a ReviewFlag with severity `INFO`

**Integration test** (`blender_tests/test_stage5_blender.py`):
- Render turntable for sample glTF asset (EEVEE, 4 angles for speed)
- Assert 4 PNG files exist and are valid images (non-zero file size)

**Unity test** (`asscheck_uproj/Assets/Editor/Tests/ScaleVerificationTests.cs`):
- `ScaleVerificationCapture.Capture(assetPath)` creates a PNG at the expected path

## Out of Scope
- Machine-learning visual quality scoring (future)
- Automated human review approval (always requires human)
- Video turntable export (future)
