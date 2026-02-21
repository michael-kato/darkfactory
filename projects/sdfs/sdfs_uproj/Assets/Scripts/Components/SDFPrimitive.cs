using UnityEngine;

public enum PrimitiveType
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
    [SerializeField] private PrimitiveType type = PrimitiveType.Sphere;
    [SerializeField] private Vector3 position = Vector3.zero;
    [SerializeField] private Vector3 scale = Vector3.one;
    [SerializeField] private Quaternion rotation = Quaternion.identity;
    [SerializeField] private float blendRadius = 0.5f;
    [SerializeField] private BlendMode blendMode = BlendMode.Union;
    [SerializeField] private bool isSelected = false;

    public bool IsSelected
    {
        get => isSelected;
        set => isSelected = value;
    }

    public PrimitiveType Type
    {
        get => type;
        set => type = value;
    }

    public Vector3 Position
    {
        get => position;
        set => position = value;
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
        transform.position = position;
        transform.localScale = scale;
        transform.rotation = rotation;
    }

    public void SyncFromTransform()
    {
        position = transform.position;
        scale = transform.localScale;
        rotation = transform.rotation;
    }
}
