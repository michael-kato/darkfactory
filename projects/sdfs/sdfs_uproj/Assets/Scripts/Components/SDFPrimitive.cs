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

public class SDFPrimitive : MonoBehaviour
{
    [Header("SDF Settings")]
    [SerializeField] private SDFPrimitiveType type = SDFPrimitiveType.Sphere;
    [SerializeField] private float blendRadius = 0.5f;
    [SerializeField] private BlendMode blendMode = BlendMode.Union;

    [Header("Material")]
    [SerializeField] private Color baseColor = new Color(0.3f, 0.6f, 1f);
    [SerializeField] private float metallic = 0f;
    [SerializeField] private float roughness = 0.5f;
    [SerializeField] private float ior = 1.33f;
    [SerializeField] private Color emission = Color.black;

    [Header("Physics")]
    [SerializeField] private Vector3 velocity = Vector3.zero;
    [SerializeField] private Vector3 displacement = Vector3.zero;

    [Header("Selection")]
    [SerializeField] private bool isSelected = false;

    public SDFPrimitiveType Type
    {
        get => type;
        set => type = value;
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

    public Vector3 Position
    {
        get => transform.position;
        set => transform.position = value;
    }

    public Vector3 Scale
    {
        get => transform.localScale;
        set => transform.localScale = value;
    }

    public Quaternion Rotation
    {
        get => transform.rotation;
        set => transform.rotation = value;
    }

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

    public bool IsSelected
    {
        get => isSelected;
        set => isSelected = value;
    }

    public void SyncFromTransform()
    {
        // No-op - position/scale are now direct proxies to transform
    }
}
