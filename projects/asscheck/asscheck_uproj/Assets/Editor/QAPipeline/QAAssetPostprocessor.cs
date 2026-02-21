using System;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace QAPipeline
{
    // -----------------------------------------------------------------------
    // Manifest data model — matches QaReport.to_dict() JSON produced by stage 3
    // -----------------------------------------------------------------------

    [Serializable]
    internal class QaManifestMetadata
    {
        public string asset_id = "";
        public string category = "";
    }

    [Serializable]
    internal class QaManifestPerformance
    {
        public int bone_count;
    }

    /// <summary>
    /// Parsed representation of a stage-3 sidecar manifest ({asset_id}_qa.json).
    /// Fields match the snake_case keys written by Python's QaReport.to_dict().
    /// </summary>
    [Serializable]
    public class QaManifest
    {
        public QaManifestMetadata metadata = new QaManifestMetadata();
        public QaManifestPerformance performance = new QaManifestPerformance();
        public bool require_lightmap_uv2;

        public string AssetId   => metadata != null ? metadata.asset_id  : "unknown";
        public string Category  => metadata != null ? metadata.category   : "";
        public int    BoneCount => performance != null ? performance.bone_count : 0;
        public bool   RequireLightmapUv2 => require_lightmap_uv2;
    }

    // -----------------------------------------------------------------------
    // Main postprocessor
    // -----------------------------------------------------------------------

    /// <summary>
    /// Reads the QA pipeline sidecar manifest and applies Unity import settings
    /// (model presets, texture compression, URP shader assignment) for any asset
    /// that has a companion <c>{assetName}_qa.json</c> file.
    ///
    /// Assets without a sidecar are left completely untouched.
    /// </summary>
    public class QAAssetPostprocessor : AssetPostprocessor
    {
        private const string SidecarSuffix  = "_qa.json";
        private const string LogPrefix      = "[QAPipeline]";
        private const string URPLitShader   = "Universal Render Pipeline/Lit";

        // -----------------------------------------------------------------------
        // Unity callbacks
        // -----------------------------------------------------------------------

        /// <summary>Fires before Unity's built-in ModelImporter processes a model.</summary>
        void OnPreprocessModel()
        {
            string sidecarPath = FindSidecarPath(assetPath);
            if (sidecarPath == null) return;

            QaManifest manifest = ReadManifest(sidecarPath);
            if (manifest == null) return;

            ApplyModelSettings((ModelImporter)assetImporter, manifest);
        }

        /// <summary>Fires before a texture asset is imported.</summary>
        void OnPreprocessTexture()
        {
            string sidecarPath = FindNearbyManifest(assetPath);
            if (sidecarPath == null) return;

            QaManifest manifest = ReadManifest(sidecarPath);
            if (manifest == null) return;

            ApplyTextureSettings(
                (TextureImporter)assetImporter,
                assetPath,
                EditorUserBuildSettings.activeBuildTarget,
                manifest);
        }

        /// <summary>Fires after Unity has finished importing a model.</summary>
        void OnPostprocessModel(GameObject root)
        {
            string sidecarPath = FindSidecarPath(assetPath);
            if (sidecarPath == null) return;

            QaManifest manifest = ReadManifest(sidecarPath);
            if (manifest == null) return;

            Shader urpLit = Shader.Find(URPLitShader);
            if (urpLit == null)
            {
                Debug.LogWarning(
                    $"{LogPrefix} {manifest.AssetId} — URP Lit shader not found; skipping material setup");
                return;
            }

            foreach (Renderer r in root.GetComponentsInChildren<Renderer>(includeInactive: true))
            {
                foreach (Material mat in r.sharedMaterials)
                {
                    if (mat != null) AssignURPMaterial(mat, urpLit, manifest.AssetId);
                }
            }
        }

        // -----------------------------------------------------------------------
        // Internal static helpers — public so Edit Mode tests can call them directly
        // -----------------------------------------------------------------------

        /// <summary>
        /// Returns <c>{assetPath_withoutExtension}_qa.json</c> if that file exists,
        /// otherwise null.
        /// </summary>
        internal static string FindSidecarPath(string assetPath)
        {
            string withoutExt = Path.ChangeExtension(assetPath, null);
            string candidate  = withoutExt + SidecarSuffix;
            return File.Exists(candidate) ? candidate : null;
        }

        /// <summary>
        /// Searches the same directory as <paramref name="texturePath"/>, then its
        /// parent, for any <c>*_qa.json</c> file. Returns the first match or null.
        /// Used by <see cref="OnPreprocessTexture"/> to locate the model manifest.
        /// </summary>
        internal static string FindNearbyManifest(string texturePath)
        {
            string dir = Path.GetDirectoryName(texturePath);
            if (string.IsNullOrEmpty(dir)) return null;

            foreach (string f in Directory.GetFiles(dir, "*" + SidecarSuffix))
                return f;

            string parent = Path.GetDirectoryName(dir);
            if (!string.IsNullOrEmpty(parent))
            {
                foreach (string f in Directory.GetFiles(parent, "*" + SidecarSuffix))
                    return f;
            }

            return null;
        }

        /// <summary>
        /// Deserialises a QA manifest JSON string. Returns null on any error.
        /// </summary>
        internal static QaManifest ParseManifest(string json)
        {
            if (string.IsNullOrEmpty(json)) return null;
            try
            {
                QaManifest m = JsonUtility.FromJson<QaManifest>(json);
                // JsonUtility may return a default-constructed object for bad JSON;
                // treat missing metadata as a parse failure.
                return (m != null && m.metadata != null && !string.IsNullOrEmpty(m.metadata.asset_id))
                    ? m : null;
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"{LogPrefix} Failed to parse QA manifest: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// Applies model import presets derived from the QA manifest to
        /// <paramref name="importer"/>.
        /// </summary>
        internal static void ApplyModelSettings(ModelImporter importer, QaManifest manifest)
        {
            string id = manifest.AssetId;

            // Always preserve geometry — never compress meshes
            importer.meshCompression = ModelImporterMeshCompression.Off;
            Log(id, "meshCompression", "Off");

            // Scale and units
            importer.globalScale   = 1.0f;
            importer.useFileUnits  = true;
            Log(id, "globalScale",  1.0f);
            Log(id, "useFileUnits", true);

            // Animation — character rigs only
            bool isCharacter = string.Equals(
                manifest.Category, "character", StringComparison.OrdinalIgnoreCase);
            importer.importAnimation = isCharacter;
            Log(id, "importAnimation", isCharacter);

            if (isCharacter)
            {
                importer.optimizeMeshPolygons = true;
                importer.optimizeMeshVertices = true;
                Log(id, "optimizeMesh", true);
            }

            // Bone optimisation
            if (manifest.BoneCount > 0)
            {
                importer.optimizeBones = true;
                Log(id, "optimizeBones", true);
            }

            // Lightmap UV
            if (manifest.RequireLightmapUv2)
            {
                importer.generateSecondaryUV = true;
                Log(id, "generateSecondaryUV", true);
            }
        }

        /// <summary>
        /// Applies texture compression and color-space settings based on the active
        /// build target and the texture's name keywords.
        /// </summary>
        internal static void ApplyTextureSettings(
            TextureImporter  importer,
            string           texturePath,
            BuildTarget      buildTarget,
            QaManifest       manifest)
        {
            string id   = manifest.AssetId;
            string name = Path.GetFileNameWithoutExtension(texturePath);

            bool srgb = IsSRGBTexture(name);
            importer.sRGBTexture = srgb;
            Log(id, "sRGBTexture", srgb);

            importer.mipmapEnabled   = true;
            importer.streamingMipmaps = true;
            Log(id, "mipmapEnabled",    true);
            Log(id, "streamingMipmaps", true);

            TextureImporterFormat fmt = GetTextureFormat(buildTarget);
            importer.SetPlatformTextureSettings(new TextureImporterPlatformSettings
            {
                name       = buildTarget == BuildTarget.Android ? "Android" : "Standalone",
                overridden = true,
                format     = fmt,
            });
            Log(id, "textureFormat", fmt);
        }

        /// <summary>
        /// Returns <c>true</c> when the texture name suggests sRGB content (albedo /
        /// diffuse / color), <c>false</c> for linear maps (normal / roughness /
        /// metallic / ambient-occlusion).
        /// </summary>
        internal static bool IsSRGBTexture(string textureName)
        {
            string lower = textureName.ToLowerInvariant();
            if (lower.Contains("normal")    || lower.Contains("nrm")      ||
                lower.Contains("rough")     || lower.Contains("roughness") ||
                lower.Contains("metallic")  || lower.Contains("metal")    ||
                lower.Contains("_ao")       || lower.Contains("occlusion") ||
                lower.Contains("ambient"))
            {
                return false;
            }
            return true;   // albedo, diffuse, basecolor, color → sRGB
        }

        /// <summary>
        /// Returns the platform-appropriate texture compression format.
        /// Android (mobile VR) → ASTC 6×6; everything else → BC7.
        /// </summary>
        internal static TextureImporterFormat GetTextureFormat(BuildTarget buildTarget)
        {
            return buildTarget == BuildTarget.Android
                ? TextureImporterFormat.ASTC_6x6
                : TextureImporterFormat.BC7;
        }

        // -----------------------------------------------------------------------
        // Private helpers
        // -----------------------------------------------------------------------

        private static QaManifest ReadManifest(string sidecarPath)
        {
            string json;
            try { json = File.ReadAllText(sidecarPath); }
            catch (IOException ex)
            {
                Debug.LogWarning($"{LogPrefix} Could not read sidecar '{sidecarPath}': {ex.Message}");
                return null;
            }
            return ParseManifest(json);
        }

        private static void AssignURPMaterial(Material mat, Shader urpLit, string assetId)
        {
            // Collect textures from all property slots before the shader swap
            // so we can remap them to URP slots by name keyword.
            var collected = new System.Collections.Generic.List<(string slot, Texture tex)>();
            int propCount = mat.shader.GetPropertyCount();
            for (int i = 0; i < propCount; i++)
            {
                if (mat.shader.GetPropertyType(i) == ShaderPropertyType.Texture)
                {
                    string pn  = mat.shader.GetPropertyName(i);
                    Texture tex = mat.GetTexture(pn);
                    if (tex != null) collected.Add((pn, tex));
                }
            }

            if (mat.shader.name != URPLitShader)
            {
                mat.shader = urpLit;
                Log(assetId, "shader", URPLitShader);
            }

            // Remap textures to standard URP slots
            foreach (var (_, tex) in collected)
            {
                string urpSlot = ResolveURPSlot(tex.name.ToLowerInvariant());
                if (urpSlot != null && mat.GetTexture(urpSlot) == null)
                {
                    mat.SetTexture(urpSlot, tex);
                    Log(assetId, $"textureSlot:{urpSlot}", tex.name);
                }
            }
        }

        private static string ResolveURPSlot(string texNameLower)
        {
            if (texNameLower.Contains("albedo")    || texNameLower.Contains("diffuse")   ||
                texNameLower.Contains("basecolor")  || texNameLower.Contains("base_color") ||
                texNameLower.Contains("color"))      return "_BaseMap";

            if (texNameLower.Contains("normal")    || texNameLower.Contains("nrm")  ||
                texNameLower.Contains("bump"))       return "_BumpMap";

            if (texNameLower.Contains("metallic")  || texNameLower.Contains("metal") ||
                texNameLower.Contains("roughness")  || texNameLower.Contains("rough")) return "_MetallicGlossMap";

            if (texNameLower.Contains("_ao")       || texNameLower.Contains("occlusion") ||
                texNameLower.Contains("ambient"))   return "_OcclusionMap";

            return null;
        }

        private static void Log(string assetId, string setting, object value)
        {
            Debug.Log($"{LogPrefix} {assetId} — applied {setting}: {value}");
        }
    }
}
