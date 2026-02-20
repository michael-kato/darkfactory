# Spec: Stage 1b — UV Checks

## Goal
Analyse UV layouts for all mesh objects in the Blender scene: detect missing UVs,
out-of-bounds islands, overlapping islands, texel density violations, and lightmap
UV2 issues. Append results to the QA report.

## Depends On
- `stage0-qa-schema.md`
- `stage1a-geometry-checks.md` (BlenderContext pattern established)

## Acceptance Criteria

1. Module `pipeline/stage1/uv.py` exports `check_uvs(context: BlenderContext, config: UVConfig) -> StageResult`.

2. **`UVConfig` dataclass**:
   ```python
   @dataclass
   class UVConfig:
       texel_density_target_px_per_m: tuple[float, float]  # (min, max), default (512, 1024)
       require_lightmap_uv2: bool    # default False; True for baked-lighting projects
       uv_layer_name: str            # primary UV layer name, default "UVMap"
       lightmap_layer_name: str      # lightmap UV layer name, default "UVMap2"
   ```

3. **Checks performed**:

   | Check name | Logic | Fail condition |
   |---|---|---|
   | `missing_uvs` | Any mesh object with no UV layers at all. | Count of affected objects > 0 |
   | `uv_bounds` | UV coordinates with U or V outside [0, 1]. Report count of out-of-bounds loops. | Count > 0 |
   | `uv_overlap` | Overlapping UV islands in the primary channel using spatial hashing on triangle bounding boxes followed by exact triangle-triangle intersection test. Intentional overlaps (mirrored symmetry) are NOT auto-distinguished — flag all overlaps. | Overlap count > 0 |
   | `texel_density` | For each UV island: compute (island pixel area in texture space) / (island world-space surface area in m²). Flag islands outside `texel_density_target_px_per_m` range. Report min, max, and mean density as `measured_value`. | Any island outside range |
   | `lightmap_uv2` | If `require_lightmap_uv2` is True: verify `lightmap_layer_name` UV layer exists; verify no overlapping islands in that layer. | Missing layer or overlaps in UV2 |

4. `measured_value` semantics:
   - `missing_uvs`: int (object count)
   - `uv_bounds`: int (loop count)
   - `uv_overlap`: int (overlapping island pair count)
   - `texel_density`: dict `{"min": float, "max": float, "mean": float, "outlier_count": int}`
   - `lightmap_uv2`: dict `{"present": bool, "overlap_count": int}`

5. `texel_density` check status is `WARNING` (not FAIL) when outliers are present — density
   is in the human review queue, not auto-failed (per section 6.2 of design doc).

6. Returns `StageResult(name="uv", ...)`.

## Tests

**Unit tests** (`tests/test_stage1b_uv.py`) — mock UV data as lists of (u, v) coordinates:
- All UVs in [0,1]: `uv_bounds` passes
- A UV at (1.5, 0.5): `uv_bounds` fails, measured_value ≥ 1
- No UV layer on object: `missing_uvs` fails
- Two overlapping triangles in UV space: `uv_overlap` fails
- Texel density in range: `texel_density` warns but does not fail
- Texel density out of range: `texel_density` is `CheckStatus.WARNING` (not FAIL)
- `require_lightmap_uv2=False`: lightmap check is `CheckStatus.SKIPPED`
- `require_lightmap_uv2=True`, no UV2 layer: lightmap check fails

**Integration test** (`blender_tests/test_stage1b_blender.py`):
- Load sample glTF, run UV checks, assert result is valid JSON with no crash

## Out of Scope
- Automatic UV unwrapping or repacking (stage2 handles only what's in the auto-fix list)
- Texel density auto-correction (human review)
- Overlapping UV auto-resolution (human review)
