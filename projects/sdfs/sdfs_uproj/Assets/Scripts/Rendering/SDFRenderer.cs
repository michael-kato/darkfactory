using UnityEngine;

public class SDFRenderer : MonoBehaviour
{
    [SerializeField] private Material sdfMaterial;
    [SerializeField] private SDFSceneManager sceneManager;
    
    [SerializeField] private float maxDistance = 100f;
    [SerializeField] private int maxSteps = 64;
    [SerializeField] private float surfaceThreshold = 0.001f;

    private Camera _camera;
    private MeshRenderer _meshRenderer;
    private MeshFilter _meshFilter;
    private Mesh _fullscreenQuad;
    private GameObject _quadObject;

    private void Start()
    {
        _camera = Camera.main;
        if (_camera == null)
        {
            GameObject camObj = new GameObject("Main Camera");
            _camera = camObj.AddComponent<Camera>();
            camObj.AddComponent<AudioListener>();
        }

        CreateFullscreenQuad();
        SetupMaterial();
        
        Debug.Log("[SDFRenderer] Initialized. Camera: " + (_camera != null) + ", Material: " + (sdfMaterial != null));
    }

    private void CreateFullscreenQuad()
    {
        _quadObject = new GameObject("SDF Quad");
        _quadObject.transform.SetParent(_camera.transform);
        _quadObject.transform.localPosition = new Vector3(0, 0, 1);
        _quadObject.transform.localRotation = Quaternion.identity;
        _quadObject.transform.localScale = new Vector3(2 * _camera.aspect * Mathf.Tan(_camera.fieldOfView * 0.5f * Mathf.Deg2Rad) * 2, 2 * Mathf.Tan(_camera.fieldOfView * 0.5f * Mathf.Deg2Rad) * 2, 1);

        _meshFilter = _quadObject.AddComponent<MeshFilter>();
        _meshRenderer = _quadObject.AddComponent<MeshRenderer>();

        _fullscreenQuad = new Mesh();
        _fullscreenQuad.name = "FullscreenQuad";

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

        _fullscreenQuad.vertices = vertices;
        _fullscreenQuad.uv = uvs;
        _fullscreenQuad.triangles = triangles;
        _fullscreenQuad.RecalculateNormals();

        _meshFilter.mesh = _fullscreenQuad;
    }

    private void SetupMaterial()
    {
        if (sdfMaterial == null)
        {
            Shader shader = Shader.Find("SDF/Render");
            if (shader != null)
            {
                sdfMaterial = new Material(shader);
            }
            else
            {
                Debug.LogError("SDF/Render shader not found!");
                return;
            }
        }

        sdfMaterial.SetFloat("_MaxDistance", maxDistance);
        sdfMaterial.SetInt("_MaxSteps", maxSteps);
        sdfMaterial.SetFloat("_SurfaceThreshold", surfaceThreshold);

        _meshRenderer.material = sdfMaterial;
        _meshRenderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        _meshRenderer.receiveShadows = false;
    }

    private void LateUpdate()
    {
        UpdateQuadSize();
        UpdateShaderParameters();
    }

    private void UpdateQuadSize()
    {
        if (_quadObject != null && _camera != null)
        {
            float fov = _camera.fieldOfView;
            float aspect = _camera.aspect;
            float distance = 1f;
            float height = 2f * distance * Mathf.Tan(fov * 0.5f * Mathf.Deg2Rad);
            float width = height * aspect;
            _quadObject.transform.localScale = new Vector3(width, height, 1);
            _quadObject.transform.localPosition = new Vector3(0, 0, distance);
        }
    }

    private void UpdateShaderParameters()
    {
        if (sdfMaterial == null || _camera == null) return;

        Matrix4x4 viewMatrix = _camera.worldToCameraMatrix;
        Matrix4x4 projMatrix = _camera.projectionMatrix;
        Matrix4x4 viewProjMatrix = projMatrix * viewMatrix;
        Matrix4x4 inverseViewProj = viewProjMatrix.inverse;
        
        sdfMaterial.SetMatrix("_ViewProjectionMatrix", viewProjMatrix);
        sdfMaterial.SetMatrix("_InverseViewProjection", inverseViewProj);
        sdfMaterial.SetVector("_CameraPosition", _camera.transform.position);
        sdfMaterial.SetVector("_CameraForward", _camera.transform.forward);
        sdfMaterial.SetVector("_CameraRight", _camera.transform.right);
        sdfMaterial.SetVector("_CameraUp", _camera.transform.up);

        float fov = _camera.fieldOfView;
        float aspect = _camera.aspect;
        float tanHalfFov = Mathf.Tan(fov * 0.5f * Mathf.Deg2Rad);
        sdfMaterial.SetVector("_CameraParams", new Vector4(tanHalfFov, aspect, fov, 0));

        if (sceneManager != null && sceneManager.PrimitiveBuffer != null)
        {
            sdfMaterial.SetBuffer("_Primitives", sceneManager.PrimitiveBuffer);
            sdfMaterial.SetInt("_PrimitiveCount", sceneManager.PrimitiveCount);
        }
    }

    private void OnRenderImage(RenderTexture source, RenderTexture destination)
    {
        if (sdfMaterial != null)
        {
            Graphics.Blit(source, destination, sdfMaterial);
        }
        else
        {
            Graphics.Blit(source, destination);
        }
    }
}
