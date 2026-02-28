#if UNITY_EDITOR
using UnityEngine;
using UnityEditor;

[InitializeOnLoad]
public class SDFSceneViewRenderer : Editor
{
    private static Material _sdfMaterial;
    private static bool _isInitialized;
    private static Mesh _quadMesh;
    
    private static float _maxDistance = 100f;
    private static int _maxSteps = 64;
    private static float _surfaceThreshold = 0.001f;

    static SDFSceneViewRenderer()
    {
        EditorApplication.playModeStateChanged += OnPlayModeChanged;
        SceneView.duringSceneGui += OnDuringSceneGUI;
    }

    private static void OnPlayModeChanged(PlayModeStateChange state)
    {
        if (state == PlayModeStateChange.EnteredPlayMode || state == PlayModeStateChange.ExitingPlayMode)
        {
            Cleanup();
        }
    }

    private static void OnDuringSceneGUI(SceneView sceneView)
    {
        if (EditorApplication.isPlaying) return;

        bool hasPrimitives = IsSDFSceneActive();
        
        if (!hasPrimitives)
        {
            if (_isInitialized) Cleanup();
            return;
        }

        if (!_isInitialized)
        {
            Initialize();
        }

        if (_isInitialized)
        {
            Camera cam = sceneView.camera;
            if (cam != null)
            {
                DrawSDFOverlay(cam);
            }
        }
    }

    private static void Initialize()
    {
        Shader shader = Shader.Find("SDF/Render");
        if (shader == null)
        {
            Debug.LogWarning("[SDFSceneViewRenderer] SDF/Render shader not found!");
            return;
        }

        _sdfMaterial = new Material(shader);
        _sdfMaterial.SetFloat("_MaxDistance", _maxDistance);
        _sdfMaterial.SetInt("_MaxSteps", _maxSteps);
        _sdfMaterial.SetFloat("_SurfaceThreshold", _surfaceThreshold);
        _sdfMaterial.hideFlags = HideFlags.HideAndDontSave;
        _sdfMaterial.enableInstancing = true;

        _quadMesh = CreateQuadMesh();

        _isInitialized = true;
    }

    private static Mesh CreateQuadMesh()
    {
        Mesh mesh = new Mesh();
        mesh.name = "SDFQuad";

        Vector3[] vertices = new Vector3[]
        {
            new Vector3(-1, -1, 0),
            new Vector3( 1, -1, 0),
            new Vector3( 1,  1, 0),
            new Vector3(-1,  1, 0)
        };

        Vector2[] uvs = new Vector2[]
        {
            new Vector2(0, 0),
            new Vector2(1, 0),
            new Vector2(1, 1),
            new Vector2(0, 1)
        };

        int[] triangles = new int[]
        {
            0, 2, 1,
            0, 3, 2
        };

        mesh.vertices = vertices;
        mesh.uv = uvs;
        mesh.triangles = triangles;
        mesh.RecalculateNormals();

        return mesh;
    }

    private static void Cleanup()
    {
        if (_sdfMaterial != null)
        {
            DestroyImmediate(_sdfMaterial);
            _sdfMaterial = null;
        }

        if (_quadMesh != null)
        {
            DestroyImmediate(_quadMesh);
            _quadMesh = null;
        }

        _isInitialized = false;
    }

    private static void DrawSDFOverlay(Camera cam)
    {
        if (_sdfMaterial == null || _quadMesh == null) return;

        UpdateMaterialParameters(cam);

        float fov = cam.fieldOfView;
        float aspect = cam.aspect;
        float distance = 1f;
        float height = 2f * distance * Mathf.Tan(fov * 0.5f * Mathf.Deg2Rad);
        float width = height * aspect;

        Matrix4x4 transform = Matrix4x4.TRS(
            cam.transform.position + cam.transform.forward * distance,
            cam.transform.rotation,
            new Vector3(width, height, 1)
        );

        Graphics.DrawMesh(
            _quadMesh,
            transform,
            _sdfMaterial,
            0,
            cam,
            0,
            null,
            false,
            false,
            false
        );
    }

    private static void UpdateMaterialParameters(Camera cam)
    {
        if (_sdfMaterial == null || cam == null) return;

        var sceneManagers = Resources.FindObjectsOfTypeAll<SDFSceneManager>();
        if (sceneManagers.Length > 0)
        {
            SDFSceneManager sceneManager = sceneManagers[0];
            if (sceneManager != null && sceneManager.PrimitiveBuffer != null)
            {
                _sdfMaterial.SetBuffer("_Primitives", sceneManager.PrimitiveBuffer);
                _sdfMaterial.SetInt("_PrimitiveCount", sceneManager.PrimitiveCount);
            }
        }

        Matrix4x4 viewMatrix = cam.worldToCameraMatrix;
        Matrix4x4 projMatrix = GL.GetGPUProjectionMatrix(cam.projectionMatrix, true);
        Matrix4x4 viewProjMatrix = projMatrix * viewMatrix;
        Matrix4x4 inverseViewProj = viewProjMatrix.inverse;

        _sdfMaterial.SetMatrix("_ViewProjectionMatrix", viewProjMatrix);
        _sdfMaterial.SetMatrix("_InverseViewProjection", inverseViewProj);
        _sdfMaterial.SetVector("_CameraPosition", cam.transform.position);
        _sdfMaterial.SetVector("_CameraForward", cam.transform.forward);
        _sdfMaterial.SetVector("_CameraRight", cam.transform.right);
        _sdfMaterial.SetVector("_CameraUp", cam.transform.up);

        float fov = cam.fieldOfView;
        float aspect = cam.aspect;
        float tanHalfFov = Mathf.Tan(fov * 0.5f * Mathf.Deg2Rad);
        _sdfMaterial.SetVector("_CameraParams", new Vector4(tanHalfFov, aspect, fov, 0));
    }

    private static bool IsSDFSceneActive()
    {
        var managers = Resources.FindObjectsOfTypeAll<SDFSceneManager>();
        if (managers.Length == 0) return false;
        
        var sceneManager = managers[0];
        return sceneManager != null && sceneManager.PrimitiveBuffer != null;
    }
}
#endif
