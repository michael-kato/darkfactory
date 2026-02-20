# Spec: Stage 4a — Unity Import Configuration

## Goal
An `AssetPostprocessor` script that fires automatically when an asset lands in the Unity
project. It reads the sidecar manifest, applies import settings matching the asset's
category, configures texture compression for the target VR platform, and maps materials
to the URP shader. All configuration applied is logged back to the manifest.

## Depends On
- `stage3-export-handoff.md` (sidecar manifest format)
- Unity project at `asscheck_uproj/` with URP configured

## Implementation Context
This is Unity Editor C# code. Tests are run via Unity's Test Runner (Edit Mode tests),
not pytest. The test command is: `Unity -batchmode -runTests -testPlatform editmode`.

## Acceptance Criteria

1. C# script `asscheck_uproj/Assets/Editor/QAPipeline/QAAssetPostprocessor.cs` exists.

2. Extends `UnityEditor.AssetPostprocessor`. Hooks `OnPreprocessModel` and
   `OnPreprocessTexture`.

3. **Manifest discovery**: On any model/texture import, check if a sidecar file
   `{assetPath_withoutExtension}_qa.json` exists alongside the imported asset.
   If not found, skip all QA processing (asset is not pipeline-managed).

4. **`OnPreprocessModel`** — reads manifest, applies to `ModelImporter`:
   - Read `metadata.category` from manifest
   - Apply import preset based on category:
     - All categories: `meshCompression = ModelImporterMeshCompression.Off` (preserve geometry)
     - `character`: `importAnimation = true`, `optimizeMesh = true`
     - All others: `importAnimation = false`
   - Set `globalScale = 1.0`
   - Set `useFileUnits = true`
   - If manifest `performance.bone_count > 0`: `optimizeBones = true`

5. **`OnPreprocessTexture`** — reads manifest for the model the texture belongs to
   (match by directory proximity). Applies platform compression:
   - Detect target platform from `EditorUserBuildSettings.activeBuildTarget`
   - PC/StandaloneWindows64, StandaloneLinux64: `BC7` format
   - Android (mobile VR): `ASTC_6x6` format
   - Set `mipmapEnabled = true`, `streamingMipmaps = true`
   - Set `sRGBTexture` based on texture name keywords matching the color space rules
     from `stage1c` (albedo → sRGB; normal/rough/metal/ao → linear)

6. **`OnPostprocessModel`** (after import):
   - Find all materials created by the import. For each:
     - Assign shader `"Universal Render Pipeline/Lit"` if not already assigned
     - Map standard texture slots: `_BaseMap`, `_BumpMap`, `_MetallicGlossMap`,
       `_OcclusionMap` from imported textures by name keyword matching

7. **Lightmap UV**: If `require_lightmap_uv2` was `true` in the manifest (stored as a
   custom field in the QA report), set `ModelImporter.generateSecondaryUV = true`.

8. **Log all applied settings** to `Debug.Log` in a structured format:
   `[QAPipeline] {asset_id} — applied {setting}: {value}`

9. No GUI or menu items — postprocessor only.

## Tests (Unity Edit Mode)
`asscheck_uproj/Assets/Editor/Tests/QAPostprocessorTests.cs`:
- Import a dummy `.gltf` without sidecar → postprocessor does nothing (no errors)
- Import sample asset with a hand-crafted sidecar manifest → `ModelImporter.globalScale == 1.0`
- Manifest category `character` → `importAnimation == true`
- Manifest category `env_prop` → `importAnimation == false`
- Texture name containing `Normal` → `sRGBTexture == false`
- Texture name containing `Albedo` → `sRGBTexture == true`
- Active build target PC → texture format set to BC7

## Out of Scope
- Runtime validation (stage4b)
- Prefab creation (future)
- LOD group setup (future)
