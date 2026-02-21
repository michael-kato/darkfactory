using System.IO;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;
using UnityEngine.TestTools;

namespace QAPipeline.Tests
{
    /// <summary>
    /// Edit Mode tests for <see cref="QAAssetPostprocessor"/>.
    ///
    /// Pure-logic tests call internal static helpers directly (no import required).
    /// Integration tests use AssetDatabase.ImportAsset on a minimal OBJ test asset
    /// (OBJ uses Unity's built-in ModelImporter, not the GLTFast ScriptedImporter).
    /// </summary>
    public class QAPostprocessorTests
    {
        // Relative path from project root for the test OBJ asset
        private const string TestObjPath =
            "Assets/Editor/Tests/TestAssets/qa_test_cube.obj";

        // A hand-crafted sidecar manifest for an env_prop asset
        private const string EnvPropManifestJson = @"{
            ""metadata"": {
                ""asset_id"": ""test-envprop-001"",
                ""category"": ""env_prop""
            },
            ""performance"": {
                ""bone_count"": 0
            },
            ""require_lightmap_uv2"": false
        }";

        // A hand-crafted sidecar manifest for a character asset with bones
        private const string CharacterManifestJson = @"{
            ""metadata"": {
                ""asset_id"": ""test-char-001"",
                ""category"": ""character""
            },
            ""performance"": {
                ""bone_count"": 45
            },
            ""require_lightmap_uv2"": false
        }";

        // -----------------------------------------------------------------------
        // Sidecar discovery
        // -----------------------------------------------------------------------

        [Test]
        public void NoSidecar_FindSidecarPath_ReturnsNull()
        {
            // asset without any companion _qa.json → should return null
            string result = QAAssetPostprocessor.FindSidecarPath(
                "Assets/Models/does_not_exist.gltf");
            Assert.IsNull(result,
                "FindSidecarPath must return null when no sidecar file exists");
        }

        [Test]
        public void WithSidecar_FindSidecarPath_ReturnsPath()
        {
            string sidecarPath = Path.ChangeExtension(TestObjPath, null) + "_qa.json";
            try
            {
                File.WriteAllText(sidecarPath, EnvPropManifestJson);
                string found = QAAssetPostprocessor.FindSidecarPath(TestObjPath);
                Assert.AreEqual(sidecarPath, found,
                    "FindSidecarPath should return the sidecar path when it exists");
            }
            finally
            {
                if (File.Exists(sidecarPath)) File.Delete(sidecarPath);
            }
        }

        // -----------------------------------------------------------------------
        // Manifest parsing
        // -----------------------------------------------------------------------

        [Test]
        public void ParseManifest_ValidJson_ReturnsManifest()
        {
            QaManifest m = QAAssetPostprocessor.ParseManifest(EnvPropManifestJson);
            Assert.IsNotNull(m);
            Assert.AreEqual("test-envprop-001", m.AssetId);
            Assert.AreEqual("env_prop",         m.Category);
            Assert.AreEqual(0,                  m.BoneCount);
        }

        [Test]
        public void ParseManifest_InvalidJson_ReturnsNull()
        {
            LogAssert.ignoreFailingMessages = true;
            QaManifest m = QAAssetPostprocessor.ParseManifest("not-valid-json{{{");
            Assert.IsNull(m, "ParseManifest must return null for malformed JSON");
        }

        [Test]
        public void ParseManifest_EmptyString_ReturnsNull()
        {
            QaManifest m = QAAssetPostprocessor.ParseManifest("");
            Assert.IsNull(m, "ParseManifest must return null for an empty string");
        }

        // -----------------------------------------------------------------------
        // IsSRGBTexture — pure logic
        // -----------------------------------------------------------------------

        [Test]
        public void TextureName_Normal_IsLinear()
        {
            Assert.IsFalse(QAAssetPostprocessor.IsSRGBTexture("T_StreetLamp_Normal"),
                "Normal maps must use linear color space (sRGBTexture = false)");
        }

        [Test]
        public void TextureName_Albedo_IsSRGB()
        {
            Assert.IsTrue(QAAssetPostprocessor.IsSRGBTexture("T_StreetLamp_Albedo"),
                "Albedo textures must use sRGB color space (sRGBTexture = true)");
        }

        [Test]
        public void TextureName_Roughness_IsLinear()
        {
            Assert.IsFalse(QAAssetPostprocessor.IsSRGBTexture("T_Char_Roughness"),
                "Roughness maps must be linear");
        }

        [Test]
        public void TextureName_Metallic_IsLinear()
        {
            Assert.IsFalse(QAAssetPostprocessor.IsSRGBTexture("T_Char_Metallic"),
                "Metallic maps must be linear");
        }

        // -----------------------------------------------------------------------
        // GetTextureFormat — pure logic
        // -----------------------------------------------------------------------

        [Test]
        public void BuildTargetPC_TextureFormat_IsBC7()
        {
            TextureImporterFormat fmt =
                QAAssetPostprocessor.GetTextureFormat(BuildTarget.StandaloneWindows64);
            Assert.AreEqual(TextureImporterFormat.BC7, fmt,
                "PC (StandaloneWindows64) must use BC7 compression");
        }

        [Test]
        public void BuildTargetLinux_TextureFormat_IsBC7()
        {
            TextureImporterFormat fmt =
                QAAssetPostprocessor.GetTextureFormat(BuildTarget.StandaloneLinux64);
            Assert.AreEqual(TextureImporterFormat.BC7, fmt,
                "StandaloneLinux64 must use BC7 compression");
        }

        [Test]
        public void BuildTargetAndroid_TextureFormat_IsASTCx6()
        {
            TextureImporterFormat fmt =
                QAAssetPostprocessor.GetTextureFormat(BuildTarget.Android);
            Assert.AreEqual(TextureImporterFormat.ASTC_6x6, fmt,
                "Android (mobile VR) must use ASTC 6x6 compression");
        }

        // -----------------------------------------------------------------------
        // Integration — ModelImporter (OBJ uses Unity's built-in importer)
        // -----------------------------------------------------------------------

        [Test]
        public void NoSidecar_Import_DoesNothing()
        {
            // Ensure no sidecar exists, then reimport — must complete without errors.
            string sidecarPath = Path.ChangeExtension(TestObjPath, null) + "_qa.json";
            if (File.Exists(sidecarPath)) File.Delete(sidecarPath);

            Assert.DoesNotThrow(
                () => AssetDatabase.ImportAsset(TestObjPath, ImportAssetOptions.ForceUpdate),
                "Importing without a sidecar must not throw");

            ModelImporter importer = AssetImporter.GetAtPath(TestObjPath) as ModelImporter;
            Assert.IsNotNull(importer, "Sample OBJ must use ModelImporter");
        }

        [Test]
        public void WithSidecar_GlobalScale_IsOne()
        {
            string sidecarPath = Path.ChangeExtension(TestObjPath, null) + "_qa.json";
            try
            {
                File.WriteAllText(sidecarPath, EnvPropManifestJson);
                AssetDatabase.ImportAsset(TestObjPath, ImportAssetOptions.ForceUpdate);

                ModelImporter importer = AssetImporter.GetAtPath(TestObjPath) as ModelImporter;
                Assert.IsNotNull(importer);
                Assert.AreEqual(1.0f, importer.globalScale, 0.001f,
                    "globalScale must be 1.0 when sidecar manifest is present");
            }
            finally
            {
                CleanupAndReimport(sidecarPath);
            }
        }

        [Test]
        public void CategoryCharacter_ImportAnimation_IsTrue()
        {
            string sidecarPath = Path.ChangeExtension(TestObjPath, null) + "_qa.json";
            try
            {
                File.WriteAllText(sidecarPath, CharacterManifestJson);
                AssetDatabase.ImportAsset(TestObjPath, ImportAssetOptions.ForceUpdate);

                ModelImporter importer = AssetImporter.GetAtPath(TestObjPath) as ModelImporter;
                Assert.IsNotNull(importer);
                Assert.IsTrue(importer.importAnimation,
                    "importAnimation must be true for category 'character'");
            }
            finally
            {
                CleanupAndReimport(sidecarPath);
            }
        }

        [Test]
        public void CategoryEnvProp_ImportAnimation_IsFalse()
        {
            string sidecarPath = Path.ChangeExtension(TestObjPath, null) + "_qa.json";
            try
            {
                File.WriteAllText(sidecarPath, EnvPropManifestJson);
                AssetDatabase.ImportAsset(TestObjPath, ImportAssetOptions.ForceUpdate);

                ModelImporter importer = AssetImporter.GetAtPath(TestObjPath) as ModelImporter;
                Assert.IsNotNull(importer);
                Assert.IsFalse(importer.importAnimation,
                    "importAnimation must be false for category 'env_prop'");
            }
            finally
            {
                CleanupAndReimport(sidecarPath);
            }
        }

        // -----------------------------------------------------------------------
        // Helpers
        // -----------------------------------------------------------------------

        private static void CleanupAndReimport(string sidecarPath)
        {
            if (File.Exists(sidecarPath)) File.Delete(sidecarPath);
            // Reimport without sidecar to restore default settings
            AssetDatabase.ImportAsset(TestObjPath, ImportAssetOptions.ForceUpdate);
        }
    }
}
