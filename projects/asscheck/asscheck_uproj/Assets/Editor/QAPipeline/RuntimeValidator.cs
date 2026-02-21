using System;
using System.IO;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace QAPipeline
{
    // -----------------------------------------------------------------------
    // Data model — extends the stage-3 manifest for runtime validation fields
    // -----------------------------------------------------------------------

    /// <summary>
    /// Results of runtime validation for a single asset, written back into the
    /// sidecar manifest JSON under the <c>runtime_validation</c> key.
    /// </summary>
    [Serializable]
    public class RuntimeValidationResult
    {
        public int    draw_calls_actual;
        public int    draw_calls_estimated;
        public bool   batching_compatible;
        public bool   single_pass_instanced;
        public bool   shader_complexity_ok;
        public string status = "PASS";
    }

    [Serializable]
    internal class QaManifestRuntimePerf
    {
        public int   draw_call_estimate;
        public int   bone_count;
        public int   triangle_count;
        public float vram_estimate_mb;
    }

    [Serializable]
    internal class QaManifestExport
    {
        public string path   = "";
        public string format = "";
    }

    /// <summary>
    /// Full manifest model used only by <see cref="RuntimeValidator"/>.
    /// Includes <c>overall_status</c> and <c>export</c> which are not needed
    /// by the import-time postprocessor.
    /// </summary>
    [Serializable]
    internal class QaManifestForRuntime
    {
        public QaManifestMetadata    metadata       = new QaManifestMetadata();
        public string                overall_status = "";
        public QaManifestRuntimePerf performance    = new QaManifestRuntimePerf();
        public QaManifestExport      export         = new QaManifestExport();
    }

    // -----------------------------------------------------------------------
    // Runtime Validator
    // -----------------------------------------------------------------------

    /// <summary>
    /// Instantiates each QA-approved asset in a temporary Edit Mode scene and
    /// validates runtime rendering characteristics: draw calls, batching
    /// compatibility, single-pass instanced stereo, and shader complexity.
    ///
    /// Results are appended to the sidecar manifest under
    /// <c>runtime_validation</c>; failing assets are flagged
    /// <c>NEEDS_REVIEW</c> and copied to the review queue.
    ///
    /// CLI entry point:
    ///   Unity -batchmode -executeMethod QAPipeline.RuntimeValidator.ValidateAll -logFile -
    /// </summary>
    public static class RuntimeValidator
    {
        private const string ManifestDir      = "Assets/_QA/Manifests";
        private const string ReviewQueueDir   = "Assets/_QA/ReviewQueue";
        private const string LogPrefix        = "[QAPipeline:Runtime]";
        private const float  DrawCallBudget   = 1.2f;   // 20 % tolerance over estimate
        private const int    MaxShaderComplexity = 200; // proxy threshold

        // -----------------------------------------------------------------------
        // Public entry point
        // -----------------------------------------------------------------------

        /// <summary>
        /// Scans <c>Assets/_QA/Manifests/</c> for manifests whose
        /// <c>overall_status</c> is <c>PASS</c> or <c>PASS_WITH_FIXES</c> and
        /// that have no <c>runtime_validation</c> block yet, then validates each.
        /// </summary>
        public static void ValidateAll()
        {
            string fullDir = Path.Combine(
                Application.dataPath, "_QA", "Manifests");

            if (!Directory.Exists(fullDir))
            {
                Debug.Log($"{LogPrefix} Manifests directory not found: {ManifestDir}");
                return;
            }

            string[] files = Directory.GetFiles(
                fullDir, "*_qa.json", SearchOption.TopDirectoryOnly);
            Debug.Log($"{LogPrefix} Scanning {files.Length} manifest(s) in {ManifestDir}");

            int processed = 0;
            foreach (string manifestPath in files)
            {
                string raw;
                try { raw = File.ReadAllText(manifestPath); }
                catch (IOException ex)
                {
                    Debug.LogWarning(
                        $"{LogPrefix} Cannot read {manifestPath}: {ex.Message}");
                    continue;
                }

                // Skip manifests that already have a runtime_validation block
                if (raw.Contains("\"runtime_validation\"")) continue;

                QaManifestForRuntime m = ParseFullManifest(raw);
                if (m == null) continue;

                string os = m.overall_status;
                if (os != "PASS" && os != "PASS_WITH_FIXES") continue;

                string assetPath = ResolveAssetPath(m, manifestPath);
                if (string.IsNullOrEmpty(assetPath))
                {
                    Debug.LogWarning(
                        $"{LogPrefix} {m.metadata.asset_id} — asset not found, skipping");
                    continue;
                }

                ValidateAsset(assetPath, manifestPath);
                processed++;
            }

            Debug.Log($"{LogPrefix} Done. Validated {processed} asset(s).");
        }

        // -----------------------------------------------------------------------
        // Per-asset validation
        // -----------------------------------------------------------------------

        /// <summary>
        /// Instantiates <paramref name="assetPath"/> in a temporary scene, runs
        /// all runtime checks, and writes results to
        /// <paramref name="manifestPath"/>.
        /// </summary>
        public static void ValidateAsset(string assetPath, string manifestPath)
        {
            string raw = File.ReadAllText(manifestPath);
            QaManifestForRuntime manifest = ParseFullManifest(raw);
            string assetId = manifest?.metadata?.asset_id
                ?? Path.GetFileNameWithoutExtension(assetPath);

            Debug.Log($"{LogPrefix} {assetId} — begin runtime validation");

            Scene scene = EditorSceneManager.NewScene(
                NewSceneSetup.EmptyScene, NewSceneMode.Additive);
            GameObject go = null;
            RuntimeValidationResult result;
            try
            {
                go = InstantiateAsset(assetPath);
                if (go != null)
                    SceneManager.MoveGameObjectToScene(go, scene);

                Material[] materials = CollectMaterials(go);

                int actualDC    = CountDrawCalls(go);
                int estimatedDC = manifest?.performance?.draw_call_estimate ?? 0;
                bool dcOk = estimatedDC == 0
                    || actualDC <= (int)Math.Ceiling(estimatedDC * DrawCallBudget);

                bool batchOk  = CheckBatchingCompatible(go);
                bool stereoOk = CheckSinglePassInstanced(materials);
                bool shaderOk = CheckShaderComplexity(materials);

                string status = (dcOk && shaderOk) ? "PASS" : "FAIL";

                result = new RuntimeValidationResult
                {
                    draw_calls_actual     = actualDC,
                    draw_calls_estimated  = estimatedDC,
                    batching_compatible   = batchOk,
                    single_pass_instanced = stereoOk,
                    shader_complexity_ok  = shaderOk,
                    status                = status,
                };

                Debug.Log($"{LogPrefix} {assetId} — " +
                    $"dc={actualDC}/{estimatedDC} batch={batchOk} " +
                    $"stereo={stereoOk} shader={shaderOk} → {status}");
            }
            finally
            {
                if (go != null) UnityEngine.Object.DestroyImmediate(go);
                EditorSceneManager.CloseScene(scene, removeScene: true);
            }

            WriteResultsToManifest(manifestPath, result, raw);
        }

        // -----------------------------------------------------------------------
        // Static helpers — public for Edit Mode test access
        // -----------------------------------------------------------------------

        /// <summary>
        /// Loads and instantiates the asset at <paramref name="assetPath"/> via
        /// the AssetDatabase.  Returns null when the path resolves to no
        /// <c>GameObject</c>.
        /// </summary>
        public static GameObject InstantiateAsset(string assetPath)
        {
            GameObject prefab =
                AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
            if (prefab == null) return null;

            GameObject instance =
                (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            return instance ?? UnityEngine.Object.Instantiate(prefab);
        }

        /// <summary>
        /// Gathers all unique, non-null shared <see cref="Material"/> instances
        /// from <paramref name="root"/> and all of its children.
        /// </summary>
        public static Material[] CollectMaterials(GameObject root)
        {
            if (root == null) return Array.Empty<Material>();

            var list = new System.Collections.Generic.List<Material>();
            foreach (Renderer r in
                root.GetComponentsInChildren<Renderer>(includeInactive: true))
            {
                foreach (Material m in r.sharedMaterials)
                    if (m != null && !list.Contains(m)) list.Add(m);
            }
            return list.ToArray();
        }

        /// <summary>
        /// Counts draw calls as the total number of material slots across all
        /// <see cref="Renderer"/> components.  This is a static approximation
        /// valid for Edit Mode (actual profiling requires a running player).
        /// </summary>
        public static int CountDrawCalls(GameObject root)
        {
            if (root == null) return 0;
            int n = 0;
            foreach (Renderer r in
                root.GetComponentsInChildren<Renderer>(includeInactive: true))
                n += r.sharedMaterials.Length;
            return Mathf.Max(n, 1);
        }

        /// <summary>
        /// Returns <c>true</c> when the current render pipeline supports
        /// automatic draw-call batching (URP / SRP Batcher), or when the asset
        /// uses at most one material (eligible for legacy dynamic batching).
        /// </summary>
        public static bool CheckBatchingCompatible(GameObject root)
        {
            // Any SRP (URP / HDRP) uses the SRP Batcher for automatic batching.
            if (GraphicsSettings.currentRenderPipeline != null) return true;

            // Legacy pipeline: single-material mesh is dynamic-batching eligible.
            if (root == null) return true;
            return CollectMaterials(root).Length <= 1;
        }

        /// <summary>
        /// Returns <c>true</c> only when every material's shader declares the
        /// <c>STEREO_INSTANCING_ON</c> keyword, which is required for
        /// single-pass instanced stereo rendering in VR.
        /// </summary>
        public static bool CheckSinglePassInstanced(Material[] materials)
        {
            if (materials == null || materials.Length == 0) return true;

            foreach (Material mat in materials)
            {
                if (mat == null || mat.shader == null) continue;

                bool found = false;
                try
                {
                    foreach (string kw in mat.shader.keywordSpace.keywordNames)
                    {
                        if (kw == "STEREO_INSTANCING_ON")
                        {
                            found = true;
                            break;
                        }
                    }
                }
                catch
                {
                    // keywordSpace not available — treat as unsupported
                    return false;
                }

                if (!found) return false;
            }
            return true;
        }

        /// <summary>
        /// Estimates shader complexity as <c>passCount × propertyCount</c>.
        /// Flags any material whose shader exceeds
        /// <see cref="MaxShaderComplexity"/> as too complex for mobile VR.
        /// </summary>
        public static bool CheckShaderComplexity(Material[] materials)
        {
            if (materials == null || materials.Length == 0) return true;

            foreach (Material mat in materials)
            {
                if (mat == null || mat.shader == null) continue;
                try
                {
                    int estimate =
                        mat.passCount * ShaderUtil.GetPropertyCount(mat.shader);
                    if (estimate > MaxShaderComplexity) return false;
                }
                catch (Exception ex)
                {
                    Debug.LogWarning(
                        $"{LogPrefix} Shader complexity check error: {ex.Message}");
                }
            }
            return true;
        }

        /// <summary>
        /// Appends a <c>runtime_validation</c> block to the manifest JSON.
        /// If the result status is <c>FAIL</c>, also updates
        /// <c>overall_status</c> to <c>NEEDS_REVIEW</c> and copies the manifest
        /// to the review queue directory.
        /// </summary>
        public static void WriteResultsToManifest(
            string                 manifestPath,
            RuntimeValidationResult result,
            string                 rawJson)
        {
            string json = rawJson;

            if (result.status == "FAIL")
                json = UpdateOverallStatus(json, "NEEDS_REVIEW");

            json = InjectRuntimeValidation(json, result);

            File.WriteAllText(manifestPath, json);
            Debug.Log($"{LogPrefix} Updated manifest: {manifestPath}");

            if (result.status == "FAIL")
                CopyToReviewQueue(manifestPath, json);
        }

        // -----------------------------------------------------------------------
        // Private helpers
        // -----------------------------------------------------------------------

        private static QaManifestForRuntime ParseFullManifest(string json)
        {
            if (string.IsNullOrEmpty(json)) return null;
            try
            {
                var m = JsonUtility.FromJson<QaManifestForRuntime>(json);
                return (m != null && m.metadata != null) ? m : null;
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"{LogPrefix} Manifest parse error: {ex.Message}");
                return null;
            }
        }

        private static string ResolveAssetPath(
            QaManifestForRuntime manifest, string manifestPath)
        {
            // 1. Try export.path when it is already an Assets/-relative path
            if (manifest.export != null &&
                !string.IsNullOrEmpty(manifest.export.path))
            {
                string ep = manifest.export.path.Replace('\\', '/');
                if (ep.StartsWith("Assets/") &&
                    AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(ep) != null)
                    return ep;
            }

            // 2. Search AssetDatabase by asset_id substring
            string assetId = manifest.metadata?.asset_id ?? "";
            if (!string.IsNullOrEmpty(assetId))
            {
                foreach (string guid in AssetDatabase.FindAssets(assetId))
                {
                    string p = AssetDatabase.GUIDToAssetPath(guid);
                    if (AssetDatabase.LoadAssetAtPath<GameObject>(p) != null)
                        return p;
                }
            }

            return null;
        }

        /// <summary>
        /// Injects a <c>"runtime_validation"</c> field into a JSON object string
        /// by inserting before the final closing brace.
        /// </summary>
        private static string InjectRuntimeValidation(
            string rawJson, RuntimeValidationResult result)
        {
            string rvJson = JsonUtility.ToJson(result);
            string json   = rawJson.TrimEnd();

            if (json.EndsWith("}"))
            {
                string body = json
                    .Substring(0, json.Length - 1)
                    .TrimEnd()
                    .TrimEnd(',');
                json = $"{body},\n  \"runtime_validation\": {rvJson}\n}}";
            }
            return json;
        }

        /// <summary>
        /// Replaces the value of <c>"overall_status"</c> in a JSON string.
        /// </summary>
        private static string UpdateOverallStatus(string rawJson, string newStatus)
        {
            return Regex.Replace(
                rawJson,
                @"""overall_status""\s*:\s*""[^""]*""",
                $"\"overall_status\": \"{newStatus}\"");
        }

        private static void CopyToReviewQueue(string manifestPath, string json)
        {
            try
            {
                string queueDir = Path.Combine(
                    Application.dataPath, "_QA", "ReviewQueue");
                Directory.CreateDirectory(queueDir);

                string dest = Path.Combine(
                    queueDir, Path.GetFileName(manifestPath));
                File.WriteAllText(dest, json);
                Debug.Log($"{LogPrefix} Copied failed manifest to review queue: {dest}");
            }
            catch (Exception ex)
            {
                Debug.LogWarning(
                    $"{LogPrefix} Could not write to review queue: {ex.Message}");
            }
        }
    }
}
