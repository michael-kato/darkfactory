# Spec: Stage 3 — Export & Handoff

## Goal
Export the remediated Blender scene as FBX or glTF with Unity-compatible settings,
write the JSON sidecar manifest containing the full QA report, compute the overall
pipeline status, and route the asset to the correct output queue
(Unity drop folder, human review queue, or quarantine).

## Depends On
- `stage0-qa-schema.md` (QaReport, OverallStatus)
- `stage0-intake-triage.md`
- All Stage 1 specs
- `stage2-auto-remediation.md`

## Acceptance Criteria

1. Module `pipeline/stage3/export.py` exports `run_export(context: BlenderContext, report_builder: ReportBuilder, config: ExportConfig) -> tuple[StageResult, QaReport]`.

2. **`ExportConfig` dataclass**:
   ```python
   @dataclass
   class ExportConfig:
       format: Literal["fbx", "gltf"]   # default "gltf"
       output_dir: str                   # base output directory
       unity_drop_dir: str              # path to Unity Assets/ drop folder
       review_queue_dir: str            # path for NEEDS_REVIEW assets
       quarantine_dir: str              # path for FAIL assets
       embed_textures: bool             # default False (reference via relative paths)
   ```

3. **Export settings applied** (must match section 7.1 of design doc):
   - Axis: Forward `-Z`, Up `Y`
   - Scale: `1.0` (1 unit = 1 meter; apply unit scale)
   - Apply all modifiers on export
   - glTF: use `bpy.ops.export_scene.gltf(...)` with `export_format='GLTF_SEPARATE'`
     (textures as external files) or `'GLB'` when `embed_textures=True`
   - FBX: use `bpy.ops.export_scene.fbx(...)` with compatible Unity settings

4. **Output file path**: `{output_dir}/{asset_id}/{asset_id}.{format}`

5. **Sidecar manifest**: written to `{output_dir}/{asset_id}/{asset_id}_qa.json`.
   The manifest is the serialized `QaReport` dict (via `QaReport.to_dict()`).
   It must include all fields described in section 13 of the design doc.

6. **Overall status computation** (via `ReportBuilder.finalize()`):
   - `FAIL`: any stage result is `StageStatus.FAIL`
   - `NEEDS_REVIEW`: any `ReviewFlag` present and no stage failure
   - `PASS_WITH_FIXES`: any `FixEntry` logged, no failures, no review flags
   - `PASS`: all checks pass, no fixes applied, no review flags

7. **Routing** based on `overall_status`:
   - `PASS` or `PASS_WITH_FIXES` → copy exported file and manifest to `unity_drop_dir`
     under the correct subfolder matching the Unity folder hierarchy (section 10 of design doc):
     `{unity_drop_dir}/Art/{CategoryFolder}/{AssetName}/`
   - `NEEDS_REVIEW` → copy to `review_queue_dir/{asset_id}/`
   - `FAIL` → copy to `quarantine_dir/{asset_id}/`

8. **Category to Unity folder mapping**:
   ```python
   CATEGORY_FOLDER = {
       "character": "Characters",
       "env_prop": "Environment/Props",
       "hero_prop": "Environment/Props",
       "vehicle": "Vehicles",
       "weapon": "Weapons",
       "ui": "UI",
   }
   ```

9. **ExportInfo** populated and stored in the report:
   `ExportInfo(format=..., path=<absolute output path>, axis_convention="-Z forward, Y up", scale=1.0)`

10. Returns `(StageResult(name="export", ...), finalised QaReport)`.

## Tests

**Unit tests** (`tests/test_stage3_export.py`) — mock bpy export ops, file system with `tmp_path`:
- `overall_status == PASS` → file copied to `unity_drop_dir`
- `overall_status == NEEDS_REVIEW` → file copied to `review_queue_dir`
- `overall_status == FAIL` → file copied to `quarantine_dir`
- Manifest JSON written alongside exported file
- `QaReport.from_dict(manifest_json) == original_report` (round-trip)
- Category `"character"` → path includes `"Characters/"` in unity_drop_dir
- Category `"env_prop"` → path includes `"Environment/Props/"` in unity_drop_dir
- `ExportInfo.axis_convention` is `"-Z forward, Y up"`

**Integration test** (`blender_tests/test_stage3_blender.py`):
- Full pipeline run: load sample glTF → stage1 → stage2 → stage3
- Assert exported `.gltf` and `_qa.json` files exist in output dir
- Assert manifest is valid JSON matching QaReport schema

## Out of Scope
- Unity import (stage4)
- Version control / asset database integration (future)
- ORM texture packing (future)
