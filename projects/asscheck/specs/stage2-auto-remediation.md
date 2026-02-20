# Spec: Stage 2 — Auto-Remediation

## Goal
Apply the four deterministic auto-fix actions identified in the design doc. Every change
is logged as a `FixEntry` with before/after values. Issues that cannot be safely
auto-fixed are promoted to `ReviewFlag` entries in the report. The asset must be
modified in-place in the Blender scene before Stage 3 exports it.

## Depends On
- `stage0-qa-schema.md`
- All Stage 1 specs (remediation reads their check results to decide what to fix)

## Acceptance Criteria

1. Module `pipeline/stage2/remediate.py` exports `run_remediation(context: BlenderContext, stage1_results: list[StageResult], config: RemediationConfig) -> StageResult`.

2. **`RemediationConfig` dataclass**:
   ```python
   @dataclass
   class RemediationConfig:
       merge_distance: float           # threshold for merge-by-distance, default 0.0001
       max_bone_influences: int        # hard limit for skinning, default 4
       max_texture_resolution: int     # pixels; auto-resize above this, default 2048
       hero_asset: bool                # if True, use 4096 for texture limit
   ```

3. **Auto-fix actions** (applied only when the corresponding Stage 1 check returned FAIL):

   | Fix | Trigger | Action | Logged fields |
   |---|---|---|---|
   | `recalculate_normals` | `geometry:normal_consistency` FAIL | `bpy.ops.mesh.normals_make_consistent(inside=False)` on all mesh objects | `target`: object name; `before_value`: inconsistent face count; `after_value`: 0 |
   | `merge_by_distance` | `geometry:degenerate_faces` or `geometry:loose_geometry` FAIL | `bpy.ops.mesh.remove_doubles(threshold=merge_distance)` on all mesh objects | `before_value`: original vertex count; `after_value`: post-merge vertex count |
   | `resize_textures` | `texture:resolution_limit` FAIL | For each oversized image: resize with `image.scale(new_w, new_h)` preserving aspect ratio. New size is largest PoT ≤ limit. | `target`: image name; `before_value`: [w, h]; `after_value`: [w, h] |
   | `limit_bone_weights` | `armature:vertex_weights` FAIL (excess influences or unnormalized) | `bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=max_bone_influences)` then `bpy.ops.object.vertex_group_normalize_all()` | `before_value`: max influences before; `after_value`: `max_bone_influences` |

4. **Human review queue** — for each of the following Stage 1 findings, if present,
   add a `ReviewFlag` to the stage result (do NOT modify the scene):
   - `uv:uv_overlap` FAIL → "UV islands overlap; may be intentional (mirroring/tiling)"
   - `pbr:albedo_range` WARNING → "Albedo values outside PBR range; may be stylistic"
   - `pbr:metalness_binary` WARNING → "Metalness gradient detected; verify intent"
   - `pbr:roughness_range` WARNING → "Extreme roughness values; verify intent"
   - `geometry:non_manifold` FAIL → "Non-manifold geometry; requires manual retopology"
   - `geometry:interior_faces` FAIL → "Interior faces; requires manual removal"
   - `uv:texel_density` WARNING → "Texel density outliers; requires artistic judgment"
   - Any polycount FAIL → "Polycount violation; requires manual retopology or LOD"
   - `scene:lod_presence` FAIL → "LODs missing; requires artist to create"

5. After all fixes are applied, re-run geometry and texture checks (call the check
   functions from stage 1, do not re-invoke Blender) to compute updated `measured_value`
   entries that confirm fixes worked. Log updated values in the fix's `after_value`.

6. Returns `StageResult(name="remediation", status=PASS, fixes=[...], review_flags=[...])`.
   Remediation itself does not fail the pipeline — it either fixes or flags.

## Tests

**Unit tests** (`tests/test_stage2_remediation.py`) — mock BlenderContext with controllable ops:
- `normal_consistency` FAIL in stage1 results → `recalculate_normals` fix logged
- `normal_consistency` PASS in stage1 results → no `recalculate_normals` fix applied
- `resolution_limit` FAIL with 4096×4096 image, standard asset → fix logged, after_value is [2048, 2048]
- `resolution_limit` FAIL with 3000×2000 image → fix logged, after_value is [2048, 1024] (largest PoT ≤ 2048)
- `vertex_weights` FAIL → `limit_bone_weights` fix logged
- `uv:uv_overlap` FAIL → ReviewFlag added, no scene modification
- `geometry:non_manifold` FAIL → ReviewFlag added, no scene modification
- All stage1 results PASS → StageResult has empty fixes and empty review_flags

**Integration test** (`blender_tests/test_stage2_blender.py`):
- Load sample glTF, run stage 1 checks, run remediation, verify no crash and result is valid JSON

## Out of Scope
- Decimation/retopology (not safe to automate)
- UV repacking (not safe to automate)
- Spec/gloss to metalness/roughness conversion (future)
- Any fix not listed in section 6.1 of the design doc
