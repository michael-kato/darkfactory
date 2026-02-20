# Spec: Stage 1f — Scene & Hierarchy Checks + Performance Estimates

## Goal
Validate scene-level conventions: object naming, orphan data, LOD and collision mesh
presence. Then compute performance estimates (draw calls, VRAM, bone/skinning cost)
and store them in the QA report's `performance` field.

## Depends On
- `stage0-qa-schema.md`
- `stage1a-geometry-checks.md` (BlenderContext pattern)
- `stage1c-texture-checks.md` (VRAM estimate needs texture resolution data)

## Acceptance Criteria

1. Module `pipeline/stage1/scene.py` exports `check_scene(context: BlenderContext, config: SceneConfig) -> tuple[StageResult, PerformanceEstimates]`.

2. **`SceneConfig` dataclass**:
   ```python
   @dataclass
   class SceneConfig:
       object_naming_pattern: str        # regex, e.g. r"^[A-Z]{2,4}_[A-Za-z0-9_]+$"
       require_lod: bool                 # True if LODs are required for this category
       require_collision: bool           # True if collision mesh required
       lod_suffix_pattern: str           # regex matching LOD object names, e.g. r"_LOD\d+$"
       collision_suffix_pattern: str     # regex matching collision objects, e.g. r"_Collision$"
   ```

3. **Scene checks**:

   | Check name | Logic | Fail condition |
   |---|---|---|
   | `naming_conventions` | All mesh objects must match `object_naming_pattern`. | Count of non-matching objects > 0 (WARNING) |
   | `orphan_data` | `bpy.data.meshes`, `bpy.data.materials`, `bpy.data.images` with `users == 0`. | Count > 0 (WARNING) |
   | `lod_presence` | If `require_lod`: at least one object name matches `lod_suffix_pattern`. Expect _LOD0, _LOD1 at minimum. | Missing when required (FAIL) |
   | `collision_presence` | If `require_collision`: at least one object name matches `collision_suffix_pattern`. | Missing when required (FAIL) |

4. **Performance estimates** computed and returned as `PerformanceEstimates`:
   - `triangle_count`: sum of triangle counts across all mesh objects (integer)
   - `draw_call_estimate`: count of unique (mesh, material_slot) pairs across all objects
   - `vram_estimate_mb`: sum over all unique images of `(width × height × channels × bit_depth) / 8 / 1024 / 1024 × mip_multiplier` where `mip_multiplier = 4/3`
   - `bone_count`: total bones across all armatures (0 if none)

5. `naming_conventions` and `orphan_data` are `CheckStatus.WARNING` (human review, not auto-fail).
   `lod_presence` and `collision_presence` are `CheckStatus.FAIL` when violated.

6. Returns `(StageResult(name="scene", ...), PerformanceEstimates(...))`.

7. Caller (pipeline orchestrator) stores the `PerformanceEstimates` in the report via
   `ReportBuilder.set_performance(...)`.

## Tests

**Unit tests** (`tests/test_stage1f_scene.py`) — mock bpy data with simple dataclasses:
- All objects named `ENV_Crate_Large` with pattern `r"^[A-Z]{2,4}_[A-Za-z0-9_]+"` → `naming_conventions` passes
- Object named `crate` with above pattern → `naming_conventions` warns
- 2 orphan materials → `orphan_data` warns with `measured_value == 2`
- `require_lod=True`, no object matching `_LOD\d+$` → `lod_presence` fails
- `require_lod=False` → `lod_presence` skipped
- VRAM estimate: one 2048×2048 RGBA 8-bit image → ~16MB × 4/3 = ~21.3 MB
- Draw call estimate: 2 objects, each with 2 material slots → estimate = 4
- `require_collision=True`, no `_Collision` object → `collision_presence` fails

**Integration test** (`blender_tests/test_stage1f_blender.py`):
- Load sample glTF, run scene check, verify `PerformanceEstimates` fields are non-negative numbers

## Out of Scope
- Actual GPU profiling (Unity does this in stage4b)
- LOD quality comparison (future, requires Hausdorff distance)
- Collision mesh validity (geometry is verified; mesh existence only here)
