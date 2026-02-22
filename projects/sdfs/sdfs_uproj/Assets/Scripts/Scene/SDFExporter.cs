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
            default:
                return Vector3.Distance(p, pos) - scale.x;
        }
    }
}
