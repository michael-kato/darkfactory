# Spec: Stage 1e — Armature & Rig Checks

## Goal
Validate armature and skinning data for character and vehicle assets: bone count budgets,
naming conventions, vertex weight validity, bone hierarchy integrity. Non-character assets
without armatures skip this check cleanly.

## Depends On
- `stage0-qa-schema.md`
- `stage1a-geometry-checks.md` (BlenderContext pattern)

## Acceptance Criteria

1. Module `pipeline/stage1/armature.py` exports `check_armature(context: BlenderContext, config: ArmatureConfig) -> StageResult`.

2. **`ArmatureConfig` dataclass**:
   ```python
   @dataclass
   class ArmatureConfig:
       max_bones: int                     # default 75
       max_influences_per_vertex: int     # default 4
       bone_naming_pattern: str | None    # regex; None to skip naming check
       categories_requiring_armature: list[str]  # e.g. ["character"]
   ```

3. **Early exit**: If no armature objects exist in the scene AND the asset category is
   not in `categories_requiring_armature`, return `StageResult(name="armature", status=StageStatus.SKIPPED, ...)`.

4. **If category requires armature but none present**: `CheckStatus.FAIL` on `armature_present` check.

5. **Checks performed** (when armature exists):

   | Check name | Logic | Fail condition |
   |---|---|---|
   | `armature_present` | At least one `bpy.types.Armature` object in scene. | Fail only if category requires it |
   | `bone_count` | `len(armature.bones)` across all armatures. | Total exceeds `max_bones` |
   | `bone_naming` | If `bone_naming_pattern` set: each bone name must match the regex. | Count of non-matching bones > 0 |
   | `vertex_weights` | For each skinned mesh: (a) vertices with zero total weight, (b) vertices with `> max_influences_per_vertex` non-zero groups, (c) vertices where sum of weights ≠ 1.0 ± 0.001. | Any violation in any category |
   | `bone_hierarchy` | Exactly one root bone (no parent) per armature. No orphan bones (bones with no parent and not the designated root). | Multiple roots or orphan bones |

6. `measured_value` semantics:
   - `bone_count`: int
   - `bone_naming`: dict `{"violations": [bone_name, ...], "count": int}`
   - `vertex_weights`: dict `{"zero_weight_count": int, "excess_influences_count": int, "unnormalized_count": int}`
   - `bone_hierarchy`: dict `{"root_count": int, "orphan_count": int}`

7. Returns `StageResult(name="armature", ...)`.

## Tests

**Unit tests** (`tests/test_stage1e_armature.py`) — mock armature and vertex group data:
- No armature, non-character category → `StageStatus.SKIPPED`
- No armature, character category → `armature_present` fails
- 74 bones, max=75 → `bone_count` passes
- 76 bones, max=75 → `bone_count` fails
- Bone name `"mixamorig:Hips"`, pattern `r"^[A-Za-z_][A-Za-z0-9_.]+$"` → naming fails
- Vertex with 0 total weight → `vertex_weights` fails on zero_weight_count
- Vertex with 5 influences, max=4 → `vertex_weights` fails on excess_influences_count
- Weights [0.4, 0.4] (sum=0.8) → `vertex_weights` fails on unnormalized_count
- Two root bones → `bone_hierarchy` fails
- Orphan bone (no parent, not root) → `bone_hierarchy` fails

**Integration test** (`blender_tests/test_stage1e_blender.py`):
- Load sample glTF (no armature), category `env_prop` → expect `SKIPPED`

## Out of Scope
- Bone weight auto-normalization (stage2 handles limit + renormalize as a single fix)
- Retargeting compatibility beyond naming convention check
- Animation data validation (future spec)
