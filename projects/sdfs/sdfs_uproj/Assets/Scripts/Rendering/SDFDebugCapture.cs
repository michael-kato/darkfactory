using UnityEngine;

public class SDFDebugCapture : MonoBehaviour
{
    [SerializeField] private SDFRenderer sdfRenderer;
    [SerializeField] private SDFSceneManager sceneManager;
    [SerializeField] private Camera captureCamera;
    
    private void Start()
    {
        if (captureCamera == null)
            captureCamera = GetComponent<Camera>();
            
        Invoke("CaptureDebugImage", 1f);
    }

    private void CaptureDebugImage()
    {
        Debug.Log($"[SDF Debug] Capture starting...");
        Debug.Log($"[SDF Debug] Renderer present: {sdfRenderer != null}");
        Debug.Log($"[SDF Debug] Scene Manager: {sceneManager != null}");
        if (sceneManager != null)
        {
            Debug.Log($"[SDF Debug] Primitive count: {sceneManager.PrimitiveCount}");
            Debug.Log($"[SDF Debug] Primitive buffer: {sceneManager.PrimitiveBuffer}");
        }
        
        RenderTexture rt = new RenderTexture(512, 512, 24);
        captureCamera.targetTexture = rt;
        captureCamera.Render();
        RenderTexture.active = rt;
        
        Texture2D tex = new Texture2D(512, 512, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, 512, 512), 0, 0);
        tex.Apply();
        
        byte[] bytes = tex.EncodeToPNG();
        string path = Application.dataPath + "/../debug_sdf.png";
        System.IO.File.WriteAllBytes(path, bytes);
        Debug.Log($"[SDF Debug] Screenshot saved to: {path}");
        
        captureCamera.targetTexture = null;
        RenderTexture.active = null;
        rt.Release();
    }
}
