using UnityEngine;
using System.Collections.Generic;
using System.IO;
using System.Text;

public class SDFExporter : MonoBehaviour
{
    [SerializeField] private SDFSceneManager sceneManager;
    [SerializeField] private int exportResolution = 64;
    
    public void ExportOBJ(string path)
    {
        if (sceneManager == null || sceneManager.PrimitiveBuffer == null)
        {
            Debug.LogError("No SDF data to export");
            return;
        }

        Mesh mesh = GenerateMesh(exportResolution);
        if (mesh == null)
        {
            Debug.LogError("Failed to generate mesh");
            return;
        }

        StringBuilder sb = new StringBuilder();
        sb.AppendLine("o SDF_Export");
        
        foreach (Vector3 v in mesh.vertices)
        {
            sb.AppendLine($"v {v.x} {v.y} {v.z}");
        }
        
        foreach (Vector3 n in mesh.normals)
        {
            sb.AppendLine($"vn {n.x} {n.y} {n.z}");
        }
        
        int[] tris = mesh.triangles;
        for (int i = 0; i < tris.Length; i += 3)
        {
            sb.AppendLine($"f {tris[i]+1}//{tris[i]+1} {tris[i+1]+1}//{tris[i+1]+1} {tris[i+2]+1}//{tris[i+2]+1}");
        }

        File.WriteAllText(path, sb.ToString());
        Debug.Log($"Exported OBJ to: {path}");
        
        Destroy(mesh);
    }

    public void SaveScene(string path)
    {
        if (sceneManager == null)
        {
            Debug.LogError("No scene manager");
            return;
        }

        SDFSceneData data = new SDFSceneData();
        data.physics = new PhysicsData
        {
            stiffness = sceneManager.Stiffness,
            damping = sceneManager.Damping,
            amplitude = sceneManager.Amplitude,
            waveFrequency = sceneManager.WaveFrequency,
            physicsEnabled = sceneManager.PhysicsEnabled
        };

        SDFPrimitive[] primitives = FindObjectsOfType<SDFPrimitive>();
        data.primitives = new List<PrimitiveData>();

        foreach (var prim in primitives)
        {
            data.primitives.Add(new PrimitiveData
            {
                type = prim.Type.ToString(),
                position = prim.Position,
                scale = prim.Scale,
                blendRadius = prim.BlendRadius,
                blendMode = prim.BlendMode.ToString(),
                baseColor = new float[] { prim.BaseColor.r, prim.BaseColor.g, prim.BaseColor.b, prim.BaseColor.a },
                metallic = prim.Metallic,
                roughness = prim.Roughness,
                ior = prim.Ior,
                emission = new float[] { prim.Emission.r, prim.Emission.g, prim.Emission.b }
            });
        }

        string json = JsonUtility.ToJson(data, true);
        File.WriteAllText(path, json);
        Debug.Log($"Scene saved to: {path}");
    }

    public void LoadScene(string path)
    {
        if (sceneManager == null)
        {
            Debug.LogError("No scene manager");
            return;
        }

        string json = File.ReadAllText(path);
        SDFSceneData data = JsonUtility.FromJson<SDFSceneData>(json);

        sceneManager.ClearAllPrimitives();

        if (data.physics != null)
        {
            sceneManager.Stiffness = data.physics.stiffness;
            sceneManager.Damping = data.physics.damping;
            sceneManager.Amplitude = data.physics.amplitude;
            sceneManager.WaveFrequency = data.physics.waveFrequency;
            sceneManager.PhysicsEnabled = data.physics.physicsEnabled;
        }

        if (data.primitives != null)
        {
            foreach (var p in data.primitives)
            {
                SDFPrimitiveType type = (SDFPrimitiveType)System.Enum.Parse(typeof(SDFPrimitiveType), p.type);
                sceneManager.AddPrimitive(type, p.position, p.scale);
            }
        }

        Debug.Log($"Scene loaded from: {path}");
    }

    private Mesh GenerateMesh(int resolution)
    {
        float step = 4f / resolution;
        List<Vector3> vertices = new List<Vector3>();
        List<int> triangles = new List<int>();

        for (int x = 0; x < resolution; x++)
        {
            for (int y = 0; y < resolution; y++)
            {
                for (int z = 0; z < resolution; z++)
                {
                    Vector3 pos = new Vector3(
                        -2f + x * step,
                        -2f + y * step,
                        -2f + z * step
                    );

                    float d = SampleSDF(pos);
                    if (d < 0)
                    {
                        bool hasFace = false;
                        if (x == 0 || SampleSDF(pos - new Vector3(step, 0, 0)) >= 0) hasFace = true;
                        if (y == 0 || SampleSDF(pos - new Vector3(0, step, 0)) >= 0) hasFace = true;
                        if (z == 0 || SampleSDF(pos - new Vector3(0, 0, step)) >= 0) hasFace = true;

                        if (hasFace)
                        {
                            int baseIndex = vertices.Count;
                            vertices.Add(pos);
                            vertices.Add(pos + new Vector3(step, 0, 0));
                            vertices.Add(pos + new Vector3(step, step, 0));
                            vertices.Add(pos + new Vector3(0, step, 0));

                            triangles.Add(baseIndex);
                            triangles.Add(baseIndex + 1);
                            triangles.Add(baseIndex + 2);
                            triangles.Add(baseIndex);
                            triangles.Add(baseIndex + 2);
                            triangles.Add(baseIndex + 3);
                        }
                    }
                }
            }
        }

        if (vertices.Count == 0) return null;

        Mesh mesh = new Mesh();
        mesh.vertices = vertices.ToArray();
        mesh.triangles = triangles.ToArray();
        mesh.RecalculateNormals();
        
        return mesh;
    }

    private float SampleSDF(Vector3 p)
    {
        if (sceneManager == null) return float.MaxValue;
        
        float d = float.MaxValue;
        
        SDFPrimitive[] primitives = FindObjectsOfType<SDFPrimitive>();
        foreach (var prim in primitives)
        {
            float primD = GetPrimitiveDistance(p, prim);
            switch (prim.BlendMode)
            {
                case BlendMode.Union:
                    d = Mathf.Min(d, primD);
                    break;
                case BlendMode.Subtraction:
                    d = Mathf.Max(-d, primD);
                    break;
                case BlendMode.Intersection:
                    d = Mathf.Max(d, primD);
                    break;
            }
            
            if (prim.BlendRadius > 0)
            {
                float k = prim.BlendRadius;
                float smin = d + primD - k * Mathf.Sqrt(2 * k * k - (d - primD) * (d - primD));
                if (k > 0)
                {
                    float h = Mathf.Clamp01(0.5f + 0.5f * (d - primD) / k);
                    d = Mathf.Lerp(d, primD, h) - k * h * (1 - h);
                }
            }
        }
        
        return d;
    }

    private float GetPrimitiveDistance(Vector3 p, SDFPrimitive prim)
    {
        Vector3 pos = prim.Position;
        Vector3 scale = prim.Scale;

        switch (prim.Type)
        {
            case SDFPrimitiveType.Sphere:
                return Vector3.Distance(p, pos) - scale.x;
            case SDFPrimitiveType.Box:
                Vector3 q = p - pos;
                q = new Vector3(Mathf.Abs(q.x), Mathf.Abs(q.y), Mathf.Abs(q.z)) - scale;
                return Vector3.Distance(Vector3.Max(q, Vector3.zero), Vector3.Min(q, Vector3.one)) - 0.01f;
            case SDFPrimitiveType.Cylinder:
                float x = Vector3.Distance(new Vector2(p.x, p.z), new Vector2(pos.x, pos.z)) - scale.x;
                float y = Mathf.Abs(p.y - pos.y) - scale.y;
                return Mathf.Min(Mathf.Max(x, y), 0) + Vector3.Distance(new Vector2(Mathf.Max(x, 0), Mathf.Max(y, 0)), Vector2.zero);
            default:
                return Vector3.Distance(p, pos) - scale.x;
        }
    }
}

[System.Serializable]
public class SDFSceneData
{
    public PhysicsData physics;
    public List<PrimitiveData> primitives;
}

[System.Serializable]
public class PhysicsData
{
    public float stiffness;
    public float damping;
    public float amplitude;
    public float waveFrequency;
    public bool physicsEnabled;
}

[System.Serializable]
public class PrimitiveData
{
    public string type;
    public Vector3 position;
    public Vector3 scale;
    public float blendRadius;
    public string blendMode;
    public float[] baseColor;
    public float metallic;
    public float roughness;
    public float ior;
    public float[] emission;
}
