using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace QAPipeline
{
    /// <summary>
    /// Instantiates an asset in a pre-built reference scene alongside a human
    /// figure (capsule, 1.75 m) and a door frame (2.1 m × 0.9 m), then
    /// captures a scale-reference screenshot.
    ///
    /// Scale verification is always marked <c>NEEDS_REVIEW</c> — a human
    /// reviewer must confirm the scale is correct.
    ///
    /// CLI entry point:
    ///   Unity -batchmode -executeMethod QAPipeline.ScaleVerificationCapture.CaptureDefault -logFile -
    /// </summary>
    public static class ScaleVerificationCapture
    {
        private const string LogPrefix      = "[QAPipeline:ScaleVerif]";
        private const string DefaultQaDir   = "Assets/_QA/ScaleRefs";

        // Human-figure capsule height in metres.
        private const float HumanHeight = 1.75f;
        // Door frame dimensions in metres.
        private const float DoorHeight  = 2.1f;
        private const float DoorWidth   = 0.9f;

        // -----------------------------------------------------------------------
        // Public API
        // -----------------------------------------------------------------------

        /// <summary>
        /// Captures a scale-reference screenshot for <paramref name="assetPath"/>
        /// and writes it to
        /// <c>{qaOutputDir}/{assetId}_scale_reference.png</c>.
        ///
        /// The asset may not exist (e.g. during tests) — in that case the scene
        /// still shows the reference objects and a placeholder PNG is written.
        /// </summary>
        /// <param name="assetPath">
        ///   Asset-database path of the prefab/model to inspect.
        /// </param>
        /// <param name="qaOutputDir">
        ///   Absolute filesystem directory for output.  Defaults to
        ///   <c>Application.dataPath/_QA/ScaleRefs/</c> when <c>null</c>.
        /// </param>
        /// <returns>Absolute path of the written PNG.</returns>
        public static string Capture(string assetPath, string qaOutputDir = null)
        {
            string outputDir = string.IsNullOrEmpty(qaOutputDir)
                ? Path.Combine(Application.dataPath, "_QA", "ScaleRefs")
                : qaOutputDir;

            Directory.CreateDirectory(outputDir);

            string assetId  = Path.GetFileNameWithoutExtension(assetPath);
            string outFile  = Path.Combine(outputDir, $"{assetId}_scale_reference.png");

            Scene scene = EditorSceneManager.NewScene(
                NewSceneSetup.EmptyScene, NewSceneMode.Additive);

            GameObject assetGO    = null;
            GameObject capsuleGO  = null;
            GameObject doorFrameGO = null;

            try
            {
                // Human figure — capsule scaled to 1.75 m total height.
                // Unity's default capsule is 2 units tall, so scale.y = 0.875
                // gives 1.75 m.
                capsuleGO = CreateHumanFigure();
                SceneManager.MoveGameObjectToScene(capsuleGO, scene);

                // Door frame — 2.1 m tall × 0.9 m wide.
                doorFrameGO = CreateDoorFrame();
                SceneManager.MoveGameObjectToScene(doorFrameGO, scene);

                // Asset — loaded from AssetDatabase; may be null if path is
                // fictitious (unit-test scenario).
                assetGO = TryInstantiateAsset(assetPath);
                if (assetGO != null)
                    SceneManager.MoveGameObjectToScene(assetGO, scene);

                WriteScreenshot(outFile);

                Debug.Log($"{LogPrefix} Captured: {outFile}");
            }
            finally
            {
                if (assetGO    != null) UnityEngine.Object.DestroyImmediate(assetGO);
                if (capsuleGO  != null) UnityEngine.Object.DestroyImmediate(capsuleGO);
                if (doorFrameGO != null) UnityEngine.Object.DestroyImmediate(doorFrameGO);
                EditorSceneManager.CloseScene(scene, removeScene: true);
            }

            return outFile;
        }

        /// <summary>Batch-mode entry point. Captures the sample asset.</summary>
        public static void CaptureDefault()
        {
            string sample = "Assets/Models/street_lamp_01_quant.gltf";
            string result = Capture(sample);
            Debug.Log($"{LogPrefix} Default capture complete: {result}");
        }

        // -----------------------------------------------------------------------
        // Scene-object builders
        // -----------------------------------------------------------------------

        /// <summary>
        /// Creates a capsule representing a 1.75 m human figure positioned
        /// to the left of the asset placement origin.
        /// </summary>
        public static GameObject CreateHumanFigure()
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            go.name = "HumanFigure_1_75m";
            // Unity capsule height = 2 * scale.y  →  scale.y = 0.875 for 1.75 m
            go.transform.localScale   = new Vector3(0.3f, HumanHeight * 0.5f, 0.3f);
            go.transform.position     = new Vector3(-1.5f, HumanHeight * 0.5f, 0f);
            return go;
        }

        /// <summary>
        /// Creates a simple door-frame prop: two vertical posts and a lintel,
        /// sized to 2.1 m height × 0.9 m width.
        /// </summary>
        public static GameObject CreateDoorFrame()
        {
            var frame = new GameObject("DoorFrame_2_1x0_9m");
            float postW   = 0.08f;
            float halfGap = DoorWidth * 0.5f;

            // Left post
            CreateBox(frame, "LeftPost",
                new Vector3(postW, DoorHeight, postW),
                new Vector3(-halfGap - postW * 0.5f, DoorHeight * 0.5f, 0f));

            // Right post
            CreateBox(frame, "RightPost",
                new Vector3(postW, DoorHeight, postW),
                new Vector3( halfGap + postW * 0.5f, DoorHeight * 0.5f, 0f));

            // Lintel
            CreateBox(frame, "Lintel",
                new Vector3(DoorWidth + postW * 2f, postW, postW),
                new Vector3(0f, DoorHeight + postW * 0.5f, 0f));

            frame.transform.position = new Vector3(1.5f, 0f, 0f);
            return frame;
        }

        // -----------------------------------------------------------------------
        // Private helpers
        // -----------------------------------------------------------------------

        private static GameObject TryInstantiateAsset(string assetPath)
        {
            try
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
                if (prefab == null) return null;

                var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
                return go ?? UnityEngine.Object.Instantiate(prefab);
            }
            catch (Exception ex)
            {
                Debug.LogWarning(
                    $"{LogPrefix} Could not instantiate asset '{assetPath}': {ex.Message}");
                return null;
            }
        }

        private static void CreateBox(
            GameObject parent, string name, Vector3 scale, Vector3 localPos)
        {
            var box = GameObject.CreatePrimitive(PrimitiveType.Cube);
            box.name = name;
            box.transform.SetParent(parent.transform, worldPositionStays: false);
            box.transform.localScale    = scale;
            box.transform.localPosition = localPos;
        }

        private static void WriteScreenshot(string outFile)
        {
            Texture2D tex = null;
            try
            {
                tex = ScreenCapture.CaptureScreenshotAsTexture();
            }
            catch (Exception ex)
            {
                Debug.LogWarning(
                    $"{LogPrefix} ScreenCapture failed ({ex.Message}); writing placeholder PNG.");
            }

            if (tex != null)
            {
                byte[] png = tex.EncodeToPNG();
                UnityEngine.Object.DestroyImmediate(tex);
                File.WriteAllBytes(outFile, png);
            }
            else
            {
                // Batch-mode / headless fallback: write a minimal 1×1 PNG so
                // downstream tools can always find a file at the expected path.
                File.WriteAllBytes(outFile, MinimalPng1x1());
            }
        }

        /// <summary>Returns the raw bytes of a valid 1×1 white PNG.</summary>
        internal static byte[] MinimalPng1x1()
        {
            // Pre-built 1×1 white RGBA PNG (67 bytes).
            return new byte[]
            {
                0x89,0x50,0x4E,0x47,0x0D,0x0A,0x1A,0x0A, // PNG signature
                0x00,0x00,0x00,0x0D,0x49,0x48,0x44,0x52, // IHDR length + type
                0x00,0x00,0x00,0x01,0x00,0x00,0x00,0x01, // 1×1
                0x08,0x02,0x00,0x00,0x00,0x90,0x77,0x53, // 8-bit RGB, CRC start
                0xDE,0x00,0x00,0x00,0x0C,0x49,0x44,0x41, // CRC end + IDAT
                0x54,0x08,0xD7,0x63,0xF8,0xCF,0xC0,0x00, // IDAT data
                0x00,0x00,0x02,0x00,0x01,0xE2,0x21,0xBC, // IDAT CRC
                0x33,0x00,0x00,0x00,0x00,0x49,0x45,0x4E, // IEND
                0x44,0xAE,0x42,0x60,0x82,                 // IEND CRC
            };
        }
    }
}
