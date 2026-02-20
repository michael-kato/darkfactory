# Spec: Stage 4b — Unity Runtime Validation

## Goal
After import, instantiate each asset in a controlled test scene and validate runtime
rendering characteristics: actual draw call count, batching compatibility, single-pass
instanced stereo rendering support, and shader complexity. Results are appended to the
sidecar manifest.

## Depends On
- `stage4a-unity-import-config.md` (asset must be imported and configured first)
- Unity project with URP, XR Plugin Management installed

## Implementation Context
Unity Editor C# code. Runs in Edit Mode via `EditorApplication.update` loop or a
custom `EditorWindow` / CLI entry point. Test command:
`Unity -batchmode -executeMethod QAPipeline.RuntimeValidator.ValidateAll -logFile -`

## Acceptance Criteria

1. C# class `asscheck_uproj/Assets/Editor/QAPipeline/RuntimeValidator.cs`:
   - Static method `ValidateAll()` — entry point for batch execution
   - Discovers all assets in `Assets/_QA/Manifests/` with `overall_status` of `PASS`
     or `PASS_WITH_FIXES` and no `runtime_validation` field yet
   - Runs `ValidateAsset(string assetPath, string manifestPath)` for each

2. **`ValidateAsset`** workflow:
   - Create a temporary test scene (`EditorSceneManager.NewScene`)
   - Instantiate the asset prefab (or the imported mesh as a `GameObject`)
   - Call `UnityEngine.Rendering.DebugManager` or `UnityEngine.Profiling.Profiler` to
     collect draw call count via `Camera.Render()` + `UnityStats.drawCalls`
   - Check batching: verify `MeshRenderer.staticBatchingEnabled` or
     `GraphicsSettings.currentRenderPipeline` batching support
   - Check single-pass instanced: query each material's shader for
     `STEREO_INSTANCING_ON` keyword support
   - Check shader complexity: use `ShaderUtil.GetShaderActiveSubPrograms` to count
     instruction count; flag shaders exceeding 200 fragment instructions
   - Destroy test scene after validation

3. **Draw call check**:
   - Expected ≤ `performance.draw_call_estimate` from manifest × 1.2 (20% tolerance)
   - Exceeds budget → `CheckStatus.FAIL`
   - Within budget → `CheckStatus.PASS`

4. **Results written back** to the sidecar manifest JSON under a `runtime_validation` key:
   ```json
   {
     "runtime_validation": {
       "draw_calls_actual": 2,
       "draw_calls_estimated": 2,
       "batching_compatible": true,
       "single_pass_instanced": true,
       "shader_complexity_ok": true,
       "status": "PASS"
     }
   }
   ```

5. Assets that fail runtime validation: update manifest `overall_status` to `NEEDS_REVIEW`,
   move to `review_queue_dir` (overwrite if already there as PASS).

6. Log all results to `Debug.Log` with `[QAPipeline:Runtime]` prefix.

## Tests (Unity Edit Mode)
`asscheck_uproj/Assets/Editor/Tests/RuntimeValidatorTests.cs`:
- Asset with 1 material → draw call ≤ 2, check passes
- Mock shader without `STEREO_INSTANCING_ON` → `single_pass_instanced == false`, flagged
- Manifest updated with `runtime_validation` block after validation
- Asset initially `PASS`, runtime fails → manifest `overall_status` updated to `NEEDS_REVIEW`

## Out of Scope
- GPU frame capture / RenderDoc integration (future)
- Mobile VR performance profiling (future)
- Overdraw analysis (future)
