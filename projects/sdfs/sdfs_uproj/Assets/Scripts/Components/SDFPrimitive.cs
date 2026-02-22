using UnityEngine;

public enum SDFPrimitiveType
{
    Sphere = 0,
    Box = 1,
    Cylinder = 2,
    Cone = 3,
    Torus = 4,
    Capsule = 5
}

public enum BlendMode
{
    Union = 0,
    Subtraction = 1,
    Intersection = 2
}

[RequireComponent(typeof(MeshFilter))]
[RequireComponent(typeof(MeshRenderer))]
public class SDFPrimitive : MonoBehaviour
{
    [SerializeField] private SDFPrimitiveType type = SDFPrimitiveType.Sphere;
    [SerializeField] private Vector3 position = Vector3.zero;
    [SerializeField] private Vector3 scale = Vector3.one;
    [SerializeField] private Quaternion rotation = Quaternion.identity;
    [SerializeField] private float blendRadius = 0.5f;
    [SerializeField] private BlendMode blendMode = BlendMode.Union;
    [SerializeField] private bool isSelected = false;
    
    [SerializeField] private Vector3 basePosition = Vector3.zero;
    [SerializeField] private Vector3 velocity = Vector3.zero;
    [SerializeField] private Vector3 displacement = Vector3.zero;
    [SerializeField] private float timeOffset = 0f;
    
    [Header("Material")]
    [SerializeField] private Color baseColor = new Color(0.3f, 0.6f, 1f, 1f);
    [SerializeField] private float metallic = 0f;
    [SerializeField] private float roughness = 0.5f;
    [SerializeField] private float ior = 1.33f;
    [SerializeField] private Color emission = Color.black;

    private MeshFilter _meshFilter;
    private MeshRenderer _meshRenderer;
    private Material _primitiveMaterial;

    public Color BaseColor
    {
        get => baseColor;
        set => baseColor = value;
    }
    
    public float Metallic
    {
        get => metallic;
        set => metallic = value;
    }
    
    public float Roughness
    {
        get => roughness;
        set => roughness = value;
    }
    
    public float Ior
    {
        get => ior;
        set => ior = value;
    }
    
    public Color Emission
    {
        get => emission;
        set => emission = value;
    }

    private void Awake()
    {
        _meshFilter = GetComponent<MeshFilter>();
        _meshRenderer = GetComponent<MeshRenderer>();
        
        Shader shader = Shader.Find("Universal Render Pipeline/Lit");
        if (shader == null)
            shader = Shader.Find("Standard");
        if (shader == null)
            shader = Shader.Find("Unlit/Color");
        
        if (shader != null)
        {
            _primitiveMaterial = new Material(shader);
            _primitiveMaterial.color = new Color(0.3f, 0.6f, 1f, 0.8f);
        }
        
        if (_primitiveMaterial == null)
        {
            _primitiveMaterial = new Material(Shader.Find("Unlit/Color"));
            _primitiveMaterial.color = Color.blue;
        }
        
        _meshRenderer.material = _primitiveMaterial;
        
        UpdateMesh();
    }

    public bool IsSelected
    {
        get => isSelected;
        set 
        { 
            isSelected = value; 
            UpdateSelectionState();
        }
    }

    private void UpdateSelectionState()
    {
        if (_primitiveMaterial != null)
        {
            _primitiveMaterial.color = isSelected ? new Color(1f, 0.6f, 0.3f, 0.6f) : new Color(0.3f, 0.6f, 1f, 0.5f);
        }
    }

    public SDFPrimitiveType Type
    {
        get => type;
        set 
        { 
            type = value; 
            UpdateMesh();
        }
    }

    public Vector3 Position
    {
        get => position;
        set => position = value;
    }

    public Vector3 BasePosition
    {
        get => basePosition;
        set => basePosition = value;
    }
    
    public Vector3 Velocity
    {
        get => velocity;
        set => velocity = value;
    }
    
    public Vector3 Displacement
    {
        get => displacement;
        set => displacement = value;
    }
    
    public float TimeOffset
    {
        get => timeOffset;
        set => timeOffset = value;
    }

    public Vector3 Scale
    {
        get => scale;
        set => scale = value;
    }

    public Quaternion Rotation
    {
        get => rotation;
        set => rotation = value;
    }

    public float BlendRadius
    {
        get => blendRadius;
        set => blendRadius = value;
    }

    public BlendMode BlendMode
    {
        get => blendMode;
        set => blendMode = value;
    }

    private void Update()
    {
        transform.position = position + displacement;
        transform.localScale = scale;
        transform.rotation = rotation;
    }

    public void SyncFromTransform()
    {
        position = transform.position;
        basePosition = position;
        scale = transform.localScale;
        rotation = transform.rotation;
    }

    private void UpdateMesh()
    {
        if (_meshFilter == null) return;

        switch (type)
        {
            case SDFPrimitiveType.Sphere:
                _meshFilter.sharedMesh = GetPrimitiveMesh(SDFPrimitiveType.Sphere);
                break;
            case SDFPrimitiveType.Box:
                _meshFilter.sharedMesh = GetPrimitiveMesh(SDFPrimitiveType.Box);
                break;
            case SDFPrimitiveType.Cylinder:
                _meshFilter.sharedMesh = GetPrimitiveMesh(SDFPrimitiveType.Cylinder);
                break;
            case SDFPrimitiveType.Cone:
                _meshFilter.sharedMesh = GetPrimitiveMesh(SDFPrimitiveType.Cone);
                break;
            case SDFPrimitiveType.Torus:
                _meshFilter.sharedMesh = CreateTorusMesh();
                break;
            case SDFPrimitiveType.Capsule:
                _meshFilter.sharedMesh = GetPrimitiveMesh(SDFPrimitiveType.Capsule);
                break;
        }
    }

    private static Mesh GetPrimitiveMesh(SDFPrimitiveType type)
    {
        GameObject temp = null;
        Mesh mesh = null;
        
        switch (type)
        {
            case SDFPrimitiveType.Sphere:
                temp = GameObject.CreatePrimitive(UnityEngine.PrimitiveType.Sphere);
                break;
            case SDFPrimitiveType.Box:
                temp = GameObject.CreatePrimitive(UnityEngine.PrimitiveType.Cube);
                break;
            case SDFPrimitiveType.Cylinder:
                temp = GameObject.CreatePrimitive(UnityEngine.PrimitiveType.Cylinder);
                break;
            case SDFPrimitiveType.Cone:
                mesh = CreateConeMesh();
                return mesh;
            case SDFPrimitiveType.Capsule:
                temp = GameObject.CreatePrimitive(UnityEngine.PrimitiveType.Capsule);
                break;
        }
        
        if (temp != null)
        {
            mesh = temp.GetComponent<MeshFilter>().sharedMesh;
            Destroy(temp);
        }
        
        return mesh;
    }

    private static Mesh CreateConeMesh()
    {
        GameObject temp = GameObject.CreatePrimitive(UnityEngine.PrimitiveType.Cylinder);
        temp.transform.localScale = new Vector3(1, 0.001f, 1);
        Mesh mesh = temp.GetComponent<MeshFilter>().sharedMesh;
        Destroy(temp);
        return mesh;
    }

    private static Mesh CreateTorusMesh()
    {
        GameObject temp = GameObject.CreatePrimitive(UnityEngine.PrimitiveType.Quad);
        Mesh mesh = temp.GetComponent<MeshFilter>().sharedMesh;
        Destroy(temp);
        return mesh;
    }
}
