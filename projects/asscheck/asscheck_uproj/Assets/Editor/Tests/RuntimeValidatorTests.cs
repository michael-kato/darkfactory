using System.IO;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

namespace QAPipeline.Tests
{
    /// <summary>
    /// Edit Mode tests for <see cref="RuntimeValidator"/>.
    ///
    /// Pure-logic tests call public static helpers directly.
    /// JSON round-trip tests use temporary files to verify manifest mutation.
    /// </summary>
    public class RuntimeValidatorTests
    {
        // Minimal PASS manifest — no runtime_validation block
        private const string PassManifestJson = @"{
    ""metadata"": { ""asset_id"": ""test-rt-001"", ""category"": ""env_prop"" },
    ""overall_status"": ""PASS"",
    ""performance"": { ""draw_call_estimate"": 2 }
}";

        // -----------------------------------------------------------------------
        // Draw call counting
        // -----------------------------------------------------------------------

        /// <summary>
        /// A single primitive (1 renderer, 1 material) must report ≤ 2 draw calls.
        /// </summary>
        [Test]
        public void SingleMaterial_DrawCallCount_LteTwo()
        {
            GameObject cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            try
            {
                int dc = RuntimeValidator.CountDrawCalls(cube);
                Assert.LessOrEqual(dc, 2,
                    "A single-material primitive must count as ≤ 2 draw calls");
            }
            finally
            {
                Object.DestroyImmediate(cube);
            }
        }

        [Test]
        public void NullGameObject_DrawCallCount_IsZero()
        {
            Assert.AreEqual(0, RuntimeValidator.CountDrawCalls(null),
                "Null root must return 0 draw calls");
        }

        // -----------------------------------------------------------------------
        // Single-pass instanced stereo (STEREO_INSTANCING_ON keyword)
        // -----------------------------------------------------------------------

        /// <summary>
        /// A shader that does not declare <c>STEREO_INSTANCING_ON</c> must cause
        /// <c>CheckSinglePassInstanced</c> to return <c>false</c>.
        /// </summary>
        [Test]
        public void ShaderWithoutStereoKeyword_SinglePassInstanced_IsFalse()
        {
            // Unlit/Color is a simple built-in shader that has no XR keywords.
            Shader sh = Shader.Find("Unlit/Color")
                     ?? Shader.Find("Hidden/InternalErrorShader");
            if (sh == null)
            {
                Assert.Inconclusive(
                    "No suitable test shader found — cannot verify stereo check");
                return;
            }

            Material mat = new Material(sh);
            try
            {
                bool result = RuntimeValidator.CheckSinglePassInstanced(
                    new[] { mat });
                Assert.IsFalse(result,
                    "Shader without STEREO_INSTANCING_ON must report " +
                    "single_pass_instanced = false");
            }
            finally
            {
                Object.DestroyImmediate(mat);
            }
        }

        [Test]
        public void NullMaterialArray_SinglePassInstanced_IsTrue()
        {
            // Vacuously true when no materials exist
            Assert.IsTrue(RuntimeValidator.CheckSinglePassInstanced(null));
            Assert.IsTrue(
                RuntimeValidator.CheckSinglePassInstanced(new Material[0]));
        }

        // -----------------------------------------------------------------------
        // Manifest written back with runtime_validation block
        // -----------------------------------------------------------------------

        [Test]
        public void WriteResultsToManifest_AddsRuntimeValidationBlock()
        {
            string path = Path.GetTempFileName();
            try
            {
                File.WriteAllText(path, PassManifestJson);

                var result = new RuntimeValidationResult
                {
                    draw_calls_actual     = 1,
                    draw_calls_estimated  = 2,
                    batching_compatible   = true,
                    single_pass_instanced = true,
                    shader_complexity_ok  = true,
                    status                = "PASS",
                };

                RuntimeValidator.WriteResultsToManifest(
                    path, result, PassManifestJson);

                string updated = File.ReadAllText(path);
                Assert.IsTrue(
                    updated.Contains("\"runtime_validation\""),
                    "Manifest must contain a runtime_validation block after validation");
                Assert.IsTrue(
                    updated.Contains("\"draw_calls_actual\""),
                    "runtime_validation must include draw_calls_actual");
                Assert.IsTrue(
                    updated.Contains("\"status\""),
                    "runtime_validation must include status");
            }
            finally
            {
                if (File.Exists(path)) File.Delete(path);
            }
        }

        // -----------------------------------------------------------------------
        // Failing validation updates overall_status → NEEDS_REVIEW
        // -----------------------------------------------------------------------

        /// <summary>
        /// When runtime validation fails, the manifest's <c>overall_status</c>
        /// must be updated from <c>PASS</c> to <c>NEEDS_REVIEW</c>.
        /// </summary>
        [Test]
        public void FailingValidation_UpdatesOverallStatusToNeedsReview()
        {
            string path = Path.GetTempFileName();
            try
            {
                File.WriteAllText(path, PassManifestJson);

                var result = new RuntimeValidationResult
                {
                    draw_calls_actual     = 100,
                    draw_calls_estimated  = 2,
                    batching_compatible   = false,
                    single_pass_instanced = false,
                    shader_complexity_ok  = false,
                    status                = "FAIL",
                };

                RuntimeValidator.WriteResultsToManifest(
                    path, result, PassManifestJson);

                string updated = File.ReadAllText(path);
                Assert.IsTrue(
                    updated.Contains("\"NEEDS_REVIEW\""),
                    "A failed asset must have overall_status updated to NEEDS_REVIEW");
                Assert.IsFalse(
                    updated.Contains("\"PASS\""),
                    "The original PASS status must be replaced, not duplicated");
            }
            finally
            {
                if (File.Exists(path)) File.Delete(path);
            }
        }
    }
}
