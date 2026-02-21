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
    public float timeOffset;
}

public class SDFSceneManager : MonoBehaviour
{
    [SerializeField] private int maxPrimitives = 64;
    
    [Header("Physics")]
    [SerializeField] private float stiffness = 2.0f;
    [SerializeField] private float damping = 0.8f;
    [SerializeField] private float amplitude = 0.5f;
    [SerializeField] private float waveFrequency = 3.0f;
    [SerializeField] private bool physicsEnabled = true;
    
    private ComputeBuffer _primitiveBuffer;
    private SDFPrimitiveData[] _primitiveData;
    private List<SDFPrimitive> _primitives = new List<SDFPrimitive>();
    private SDFPrimitive _selectedPrimitive;
    private float _time;

    public ComputeBuffer PrimitiveBuffer => _primitiveBuffer;
    public int PrimitiveCount => _primitives.Count;
    public SDFPrimitive SelectedPrimitive => _selectedPrimitive;
    
    public float Stiffness { get => stiffness; set => stiffness = value; }
    public float Damping { get => damping; set => damping = value; }
    public float Amplitude { get => amplitude; set => amplitude = value; }
    public float WaveFrequency { get => waveFrequency; set => waveFrequency = value; }
    public bool PhysicsEnabled { get => physicsEnabled; set => physicsEnabled = value; }

    public event System.Action<SDFPrimitive> OnSelectionChanged;

    private void Start()
    {
        _primitiveData = new SDFPrimitiveData[maxPrimitives];
        
        _primitiveBuffer = new ComputeBuffer(
            maxPrimitives,
            Marshal.SizeOf(typeof(SDFPrimitiveData))
        );

        CollectPrimitives();
    }

    private void Update()
    {
        _time += Time.deltaTime;
        CollectPrimitives();
        UpdatePhysics();
        UpdateBuffer();
    }

    private void CollectPrimitives()
    {
        _primitives.Clear();
        _primitives.AddRange(FindObjectsOfType<SDFPrimitive>());
    }

    private void UpdatePhysics()
    {
        if (!physicsEnabled) return;
        
        float dt = Time.deltaTime;
        
        for (int i = 0; i < _primitives.Count; i++)
        {
            SDFPrimitive prim = _primitives[i];
            if (prim == null) continue;
            
            Vector3 targetPos = prim.BasePosition;
            Vector3 currentPos = prim.Position;
            
            Vector3 displacement = prim.Displacement;
            Vector3 velocity = prim.Velocity;
            
            Vector3 springForce = (targetPos - currentPos - displacement) * stiffness;
            Vector3 dampingForce = -velocity * damping;
            
            Vector3 acceleration = springForce + dampingForce;
            velocity += acceleration * dt;
            displacement += velocity * dt;
            
            float maxDisplacement = amplitude * 0.5f;
            displacement = Vector3.ClampMagnitude(displacement, maxDisplacement);
            
            float wobble = Mathf.Sin(_time * waveFrequency + prim.TimeOffset) * amplitude;
            Vector3 wobbleOffset = new Vector3(
                Mathf.Sin(_time * waveFrequency * 1.3f + prim.TimeOffset),
                Mathf.Sin(_time * waveFrequency * 0.9f + prim.TimeOffset + 1.0f),
                Mathf.Sin(_time * waveFrequency * 1.1f + prim.TimeOffset + 2.0f)
            ) * wobble * 0.1f;
            
            prim.Velocity = velocity;
            prim.Displacement = displacement + wobbleOffset;
        }
    }

    private void UpdateBuffer()
    {
        for (int i = 0; i < _primitives.Count && i < maxPrimitives; i++)
        {
            SDFPrimitive prim = _primitives[i];
            _primitiveData[i] = new SDFPrimitiveData
            {
                position = prim.Position,
                scale = prim.Scale,
                type = (int)prim.Type,
                blendRadius = prim.BlendRadius,
                blendMode = (int)prim.BlendMode,
                velocity = prim.Velocity,
                displacement = prim.Displacement,
                timeOffset = prim.TimeOffset
            };
        }

        if (_primitives.Count > 0)
        {
            _primitiveBuffer.SetData(_primitiveData);
        }
    }

    public void AddPrimitive(SDFPrimitiveType type, Vector3 position, Vector3 scale)
    {
        GameObject primObj = new GameObject($"Primitive_{type}");
        primObj.transform.position = position;
        primObj.transform.localScale = scale;
        
        SDFPrimitive prim = primObj.AddComponent<SDFPrimitive>();
        prim.Type = type;
        prim.BlendMode = BlendMode.Union;
        prim.BlendRadius = 0.5f;
        prim.BasePosition = position;
        prim.TimeOffset = Random.Range(0f, Mathf.PI * 2f);
    }

    public void RemovePrimitive(SDFPrimitive prim)
    {
        if (prim != null)
        {
            Destroy(prim.gameObject);
        }
    }

    public void ClearAllPrimitives()
    {
        foreach (var prim in _primitives)
        {
            if (prim != null)
            {
                Destroy(prim.gameObject);
            }
        }
        _primitives.Clear();
        _selectedPrimitive = null;
        OnSelectionChanged?.Invoke(_selectedPrimitive);
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
