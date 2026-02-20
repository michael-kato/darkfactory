# Spec: Stage 1a — Geometry Checks

## Goal
Analyse mesh geometry inside Blender headless using bpy and bmesh. Detect polycount
violations, non-manifold conditions, degenerate faces, normal inconsistencies, loose
geometry, and interior faces. Append results to the QA report.

## Depends On
- `stage0-qa-schema.md`
- `stage0-intake-triage.md` (report object passed in)
- Blender 3.x or 4.x installed and on PATH as `blender`

## Acceptance Criteria

1. Module `pipeline/stage1/geometry.py` exports `check_geometry(context: BlenderContext, config: GeometryConfig) -> StageResult`.

2. **`GeometryConfig` dataclass**:
   ```python
   @dataclass
   class GeometryConfig:
       triangle_budgets: dict[str, tuple[int, int]]  # category → (min, max) tris
       # defaults: env_prop (500,5000), hero_prop (5000,15000),
       #           character (15000,30000), vehicle (10000,25000)
   ```

3. **`BlenderContext`** is a thin wrapper around a loaded bpy scene (or a mock for testing).
   It exposes `mesh_objects() -> list[MeshObject]` where `MeshObject` has:
   - `name: str`
   - `triangle_count() -> int`
   - `bmesh_get() -> bmesh.types.BMesh`

4. **Checks performed** (each logged as a `CheckResult`):

   | Check name | Logic | Fail condition |
   |---|---|---|
   | `polycount_budget` | Sum triangles across all mesh objects. Compare against `triangle_budgets[category]`. | Total outside (min, max) range |
   | `non_manifold` | `bmesh.edges` where `is_manifold == False`. | Count > 0 |
   | `degenerate_faces` | Faces with `calc_area() < 1e-6` or collinear vertices. | Count > 0 |
   | `normal_consistency` | Faces where normal direction is inconsistent with neighbors (use `FACE_NORMALS` check via bmesh). | Inconsistent face count > 0 |
   | `loose_geometry` | Vertices with no linked faces; edges with no linked faces. | Count > 0 |
   | `interior_faces` | Faces fully enclosed in mesh volume (heuristic: both sides have adjacent faces). | Count > 0 |

5. `measured_value` in each `CheckResult` is the integer count of violations.
   `threshold` is the budget or limit (0 for binary checks).

6. All checks are run even if an earlier check fails (collect all issues, don't short-circuit).

7. Returns a `StageResult(name="geometry", ...)`.

8. Blender integration: `pipeline/stage1/blender_runner.py` exports
   `run_in_blender(script: str, args: list[str]) -> dict` — invokes
   `blender --background --python <script>` and parses stdout JSON.

## Tests

**Unit tests** (`tests/test_stage1a_geometry.py`) — use mock `BlenderContext`:
- A clean mesh (0 violations all checks) → all `CheckStatus.PASS`
- Triangle count above max budget → `CheckStatus.FAIL` on `polycount_budget`
- Triangle count below min → `CheckStatus.FAIL`
- `non_manifold` count = 3 → `CheckStatus.FAIL`, `measured_value == 3`
- Degenerate face present → `CheckStatus.FAIL` on `degenerate_faces`
- All checks run even if polycount fails (no short-circuit)

**Integration test** (`blender_tests/test_stage1a_blender.py`) — run via
`blender --background --python blender_tests/test_stage1a_blender.py`:
- Import `asscheck_uproj/Assets/Models/street_lamp_01_quant.gltf`
- Run full geometry check; assert no crash and result is valid JSON

## Out of Scope
- UV analysis (stage1b)
- Auto-fixing geometry (stage2)
- LOD generation
