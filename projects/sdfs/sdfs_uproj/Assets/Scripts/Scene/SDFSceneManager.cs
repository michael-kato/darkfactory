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
}

public class SDFSceneManager : MonoBehaviour
{
    [SerializeField] private int maxPrimitives = 64;
    
    private ComputeBuffer _primitiveBuffer;
    private SDFPrimitiveData[] _primitiveData;
    private List<SDFPrimitive> _primitives = new List<SDFPrimitive>();
    private SDFPrimitive _selectedPrimitive;

    public ComputeBuffer PrimitiveBuffer => _primitiveBuffer;
    public int PrimitiveCount => _primitives.Count;
    public SDFPrimitive SelectedPrimitive => _selectedPrimitive;

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
        CollectPrimitives();
        UpdateBuffer();
    }

    private void CollectPrimitives()
    {
        _primitives.Clear();
        _primitives.AddRange(FindObjectsOfType<SDFPrimitive>());
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
                blendMode = (int)prim.BlendMode
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
