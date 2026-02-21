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

    private void Start()
    {
        _camera = Camera.main;
        if (_camera == null)
        {
            GameObject camObj = new GameObject("Main Camera");
            _camera = camObj.AddComponent<Camera>();
            camObj.AddComponent<AudioListener>();
        }

        _camera.enabled = false;

        CreateFullscreenQuad();
        SetupMaterial();
    }

    private void CreateFullscreenQuad()
    {
        _meshFilter = gameObject.AddComponent<MeshFilter>();
        _meshRenderer = gameObject.AddComponent<MeshRenderer>();

        Mesh quad = new Mesh();
        quad.name = "FullscreenQuad";

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

        quad.vertices = vertices;
        quad.uv = uvs;
        quad.triangles = triangles;
        quad.RecalculateNormals();

        _meshFilter.mesh = quad;
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
        if (sdfMaterial == null || _camera == null) return;

        Matrix4x4 cameraMatrix = _camera.cameraToWorldMatrix * _camera.projectionMatrix.inverse;
        sdfMaterial.SetMatrix("_CameraMatrix", cameraMatrix);
        sdfMaterial.SetVector("_CameraPosition", _camera.transform.position);

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
