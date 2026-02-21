using System.IO;
using NUnit.Framework;

namespace QAPipeline.Tests
{
    /// <summary>
    /// Edit Mode tests for <see cref="ScaleVerificationCapture"/>.
    ///
    /// Uses a temporary filesystem directory so Unity's AssetDatabase is not
    /// required; an asset that does not exist simply results in an asset-free
    /// scene, which is still valid for verifying the file-write path.
    /// </summary>
    public class ScaleVerificationTests
    {
        // -----------------------------------------------------------------------
        // Capture — file creation
        // -----------------------------------------------------------------------

        /// <summary>
        /// Calling <c>Capture</c> with any asset path must always create a PNG
        /// file at the expected location, even when the asset does not exist.
        /// </summary>
        [Test]
        public void Capture_CreatesScaleReferencePng()
        {
            string tmpDir   = Path.Combine(Path.GetTempPath(), "qa_scale_test");
            string assetPath = "Assets/Models/street_lamp_01_quant.gltf";
            string expected = Path.Combine(tmpDir,
                "street_lamp_01_quant_scale_reference.png");

            try
            {
                string result = ScaleVerificationCapture.Capture(assetPath, tmpDir);

                Assert.AreEqual(expected, result,
                    "Return value must be the expected output path");
                Assert.IsTrue(File.Exists(result),
                    "Capture must write a file at the returned path");
                Assert.Greater(new FileInfo(result).Length, 0L,
                    "Written PNG must be non-empty");
            }
            finally
            {
                if (File.Exists(expected)) File.Delete(expected);
                if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, recursive: true);
            }
        }

        [Test]
        public void Capture_OutputPathEndsWithScaleReferencePng()
        {
            string tmpDir = Path.Combine(Path.GetTempPath(), "qa_scale_suffix");
            try
            {
                string result = ScaleVerificationCapture.Capture(
                    "Assets/Nonexistent.gltf", tmpDir);

                Assert.IsNotNull(result, "Capture must return a non-null path");
                Assert.IsTrue(result.EndsWith("_scale_reference.png"),
                    "Output filename must end with _scale_reference.png");
            }
            finally
            {
                if (Directory.Exists(tmpDir))
                    Directory.Delete(tmpDir, recursive: true);
            }
        }

        // -----------------------------------------------------------------------
        // MinimalPng1x1 — guard against broken placeholder bytes
        // -----------------------------------------------------------------------

        [Test]
        public void MinimalPng1x1_StartsWithPngSignature()
        {
            byte[] data = ScaleVerificationCapture.MinimalPng1x1();
            Assert.IsNotNull(data);
            Assert.GreaterOrEqual(data.Length, 8);
            // PNG magic bytes: 0x89 P N G \r \n 0x1A \n
            Assert.AreEqual(0x89, data[0]);
            Assert.AreEqual((byte)'P', data[1]);
            Assert.AreEqual((byte)'N', data[2]);
            Assert.AreEqual((byte)'G', data[3]);
        }

        // -----------------------------------------------------------------------
        // Scene-object builders — shape and naming
        // -----------------------------------------------------------------------

        [Test]
        public void CreateHumanFigure_HasCorrectName()
        {
            var go = ScaleVerificationCapture.CreateHumanFigure();
            try
            {
                Assert.AreEqual("HumanFigure_1_75m", go.name);
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(go);
            }
        }

        [Test]
        public void CreateDoorFrame_HasCorrectName()
        {
            var go = ScaleVerificationCapture.CreateDoorFrame();
            try
            {
                Assert.AreEqual("DoorFrame_2_1x0_9m", go.name);
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(go);
            }
        }

        [Test]
        public void CreateHumanFigure_HeightApproximately175m()
        {
            // The capsule's world-space height is 2 * scale.y (Unity default).
            var go = ScaleVerificationCapture.CreateHumanFigure();
            try
            {
                float height = go.transform.localScale.y * 2f;
                Assert.AreEqual(1.75f, height, 0.01f,
                    "Human figure total height must be ~1.75 m");
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(go);
            }
        }
    }
}
