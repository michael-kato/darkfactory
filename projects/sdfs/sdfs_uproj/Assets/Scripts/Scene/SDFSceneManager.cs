using System.Collections.Generic;
using UnityEngine;
using System.Runtime.InteropServices;

public struct SDFPrimitiveData
{
    public Vector3 position;
    public Vector3 scale;
    public int type;
    public float blendRadius;
    public int blendMode;
    public Vector3 velocity;
    public Vector3 displacement;
    public Vector4 baseColor;
    public float metallic;
    public float roughness;
    public float ior;
    public Vector3 emission;
}

public class SDFSceneManager : MonoBehaviour
{
    [SerializeField] private int maxPrimitives = 64;
    
    [Header("Physics")]
    [SerializeField] private float stiffness = 5.0f;
    [SerializeField] private float damping = 3.0f;
    [SerializeField] private float amplitude = 0.3f;
    [SerializeField] private bool physicsEnabled = true;
    
    private ComputeBuffer _primitiveBuffer;
    private SDFPrimitiveData[] _primitiveData;
    private List<SDFPrimitive> _primitives = new List<SDFPrimitive>();
    private SDFPrimitive _selectedPrimitive;
    private Vector3[] _prevPositions;

    public ComputeBuffer PrimitiveBuffer => _primitiveBuffer;
    public int PrimitiveCount => _primitives.Count;
    public SDFPrimitive SelectedPrimitive => _selectedPrimitive;
    
    public float Stiffness { get => stiffness; set => stiffness = value; }
    public float Damping { get => damping; set => damping = value; }
    public float Amplitude { get => amplitude; set => amplitude = value; }
    public float WaveFrequency { get; set; }
    public bool PhysicsEnabled { get => physicsEnabled; set => physicsEnabled = value; }

    public event System.Action<SDFPrimitive> OnSelectionChanged;

    private void Start()
    {
        _primitiveData = new SDFPrimitiveData[maxPrimitives];
        _prevPositions = new Vector3[maxPrimitives];
        
        _primitiveBuffer = new ComputeBuffer(
            maxPrimitives,
            Marshal.SizeOf(typeof(SDFPrimitiveData))
        );

        CollectPrimitives();
    }

    private void Update()
    {
        CollectPrimitives();
        UpdatePhysics();
        UpdateBuffer();
    }

    private void CollectPrimitives()
    {
        int count = _primitives.Count;
        _primitives.Clear();
        _primitives.AddRange(FindObjectsByType<SDFPrimitive>(FindObjectsSortMode.None));
        
        if (_prevPositions.Length < _primitives.Count)
        {
            _prevPositions = new Vector3[Mathf.Max(_primitives.Count, maxPrimitives)];
        }
        
        for (int i = 0; i < _primitives.Count; i++)
        {
            if (i >= count)
            {
                _prevPositions[i] = _primitives[i].Position;
            }
        }
    }

    private void UpdatePhysics()
    {
        if (!physicsEnabled) return;
        
        float dt = Time.deltaTime;
        
        for (int i = 0; i < _primitives.Count; i++)
        {
            SDFPrimitive prim = _primitives[i];
            if (prim == null) continue;
            
            Vector3 currentPos = prim.Position;
            Vector3 prevPos = _prevPositions[i];
            
            Vector3 delta = currentPos - prevPos;
            float moveSpeed = delta.magnitude / Mathf.Max(dt, 0.001f);
            
            if (moveSpeed > 0.1f)
            {
                Vector3 displacement = prim.Displacement;
                Vector3 velocity = prim.Velocity;
                
                velocity += delta * stiffness;
                velocity *= Mathf.Max(0, 1f - damping * dt);
                
                displacement += velocity * dt;
                displacement = Vector3.ClampMagnitude(displacement, amplitude);
                
                prim.Velocity = velocity;
                prim.Displacement = displacement;
            }
            else
            {
                Vector3 velocity = prim.Velocity * Mathf.Max(0, 1f - damping * dt * 2f);
                Vector3 displacement = prim.Displacement * Mathf.Max(0, 1f - damping * dt);
                
                if (displacement.magnitude < 0.001f)
                {
                    displacement = Vector3.zero;
                    velocity = Vector3.zero;
                }
                
                prim.Velocity = velocity;
                prim.Displacement = displacement;
            }
            
            _prevPositions[i] = currentPos;
        }
    }

    private void UpdateBuffer()
    {
        for (int i = 0; i < _primitives.Count && i < maxPrimitives; i++)
        {
            SDFPrimitive prim = _primitives[i];
            Color baseColor = prim.BaseColor;
            Color emission = prim.Emission;
            
            Vector3 renderPos = prim.Position + prim.Displacement;
            
            _primitiveData[i] = new SDFPrimitiveData
            {
                position = renderPos,
                scale = prim.Scale,
                type = (int)prim.Type,
                blendRadius = prim.BlendRadius,
                blendMode = (int)prim.BlendMode,
                velocity = prim.Velocity,
                displacement = prim.Displacement,
                baseColor = new Vector4(baseColor.r, baseColor.g, baseColor.b, baseColor.a),
                metallic = prim.Metallic,
                roughness = prim.Roughness,
                ior = prim.Ior,
                emission = new Vector3(emission.r, emission.g, emission.b)
            };
        }

        if (_primitives.Count > 0)
        {
            _primitiveBuffer.SetData(_primitiveData);
        }
    }

    public void SelectPrimitive(SDFPrimitive prim)
    {
        _selectedPrimitive = prim;
        OnSelectionChanged?.Invoke(_selectedPrimitive);
    }

    public void DeselectAll()
    {
        _selectedPrimitive = null;
        OnSelectionChanged?.Invoke(_selectedPrimitive);
    }

    private void OnDestroy()
    {
        if (_primitiveBuffer != null)
        {
            _primitiveBuffer.Release();
            _primitiveBuffer = null;
        }
    }
}
